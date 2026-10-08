from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from project.models import Project
from account.models import Tenant, TenantMembership
from case_app.models import AppExecutionNode
from suite.models import RunResult, Suite
from suite.run_metrics import collect_run_facts
from suite.tasks import _claim_ready_run

from .models import ExecutionTask, ExecutionWorker
from .dispatcher import _enqueue_task, dispatch_waiting_tasks
from .services import WorkerHeartbeat, diagnose_tasks
from Tesla.pagination import PageNumberPagination


class ExecutionControlTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("runner", password="secret")
        self.project = Project.objects.create(name="控制中心项目", pm=self.user)
        self.suite = Suite.objects.create(name="回归套件")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_suite_run_is_synchronized_and_updated(self):
        run = RunResult.objects.create(
            suite=self.suite, project=self.project, path="todo",
            environment_name="Test", status=RunResult.RunStatus.Ready,
        )
        task = ExecutionTask.objects.get(source_type="suite", source_id=run.id)
        self.assertEqual(task.status, ExecutionTask.Status.QUEUED)
        self.assertEqual(task.execution_no, str(run.id))

        run.status = RunResult.RunStatus.Done
        run.is_pass = True
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "is_pass", "finished_at", "update_datetime"])
        task.refresh_from_db()
        self.assertEqual(task.status, ExecutionTask.Status.SUCCEEDED)
        self.assertEqual(task.progress, 100)

    def test_same_run_can_only_be_claimed_once(self):
        run = RunResult.objects.create(
            suite=self.suite, project=self.project, path="todo",
            environment_name="Test", status=RunResult.RunStatus.Ready,
        )

        self.assertTrue(_claim_ready_run(run.id))
        self.assertFalse(_claim_ready_run(run.id))
        run.refresh_from_db()
        self.assertEqual(run.status, RunResult.RunStatus.Running)
        self.assertIsNotNone(run.started_at)

    def test_retry_clears_previous_dispatch_state(self):
        now = timezone.now()
        run = RunResult.objects.create(
            suite=self.suite, project=self.project, path="todo",
            environment_name="Test", status=RunResult.RunStatus.Done,
            is_pass=False, finished_at=now,
        )
        task = ExecutionTask.objects.get(source_type="suite", source_id=run.id)
        ExecutionTask.objects.filter(pk=task.pk).update(
            dispatched_at=now - timedelta(minutes=5), dispatch_attempts=2,
        )

        run.status = RunResult.RunStatus.Ready
        run.started_at = None
        run.finished_at = None
        run.save(update_fields=["status", "started_at", "finished_at", "update_datetime"])

        task.refresh_from_db()
        self.assertEqual(task.status, ExecutionTask.Status.QUEUED)
        self.assertIsNone(task.dispatched_at)
        self.assertEqual(task.dispatch_attempts, 0)

    def test_recent_case_history_uses_finished_time_not_random_run_id(self):
        now = timezone.now()
        common = {
            "suite": self.suite,
            "project": self.project,
            "path": "todo",
            "environment_name": "Test",
            "status": RunResult.RunStatus.Done,
            "native_report": {"scenarios": [{"id": 18, "status": "passed"}]},
        }
        RunResult.objects.create(
            id=9_900_000_001, finished_at=now - timedelta(days=1), **common,
        )
        latest = RunResult.objects.create(
            id=1_100_000_001, finished_at=now, **common,
        )

        facts = collect_run_facts(self.user, "", {18})

        self.assertEqual(facts[18][0]["run_id"], latest.id)

    @patch("execution_control.dispatcher.async_task")
    def test_suite_queue_timeout_includes_finishing_grace(self, async_task):
        run = RunResult.objects.create(
            suite=self.suite, project=self.project, path="todo",
            environment_name="Test", status=RunResult.RunStatus.Ready,
            timeout_seconds=86400,
        )
        task = ExecutionTask.objects.get(source_type="suite", source_id=run.id)

        _enqueue_task(task)

        self.assertEqual(async_task.call_args.kwargs["q_options"]["timeout"], 86700)
        self.assertEqual(async_task.call_args.args[-1], str(run.tenant_id))
        self.assertEqual(async_task.call_args.kwargs["group"], f"tenant-{run.tenant_id}")

    @override_settings(Q_CLUSTER={"workers": 2})
    @patch("execution_control.dispatcher._enqueue_task")
    def test_tenant_concurrency_limit_does_not_block_other_tenants(self, enqueue_task):
        now = timezone.now()
        tenant_a = self.project.tenant
        tenant_a.max_regular_concurrent_executions = 1
        tenant_a.save(update_fields=["max_regular_concurrent_executions"])
        tenant_b = Tenant.objects.create(
            name="并发租户 B", slug="concurrency-tenant-b",
            max_regular_concurrent_executions=1,
        )
        project_b = Project.objects.create(tenant=tenant_b, name="并发项目 B", pm=self.user)
        ExecutionTask.objects.create(
            tenant=tenant_a, source_type="suite", source_id=4100, execution_no="4100",
            project=self.project, name="租户 A 运行中", engine="pytest", status="running",
            last_activity_at=now, queued_at=now - timedelta(seconds=3), started_at=now,
            source_created_at=now, source_updated_at=now,
        )
        waiting_a = ExecutionTask.objects.create(
            tenant=tenant_a, source_type="suite", source_id=4101, execution_no="4101",
            project=self.project, name="租户 A 等待", engine="pytest", status="queued",
            last_activity_at=now, queued_at=now - timedelta(seconds=2),
            source_created_at=now, source_updated_at=now,
        )
        waiting_b = ExecutionTask.objects.create(
            tenant=tenant_b, source_type="suite", source_id=4201, execution_no="4201",
            project=project_b, name="租户 B 等待", engine="pytest", status="queued",
            last_activity_at=now, queued_at=now - timedelta(seconds=1),
            source_created_at=now, source_updated_at=now,
        )

        self.assertEqual(dispatch_waiting_tasks(), 1)
        waiting_a.refresh_from_db()
        waiting_b.refresh_from_db()
        self.assertIsNone(waiting_a.dispatched_at)
        self.assertEqual(waiting_a.waiting_reason, "等待当前租户普通任务并发额度释放")
        self.assertIsNotNone(waiting_b.dispatched_at)
        enqueue_task.assert_called_once()

    @override_settings(EXECUTION_QUEUE_DIAGNOSIS_SECONDS=10, EXECUTION_WORKER_OFFLINE_SECONDS=15)
    def test_queued_task_explains_missing_worker(self):
        run = RunResult.objects.create(
            suite=self.suite, project=self.project, path="todo",
            environment_name="Test", status=RunResult.RunStatus.Ready,
        )
        old = timezone.now() - timedelta(minutes=1)
        ExecutionTask.objects.filter(source_type="suite", source_id=run.id).update(
            queued_at=old, last_activity_at=old,
        )
        diagnose_tasks()
        task = ExecutionTask.objects.get(source_type="suite", source_id=run.id)
        self.assertEqual(task.diagnostic_code, "WORKER_OFFLINE")
        self.assertIn("执行器", task.diagnostic_message)

        WorkerHeartbeat(
            ExecutionWorker.Kind.SCHEDULER, "测试执行器", ["api"], capacity=1,
        ).touch()
        diagnose_tasks()
        task.refresh_from_db()
        self.assertEqual(task.diagnostic_code, "")

    def test_task_list_only_returns_accessible_projects(self):
        visible = ExecutionTask.objects.create(
            source_type="app", source_id=1001, execution_no="1001", project=self.project,
            name="可见任务", engine="Appium", status="succeeded", progress=100,
            last_activity_at=timezone.now(), queued_at=timezone.now(),
            source_created_at=timezone.now(), source_updated_at=timezone.now(),
        )
        other_user = User.objects.create_user("other")
        other_project = Project.objects.create(name="其他项目", pm=other_user)
        ExecutionTask.objects.create(
            source_type="app", source_id=1002, execution_no="1002", project=other_project,
            name="不可见任务", engine="Appium", status="succeeded", progress=100,
            last_activity_at=timezone.now(), queued_at=timezone.now(),
            source_created_at=timezone.now(), source_updated_at=timezone.now(),
        )
        response = self.client.get("/api/execution-control/tasks/?pageSize=100")
        self.assertEqual(response.status_code, 200)
        items = response.data["list"]
        ids = [item["id"] for item in items]
        self.assertIn(visible.id, ids)
        self.assertEqual(len(ids), 1)
        self.assertEqual(items[0]["report_path"], "/execution/report/app/1001")

    def test_task_list_orders_by_execution_start_time_descending(self):
        now = timezone.now()
        older = ExecutionTask.objects.create(
            source_type="app", source_id=1101, execution_no="1101", project=self.project,
            name="较早开始", engine="Appium", status="succeeded", progress=100,
            last_activity_at=now, queued_at=now - timedelta(minutes=3),
            started_at=now - timedelta(minutes=2), finished_at=now - timedelta(minutes=1),
            source_created_at=now, source_updated_at=now,
        )
        newer = ExecutionTask.objects.create(
            source_type="app", source_id=1102, execution_no="1102", project=self.project,
            name="较晚开始", engine="Appium", status="succeeded", progress=100,
            last_activity_at=now, queued_at=now - timedelta(minutes=5),
            started_at=now - timedelta(seconds=30), finished_at=now,
            source_created_at=now - timedelta(days=1), source_updated_at=now,
        )

        response = self.client.get("/api/execution-control/tasks/?pageSize=100")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.data["list"]],
            [newer.id, older.id],
        )

    @patch("execution_control.views.diagnose_tasks")
    def test_only_overview_runs_task_diagnosis(self, diagnose):
        list_response = self.client.get("/api/execution-control/tasks/?pageSize=100")
        self.assertEqual(list_response.status_code, 200)
        diagnose.assert_not_called()

        overview_response = self.client.get("/api/execution-control/tasks/overview/")
        self.assertEqual(overview_response.status_code, 200)
        diagnose.assert_called_once()

    def test_queue_positions_are_annotated_without_per_row_queries(self):
        now = timezone.now()
        tasks = [
            ExecutionTask.objects.create(
                source_type="suite", source_id=1201, execution_no="1201",
                project=self.project, name="普通队列 1", engine="pytest", status="queued",
                last_activity_at=now, queued_at=now - timedelta(seconds=3),
                source_created_at=now, source_updated_at=now,
            ),
            ExecutionTask.objects.create(
                source_type="app", source_id=1202, execution_no="1202",
                project=self.project, name="普通队列 2", engine="Appium", status="queued",
                last_activity_at=now, queued_at=now - timedelta(seconds=2),
                source_created_at=now, source_updated_at=now,
            ),
            ExecutionTask.objects.create(
                source_type="performance", source_id=1203, execution_no="1203",
                project=self.project, name="性能队列 1", engine="Locust", status="queued",
                last_activity_at=now, queued_at=now - timedelta(seconds=1),
                source_created_at=now, source_updated_at=now,
            ),
        ]

        with CaptureQueriesContext(connection) as captured:
            response = self.client.get("/api/execution-control/tasks/?pageSize=100")

        self.assertEqual(response.status_code, 200)
        positions = {item["id"]: item["queue_position"] for item in response.data["list"]}
        self.assertEqual([positions[task.id] for task in tasks], [1, 2, 1])
        # 分页 COUNT + 列表主查询为固定查询；不得再每个排队任务追加 COUNT。
        self.assertLessEqual(len(captured), 8)

    def test_page_size_is_capped(self):
        request = Request(APIRequestFactory().get("/tasks/", {"pageSize": 999999}))
        self.assertEqual(PageNumberPagination().get_page_size(request), 1000)

    def test_task_list_supports_twenty_items_per_page(self):
        now = timezone.now()
        ExecutionTask.objects.bulk_create([
            ExecutionTask(
                source_type="app",
                source_id=5000 + index,
                execution_no=str(5000 + index),
                project=self.project,
                name=f"分页任务 {index}",
                engine="Appium",
                status="succeeded",
                progress=100,
                last_activity_at=now,
                queued_at=now - timedelta(seconds=index),
                started_at=now - timedelta(seconds=index),
                finished_at=now,
                source_created_at=now,
                source_updated_at=now,
            )
            for index in range(21)
        ])

        first_page = self.client.get("/api/execution-control/tasks/?page=1&pageSize=20")
        second_page = self.client.get("/api/execution-control/tasks/?page=2&pageSize=20")

        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(first_page.data["itemCount"], 21)
        self.assertEqual(len(first_page.data["list"]), 20)
        self.assertEqual(len(second_page.data["list"]), 1)

    def test_effective_start_order_has_matching_index(self):
        names = {index.name for index in ExecutionTask._meta.indexes}
        self.assertIn("exec_task_tenant_started_idx", names)

    def test_overview_does_not_count_historical_errors_as_actionable(self):
        ExecutionTask.objects.create(
            source_type="app", source_id=2001, execution_no="2001", project=self.project,
            name="历史异常", engine="Appium", status="error", progress=100,
            diagnostic_code="SOURCE_ERROR", diagnostic_message="历史设备占用异常",
            last_activity_at=timezone.now(), queued_at=timezone.now(), finished_at=timezone.now(),
            source_created_at=timezone.now(), source_updated_at=timezone.now(),
        )
        response = self.client.get("/api/execution-control/tasks/overview/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["active"], 0)
        self.assertEqual(response.data["abnormal_tasks"], 0)
        self.assertEqual(response.data["abnormal"], response.data["abnormal_services"])

    @patch("execution_control.views.dependency_overview")
    def test_overview_counts_offline_service_as_actionable(self, dependency_overview):
        dependency_overview.return_value = [
            {"key": "database", "name": "数据库", "status": "online", "message": "连接正常"},
            {
                "key": "performance",
                "name": "性能执行器",
                "status": "offline",
                "message": "未检测到有效心跳",
            },
        ]

        response = self.client.get("/api/execution-control/tasks/overview/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["abnormal_tasks"], 0)
        self.assertEqual(response.data["abnormal_services"], 1)
        self.assertEqual(response.data["abnormal"], 1)
        dependency_overview.assert_called_once_with(
            tenant=self.project.tenant,
            user=self.user,
        )

    def test_overview_does_not_count_unconfigured_appium_as_abnormal(self):
        response = self.client.get("/api/execution-control/tasks/overview/")

        self.assertEqual(response.status_code, 200)
        appium = next(item for item in response.data["services"] if item["key"] == "appium")
        self.assertEqual(appium["status"], "not_configured")
        self.assertEqual(appium["message"], "当前租户未配置启用的 Appium 节点")
        self.assertIsNone(appium["last_heartbeat_at"])
        explicit_abnormal = sum(
            item["status"] in {"offline", "degraded"}
            for item in response.data["services"]
        )
        self.assertEqual(response.data["abnormal_services"], explicit_abnormal)

    def test_overview_appium_service_only_counts_current_tenant_accessible_projects(self):
        tenant = self.project.tenant
        TenantMembership.objects.create(
            tenant=tenant,
            user=self.user,
            role=TenantMembership.Role.MEMBER,
        )
        AppExecutionNode.objects.create(
            project=self.project,
            name="可见节点",
            enabled=True,
            status="online",
            last_seen_at=timezone.now(),
            created_by=self.user,
        )

        other_user = User.objects.create_user("other-appium-user")
        inaccessible_project = Project.objects.create(
            tenant=tenant,
            name="同租户不可见项目",
            pm=other_user,
        )
        AppExecutionNode.objects.create(
            project=inaccessible_project,
            name="同租户不可见节点",
            enabled=True,
            status="online",
            last_seen_at=timezone.now(),
            created_by=other_user,
        )

        other_tenant = Tenant.objects.create(name="Appium 租户 B", slug="appium-tenant-b")
        other_tenant_project = Project.objects.create(
            tenant=other_tenant,
            name="其他租户项目",
            pm=self.user,
        )
        AppExecutionNode.objects.create(
            project=other_tenant_project,
            name="其他租户节点",
            enabled=True,
            status="online",
            last_seen_at=timezone.now(),
            created_by=self.user,
        )

        response = self.client.get(
            "/api/execution-control/tasks/overview/",
            HTTP_X_TENANT_ID=str(tenant.id),
        )

        self.assertEqual(response.status_code, 200)
        appium = next(item for item in response.data["services"] if item["key"] == "appium")
        self.assertEqual(appium["status"], "online")
        self.assertEqual(appium["message"], "1/1 个启用节点在线")
        self.assertIsNotNone(appium["last_heartbeat_at"])

    @override_settings(APPIUM_NODE_OFFLINE_SECONDS=60)
    def test_overview_marks_stale_appium_heartbeat_offline(self):
        heartbeat = timezone.now() - timedelta(minutes=2)
        node = AppExecutionNode.objects.create(
            project=self.project,
            name="心跳过期节点",
            enabled=True,
            status="online",
            last_seen_at=heartbeat,
            created_by=self.user,
        )

        response = self.client.get("/api/execution-control/tasks/overview/")

        self.assertEqual(response.status_code, 200)
        appium = next(item for item in response.data["services"] if item["key"] == "appium")
        self.assertEqual(appium["status"], "offline")
        self.assertIsNotNone(appium["last_heartbeat_at"])
        node.refresh_from_db()
        self.assertEqual(node.status, "offline")

    def test_platform_admin_appium_service_still_respects_selected_tenant(self):
        tenant = self.project.tenant
        AppExecutionNode.objects.create(
            project=self.project,
            name="当前租户离线节点",
            enabled=True,
            status="offline",
            created_by=self.user,
        )
        other_tenant = Tenant.objects.create(name="Appium 租户 C", slug="appium-tenant-c")
        other_project = Project.objects.create(
            tenant=other_tenant,
            name="其他租户在线项目",
            pm=self.user,
        )
        AppExecutionNode.objects.create(
            project=other_project,
            name="其他租户在线节点",
            enabled=True,
            status="online",
            last_seen_at=timezone.now(),
            created_by=self.user,
        )
        self.user.is_superuser = True
        self.user.is_staff = True
        self.user.save(update_fields=["is_superuser", "is_staff"])

        response = self.client.get(
            "/api/execution-control/tasks/overview/",
            HTTP_X_TENANT_ID=str(tenant.id),
        )

        self.assertEqual(response.status_code, 200)
        appium = next(item for item in response.data["services"] if item["key"] == "appium")
        self.assertEqual(appium["status"], "offline")
        self.assertEqual(appium["message"], "0/1 个启用节点在线")

    def test_terminal_source_and_report_are_deleted_from_unified_center(self):
        run = RunResult.objects.create(
            suite=self.suite, project=self.project, path="todo", environment_name="Test",
            status=RunResult.RunStatus.Done, is_pass=True, finished_at=timezone.now(),
        )
        task = ExecutionTask.objects.get(source_type="suite", source_id=run.id)
        response = self.client.delete(f"/api/execution-control/tasks/{task.id}/")
        self.assertEqual(response.status_code, 204)
        self.assertFalse(RunResult.objects.filter(pk=run.id).exists())
        self.assertFalse(ExecutionTask.objects.filter(pk=task.id).exists())

    def test_active_task_cannot_be_deleted_from_unified_center(self):
        run = RunResult.objects.create(
            suite=self.suite, project=self.project, path="todo", environment_name="Test",
            status=RunResult.RunStatus.Running,
        )
        task = ExecutionTask.objects.get(source_type="suite", source_id=run.id)
        response = self.client.delete(f"/api/execution-control/tasks/{task.id}/")
        self.assertEqual(response.status_code, 400)
        self.assertTrue(RunResult.objects.filter(pk=run.id).exists())

    @override_settings(Q_CLUSTER={"workers": 1})
    @patch("execution_control.dispatcher._enqueue_task")
    def test_dispatcher_uses_fifo_and_respects_worker_capacity(self, enqueue_task):
        now = timezone.now()
        first = ExecutionTask.objects.create(
            source_type="suite", source_id=3001, execution_no="3001", project=self.project,
            name="先提交", engine="pytest", status="queued", progress=0,
            last_activity_at=now, queued_at=now - timedelta(seconds=2),
            source_created_at=now, source_updated_at=now,
        )
        second = ExecutionTask.objects.create(
            source_type="suite", source_id=3002, execution_no="3002", project=self.project,
            name="后提交", engine="pytest", status="queued", progress=0,
            last_activity_at=now, queued_at=now - timedelta(seconds=1),
            source_created_at=now, source_updated_at=now,
        )

        self.assertEqual(dispatch_waiting_tasks(), 1)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertIsNotNone(first.dispatched_at)
        self.assertIsNone(second.dispatched_at)
        self.assertEqual(second.waiting_reason, "等待执行器空闲")
        enqueue_task.assert_called_once()
        self.assertEqual(enqueue_task.call_args.args[0].id, first.id)

    @override_settings(Q_CLUSTER={"workers": 1})
    @patch("execution_control.dispatcher._enqueue_task")
    def test_dispatched_offline_task_is_not_enqueued_twice(self, enqueue_task):
        now = timezone.now()
        task = ExecutionTask.objects.create(
            source_type="suite", source_id=3901, execution_no="3901", project=self.project,
            name="已进入持久化队列", engine="pytest", status="queued", progress=0,
            dispatched_at=now - timedelta(minutes=10), dispatch_attempts=1,
            last_activity_at=now - timedelta(minutes=10), queued_at=now - timedelta(minutes=10),
            source_created_at=now, source_updated_at=now,
        )

        self.assertEqual(dispatch_waiting_tasks(), 0)
        task.refresh_from_db()
        self.assertIsNotNone(task.dispatched_at)
        self.assertEqual(task.dispatch_attempts, 1)
        enqueue_task.assert_not_called()

    @override_settings(Q_CLUSTER={"workers": 2})
    @patch("execution_control.dispatcher._enqueue_task")
    def test_resource_blocked_queue_head_cannot_be_overtaken(self, enqueue_task):
        now = timezone.now()
        ExecutionTask.objects.create(
            source_type="app", source_id=4001, execution_no="4001", project=self.project,
            name="设备占用任务", engine="Appium", status="queued", progress=0,
            resource_keys=["app-device:99"], dispatched_at=now,
            last_activity_at=now, queued_at=now - timedelta(seconds=3),
            source_created_at=now, source_updated_at=now,
        )
        blocked = ExecutionTask.objects.create(
            source_type="app", source_id=4002, execution_no="4002", project=self.project,
            name="等待同一设备", engine="Appium", status="queued", progress=0,
            resource_keys=["app-device:99"],
            last_activity_at=now, queued_at=now - timedelta(seconds=2),
            source_created_at=now, source_updated_at=now,
        )
        later = ExecutionTask.objects.create(
            source_type="suite", source_id=4003, execution_no="4003", project=self.project,
            name="后来的接口任务", engine="pytest", status="queued", progress=0,
            last_activity_at=now, queued_at=now - timedelta(seconds=1),
            source_created_at=now, source_updated_at=now,
        )

        self.assertEqual(dispatch_waiting_tasks(), 0)
        blocked.refresh_from_db()
        later.refresh_from_db()
        self.assertIn("app-device:99", blocked.waiting_reason)
        self.assertIsNone(later.dispatched_at)
        enqueue_task.assert_not_called()
