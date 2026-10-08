"""创建人 / 执行人快照的写入规则。

平台把「谁操作的」存成名称字符串而不是外键（RunResult.executor_name、
Suite.creator_name、ExecutionTask.executor_name）：用户改名或注销后，历史记录
仍要能显示当时的归属。这个文件锁住三条规则：

1. 归属字段由服务端写入，客户端提交的值一律忽略（否则有编辑权限的人就能改别人的归属）；
2. 从源任务同步时，套件取 RunResult.executor_name，App / 性能任务取 created_by 的显示名；
3. 取不到名字时保留库里的旧快照，不能把「张三执行过」抹成空值。

规则 3 是执行人列最容易回归的地方：created_by 是 SET_NULL，用户注销后外键变 None，
如果同步逻辑照着 None 写空串，快照就白存了。
"""

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from account.access import display_name
from case_app.models import (
    AppApplication, AppCase, AppDevice, AppExecutionNode, AppRun,
)
from execution_control.models import ExecutionTask
from execution_control.sync import _upsert
from project.models import Environment, Project
from suite.models import RunResult, Suite


class DisplayNameTests(TestCase):
    def test_full_name_wins_over_username(self):
        user = User.objects.create_user("zhangsan", first_name="张", last_name="三")
        # Django 的 get_full_name() 是 `f"{first_name} {last_name}"`，中文姓名中间会带一个空格。
        # 这里刻意锁住这个行为：西文姓名（John Smith）需要那个空格，
        # 要按语言去掉空格就得先知道姓名是哪种语言，不是这里能可靠判断的。
        self.assertEqual(display_name(user), "张 三")

    def test_username_is_the_fallback(self):
        user = User.objects.create_user("lisi")
        self.assertEqual(display_name(user), "lisi")

    def test_blank_full_name_does_not_produce_whitespace(self):
        user = User.objects.create_user("wangwu")
        user.first_name = "   "
        self.assertEqual(display_name(user), "wangwu")

    def test_missing_user_falls_back_to_system(self):
        self.assertEqual(display_name(None), "系统")
        # 需要区分「确实是系统发起」和「无从得知」的调用方可以传空串
        self.assertEqual(display_name(None, default=""), "")


class SuiteCreatorSnapshotTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user("creator-owner", first_name="李", last_name="四")
        self.expected_creator = display_name(self.member)
        self.project = Project.objects.create(name="归属项目", intro="", pm=self.member)
        self.environment = Environment.objects.create(
            project=self.project, name="Dev", base_url="https://creator.example.com",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.member)

    def test_create_writes_creator_from_request_user(self):
        response = self.client.post(
            "/api/suite/suite/",
            {"name": "归属校验计划", "environment": self.environment.id},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        suite = Suite.objects.get(name="归属校验计划")
        self.assertEqual(suite.creator_name, self.expected_creator)

    def test_client_supplied_creator_is_ignored(self):
        response = self.client.post(
            "/api/suite/suite/",
            {"name": "伪造创建人", "environment": self.environment.id, "creator_name": "别人"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Suite.objects.get(name="伪造创建人").creator_name, self.expected_creator)

    def test_edit_does_not_rewrite_creator(self):
        suite = Suite.objects.create(
            name="原计划", environment=self.environment, creator_name="原始创建者",
        )

        response = self.client.patch(
            f"/api/suite/suite/{suite.id}/",
            {"name": "改过名字的计划", "creator_name": "当前编辑者"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        suite.refresh_from_db()
        self.assertEqual(suite.name, "改过名字的计划")
        # 编辑是「执行人」语义，不该覆盖创建人
        self.assertEqual(suite.creator_name, "原始创建者")

    def test_historical_suite_without_creator_serializes_as_empty_string(self):
        """补字段之前的历史计划没有创建人，接口给空串，由前端渲染成「-」。"""
        suite = Suite.objects.create(name="历史计划", environment=self.environment)

        response = self.client.get(f"/api/suite/suite/{suite.id}/")

        self.assertEqual(response.status_code, 200)
        payload = response.data.get("result", response.data)
        self.assertEqual(payload["creator_name"], "")


class ExecutionTaskExecutorSnapshotTests(TestCase):
    def setUp(self):
        self.runner = User.objects.create_user("runner-one", first_name="王", last_name="五")
        self.expected_executor = display_name(self.runner)
        self.project = Project.objects.create(name="执行归属项目", intro="", pm=self.runner)
        self.environment = Environment.objects.create(
            project=self.project, name="Dev", base_url="https://runner.example.com",
        )
        self.suite = Suite.objects.create(name="执行归属套件", environment=self.environment)

    def test_suite_run_copies_executor_name(self):
        run = RunResult.objects.create(
            suite=self.suite, project=self.project, path="todo",
            environment_name="Dev", executor_name=self.expected_executor,
        )

        task = ExecutionTask.objects.get(source_type="suite", source_id=run.id)
        self.assertEqual(task.executor_name, self.expected_executor)

    def test_rerun_refreshes_executor_snapshot(self):
        """重新执行复用同一条 RunResult，执行人必须跟着更新，不能停在上一轮。"""
        run = RunResult.objects.create(
            suite=self.suite, project=self.project, path="todo",
            environment_name="Dev", executor_name=self.expected_executor,
        )
        task = ExecutionTask.objects.get(source_type="suite", source_id=run.id)

        run.executor_name = "赵六"
        run.save(update_fields=["executor_name", "update_datetime"])

        task.refresh_from_db()
        self.assertEqual(task.executor_name, "赵六")

    def test_empty_executor_does_not_wipe_previous_snapshot(self):
        """源记录取不到名字时保留旧快照（created_by 是 SET_NULL，注销后外键会变 None）。"""
        run = RunResult.objects.create(
            suite=self.suite, project=self.project, path="todo",
            environment_name="Dev", executor_name=self.expected_executor,
        )
        task = ExecutionTask.objects.get(source_type="suite", source_id=run.id)

        _upsert(
            source_type=ExecutionTask.SourceType.SUITE, source=run, execution_no=run.id,
            project=self.project, name=self.suite.name, engine="UI&API",
            status=ExecutionTask.Status.RUNNING, raw_status="running", progress=10,
            timeout_seconds=run.timeout_seconds, error_message="",
            created_at=run.create_datetime, updated_at=run.update_datetime,
            executor_name="",
        )

        task.refresh_from_db()
        self.assertEqual(task.executor_name, self.expected_executor)

    def test_app_run_uses_created_by_display_name(self):
        run = self._make_app_run(created_by=self.runner)

        task = ExecutionTask.objects.get(source_type="app", source_id=run.id)
        self.assertEqual(task.executor_name, self.expected_executor)

    def test_app_run_without_creator_stays_empty_for_dash_rendering(self):
        run = self._make_app_run(created_by=None)

        task = ExecutionTask.objects.get(source_type="app", source_id=run.id)
        # 空串而不是「系统」：历史数据没有归属信息时前端显示「-」，
        # 谎称是系统执行会让人以为真的有人（系统）跑过。
        self.assertEqual(task.executor_name, "")

    def _make_app_run(self, created_by):
        application = AppApplication.objects.create(
            project=self.project, name="归属 App", package_name="com.example.owner",
        )
        node = AppExecutionNode.objects.create(project=self.project, name="本地 Appium")
        device = AppDevice.objects.create(
            project=self.project, node=node, name="Pixel 5", udid="emulator-5556",
            state=AppDevice.State.ONLINE,
        )
        case = AppCase.objects.create(
            project=self.project, application=application, default_device=device, name="App 用例",
        )
        return AppRun.objects.create(
            tenant=self.project.tenant, case=case, project=self.project,
            application=application, device=device, status=AppRun.Status.QUEUED,
            created_by=created_by,
        )
