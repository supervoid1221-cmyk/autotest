from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from case_api.models import Scenario
from execution_control.models import ExecutionTask
from project.models import Environment, Project
from suite.models import RunResult, Suite

from .models import Tenant, TenantMembership


class CoreTenantIsolationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser("phase2-admin", "admin@example.com", "password")
        self.tenant_a = Tenant.objects.create(name="核心租户 A", slug="core-a")
        self.tenant_b = Tenant.objects.create(name="核心租户 B", slug="core-b")
        TenantMembership.objects.create(tenant=self.tenant_a, user=self.admin)
        TenantMembership.objects.create(tenant=self.tenant_b, user=self.admin)
        self.project_a = Project.objects.create(tenant=self.tenant_a, name="核心项目 A", pm=self.admin)
        self.project_b = Project.objects.create(tenant=self.tenant_b, name="核心项目 B", pm=self.admin)
        self.environment_a = Environment.objects.create(
            project=self.project_a, name="Dev", base_url="https://a.example.com",
        )
        self.environment_b = Environment.objects.create(
            project=self.project_b, name="Dev", base_url="https://b.example.com",
        )
        self.scenario_a = Scenario.objects.create(
            tenant=self.tenant_a, project=self.project_a, name="A 场景", created_by=self.admin,
        )
        self.scenario_a.projects.add(self.project_a)
        self.scenario_b = Scenario.objects.create(
            tenant=self.tenant_b, project=self.project_b, name="B 场景", created_by=self.admin,
        )
        self.scenario_b.projects.add(self.project_b)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    @staticmethod
    def items(response):
        if isinstance(response.data, dict):
            return response.data.get("list", response.data.get("results", []))
        return response.data

    def test_platform_admin_only_sees_selected_tenant_core_data(self):
        response = self.client.get(
            "/api/case_api/scenario/", HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["id"] for item in self.items(response)], [self.scenario_a.id])

    def test_core_creation_uses_selected_tenant_and_rejects_cross_tenant_relation(self):
        created = self.client.post(
            "/api/case_api/scenario/",
            {"name": "新场景", "description": "", "projects": [self.project_a.id]},
            format="json", HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )
        rejected = self.client.post(
            "/api/case_api/scenario/",
            {"name": "跨租户场景", "description": "", "projects": [self.project_b.id]},
            format="json", HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(Scenario.objects.get(pk=created.data["id"]).tenant_id, self.tenant_a.id)
        self.assertEqual(rejected.status_code, 400, rejected.data)

    def test_execution_records_and_tasks_do_not_cross_tenants(self):
        suite_a = Suite.objects.create(
            tenant=self.tenant_a, name="A 套件", environment=self.environment_a,
        )
        suite_b = Suite.objects.create(
            tenant=self.tenant_b, name="B 套件", environment=self.environment_b,
        )
        run_a = RunResult.objects.create(
            tenant=self.tenant_a, suite=suite_a, project=self.project_a,
            path="upload_yaml/a", status=RunResult.RunStatus.Done,
            finished_at=timezone.now(),
        )
        run_b = RunResult.objects.create(
            tenant=self.tenant_b, suite=suite_b, project=self.project_b,
            path="upload_yaml/b", status=RunResult.RunStatus.Done,
            finished_at=timezone.now(),
        )

        results = self.client.get(
            "/api/suite/run_result/", HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )
        tasks = self.client.get(
            "/api/execution-control/tasks/", HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        self.assertEqual([item["id"] for item in self.items(results)], [run_a.id])
        task_sources = [item["source_id"] for item in self.items(tasks)]
        self.assertIn(run_a.id, task_sources)
        self.assertNotIn(run_b.id, task_sources)
        self.assertEqual(
            ExecutionTask.objects.get(source_type="suite", source_id=run_a.id).tenant_id,
            self.tenant_a.id,
        )
