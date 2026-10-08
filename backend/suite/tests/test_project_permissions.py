from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.http import HttpResponse
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from case_api.models import Scenario
from project.models import Environment, Project
from suite.models import (
    NotificationChannel, NotificationDelivery, NotificationRule, RunResult, Suite,
    SuiteScenario,
)


class SuiteProjectPermissionTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user("suite-member")
        self.other_owner = User.objects.create_user("suite-owner")
        self.project_a = Project.objects.create(name="套件项目 A", intro="", pm=self.member)
        self.project_b = Project.objects.create(name="套件项目 B", intro="", pm=self.other_owner)
        self.environment_a = Environment.objects.create(
            project=self.project_a, name="Dev", base_url="https://a.example.com",
        )
        self.environment_b = Environment.objects.create(
            project=self.project_b, name="Dev", base_url="https://b.example.com",
        )
        self.suite_a = Suite.objects.create(name="套件 A", environment=self.environment_a)
        self.suite_b = Suite.objects.create(name="套件 B", environment=self.environment_b)
        self.channel = NotificationChannel.objects.create(
            name="共享渠道", platform="lark", webhook_url="https://example.com/webhook",
        )
        self.channel.projects.add(self.project_a, self.project_b)
        self.client = APIClient()
        self.client.force_authenticate(self.member)

    @staticmethod
    def response_items(response):
        if not isinstance(response.data, dict):
            return response.data
        return response.data.get("list", response.data.get("results", []))

    def test_suite_and_result_lists_filter_by_any_related_project(self):
        self.project_b.user_list.add(self.member)
        scenario_b = Scenario.objects.create(
            project=self.project_b,
            created_by=self.other_owner,
            name="跨项目筛选场景",
        )
        scenario_b.projects.add(self.project_b)
        SuiteScenario.objects.create(suite=self.suite_a, scenario=scenario_b, order=1)
        result_a = RunResult.objects.create(
            suite=self.suite_a,
            project=self.project_a,
            path="upload_yaml/project-filter-result",
        )

        suite_response = self.client.get(f"/api/suite/suite/?project={self.project_b.id}")
        result_response = self.client.get(f"/api/suite/run_result/?project={self.project_b.id}")

        self.assertEqual(suite_response.status_code, 200)
        self.assertEqual(result_response.status_code, 200)
        self.assertIn(self.suite_a.id, [item["id"] for item in self.response_items(suite_response)])
        self.assertIn(result_a.id, [item["id"] for item in self.response_items(result_response)])

    def test_invalid_project_filter_returns_empty_lists(self):
        suite_response = self.client.get("/api/suite/suite/?project=invalid")
        result_response = self.client.get("/api/suite/run_result/?project=invalid")

        self.assertEqual(self.response_items(suite_response), [])
        self.assertEqual(self.response_items(result_response), [])

    def test_result_list_project_names_do_not_add_queries_per_row(self):
        RunResult.objects.create(
            suite=self.suite_a, project=self.project_a, path="upload_yaml/query-count-1",
        )
        # 先预热鉴权和渲染器中的惰加载状态，只比较列表数量带来的查询变化。
        self.client.get("/api/suite/run_result/?pageSize=100")
        with CaptureQueriesContext(connection) as one_result_queries:
            response = self.client.get("/api/suite/run_result/?pageSize=100")
        self.assertEqual(response.status_code, 200)

        for index in range(2, 8):
            RunResult.objects.create(
                suite=self.suite_a,
                project=self.project_a,
                path=f"upload_yaml/query-count-{index}",
            )
        with CaptureQueriesContext(connection) as many_result_queries:
            response = self.client.get("/api/suite/run_result/?pageSize=100")

        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(many_result_queries), len(one_result_queries) + 1)
        for item in self.response_items(response):
            self.assertEqual(item["project_name"], item["project_names"])

    def test_notification_rule_cannot_use_shared_channel_without_all_project_access(self):
        response = self.client.post(
            "/api/suite/notification-rule/",
            {
                "channel": self.channel.id,
                "suite": self.suite_a.id,
                "event": "all",
                "enabled": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(NotificationRule.objects.exists())

    def test_delivery_visibility_is_based_on_result_project(self):
        result_b = RunResult.objects.create(
            suite=self.suite_b, project=self.project_b, path="upload_yaml/private-result",
        )
        rule = NotificationRule.objects.create(channel=self.channel, suite=self.suite_b, event="all")
        delivery = NotificationDelivery.objects.create(
            result=result_b, channel=self.channel, rule=rule, event="failed", status="failed",
        )

        response = self.client.get("/api/suite/notification-delivery/")

        self.assertEqual(response.status_code, 200)
        items = response.data.get("list", []) if isinstance(response.data, dict) else response.data
        self.assertNotIn(delivery.id, [item["id"] for item in items])

    def test_suite_with_inaccessible_cross_project_scenario_is_hidden(self):
        scenario_b = Scenario.objects.create(
            project=self.project_b,
            created_by=self.other_owner,
            name="B 项目私有场景",
        )
        scenario_b.projects.add(self.project_b)
        SuiteScenario.objects.create(suite=self.suite_a, scenario=scenario_b, order=1)

        list_response = self.client.get("/api/suite/suite/")
        detail_response = self.client.get(f"/api/suite/suite/{self.suite_a.id}/")

        self.assertEqual(list_response.status_code, 200)
        items = (
            list_response.data.get("list", [])
            if isinstance(list_response.data, dict)
            else list_response.data
        )
        self.assertNotIn(self.suite_a.id, [item["id"] for item in items])
        self.assertEqual(detail_response.status_code, 404)

        self.project_b.user_list.add(self.member)
        visible_response = self.client.get(f"/api/suite/suite/{self.suite_a.id}/")
        self.assertEqual(visible_response.status_code, 200)

    def test_result_of_cross_project_suite_is_hidden(self):
        scenario_b = Scenario.objects.create(
            project=self.project_b,
            created_by=self.other_owner,
            name="B 项目执行场景",
        )
        scenario_b.projects.add(self.project_b)
        SuiteScenario.objects.create(suite=self.suite_a, scenario=scenario_b, order=1)
        result = RunResult.objects.create(
            suite=self.suite_a,
            project=self.project_a,
            path="upload_yaml/cross-project-result",
        )

        response = self.client.get(f"/api/suite/run_result/{result.id}/")

        self.assertEqual(response.status_code, 404)

    def test_execution_log_is_visible_without_cross_project_report_access(self):
        scenario_b = Scenario.objects.create(
            project=self.project_b,
            created_by=self.other_owner,
            name="跨项目实时日志场景",
        )
        scenario_b.projects.add(self.project_b)
        SuiteScenario.objects.create(suite=self.suite_a, scenario=scenario_b, order=1)
        result = RunResult.objects.create(
            suite=self.suite_a,
            project=self.project_a,
            path="upload_yaml/project-member-progress",
        )

        detail_response = self.client.get(f"/api/suite/run_result/{result.id}/")
        progress_response = self.client.get(f"/api/suite/run_result/{result.id}/progress/")
        log_response = self.client.get(f"/api/suite/run_result/{result.id}/execution-log/")

        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(progress_response.status_code, 404)
        self.assertEqual(log_response.status_code, 200)
        self.assertEqual(log_response.data["result"]["id"], result.id)
        self.assertFalse(log_response.data["can_view_report"])
        self.assertNotIn("native_report", log_response.data["result"])

    def test_execution_log_is_hidden_without_result_project_access(self):
        result = RunResult.objects.create(
            suite=self.suite_b,
            project=self.project_b,
            path="upload_yaml/private-progress",
        )

        response = self.client.get(f"/api/suite/run_result/{result.id}/execution-log/")

        self.assertEqual(response.status_code, 404)

    def test_execution_log_reports_full_report_access(self):
        result = RunResult.objects.create(
            suite=self.suite_a,
            project=self.project_a,
            path="upload_yaml/visible-progress",
        )

        progress_response = self.client.get(f"/api/suite/run_result/{result.id}/progress/")
        log_response = self.client.get(f"/api/suite/run_result/{result.id}/execution-log/")

        self.assertEqual(progress_response.status_code, 200)
        self.assertEqual(log_response.status_code, 200)
        self.assertTrue(log_response.data["can_view_report"])

    @patch("suite.views.serve", return_value=HttpResponse("private"))
    def test_static_report_file_requires_result_project_access(self, serve):
        RunResult.objects.create(
            suite=self.suite_b,
            project=self.project_b,
            path="upload_yaml/private-result",
        )

        response = self.client.get("/api/suite/static/private-result/logs/pytest.log")

        self.assertEqual(response.status_code, 404)
        serve.assert_not_called()

    @patch("suite.views.serve", return_value=HttpResponse("visible"))
    def test_static_report_file_is_served_for_accessible_project(self, serve):
        RunResult.objects.create(
            suite=self.suite_a,
            project=self.project_a,
            path="upload_yaml/visible-result",
        )

        response = self.client.get("/api/suite/static/visible-result/logs/pytest.log")

        self.assertEqual(response.status_code, 200)
        serve.assert_called_once()
