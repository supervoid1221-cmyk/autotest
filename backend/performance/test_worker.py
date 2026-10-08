from django.contrib.auth.models import User
from django.test import TestCase

from account.models import Tenant
from execution_control.models import ExecutionTask
from project.models import Environment, Project

from .management.commands.performance_worker import _claim_next_run
from .models import PerformanceRun, PerformanceScenario


class PerformanceWorkerClaimTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("performance-worker-user")
        self.tenant = Tenant.objects.create(
            name="性能 Worker 租户",
            slug="performance-worker",
            max_regular_concurrent_executions=1,
            max_performance_concurrent_executions=2,
        )
        self.project = Project.objects.create(
            tenant=self.tenant, name="性能 Worker 项目", pm=self.user,
        )
        self.environment = Environment.objects.create(
            project=self.project, name="Dev", base_url="https://example.com",
        )
        self.scenario = PerformanceScenario.objects.create(
            tenant=self.tenant,
            project=self.project,
            environment=self.environment,
            name="并发领取场景",
            created_by=self.user,
        )

    def create_run(self):
        return PerformanceRun.objects.create(
            tenant=self.tenant,
            scenario=self.scenario,
            project=self.project,
            environment=self.environment,
            created_by=self.user,
        )

    def test_claims_up_to_tenant_performance_capacity(self):
        runs = [self.create_run() for _ in range(3)]

        first = _claim_next_run()
        second = _claim_next_run()
        blocked = _claim_next_run()

        self.assertEqual({first[0], second[0]}, {runs[0].id, runs[1].id})
        self.assertIsNone(blocked)
        self.assertEqual(
            PerformanceRun.objects.filter(status=PerformanceRun.Status.PREPARING).count(), 2,
        )
        runs[2].refresh_from_db()
        self.assertEqual(runs[2].status, PerformanceRun.Status.QUEUED)

    def test_claim_respects_tenant_performance_worker_capacity(self):
        self.tenant.max_performance_concurrent_executions = 1
        self.tenant.save(update_fields=["max_performance_concurrent_executions"])
        first_run = self.create_run()
        second_run = self.create_run()

        claimed = _claim_next_run()
        blocked = _claim_next_run()

        self.assertEqual(claimed[0], first_run.id)
        self.assertIsNone(blocked)
        second_run.refresh_from_db()
        self.assertEqual(second_run.status, PerformanceRun.Status.QUEUED)
        execution_task = ExecutionTask.objects.get(
            tenant=self.tenant,
            source_type=ExecutionTask.SourceType.PERFORMANCE,
            source_id=second_run.id,
        )
        self.assertEqual(
            execution_task.waiting_reason,
            "等待当前租户性能任务并发额度释放",
        )
