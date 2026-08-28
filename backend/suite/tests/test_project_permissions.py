from unittest.mock import patch

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import TestCase
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
