from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from fullstack_framework.commons.api_executor import run_dynamic_function
from project.models import DatabaseConnection, DynamicFunction, Environment, Project, response_indicates_expired_token
from project.serializers import DynamicFunctionSerializer, EnvironmentSerializer


class EnvironmentTokenTtlTests(SimpleTestCase):
    def test_cache_validity_uses_refreshed_at_plus_configured_ttl(self):
        now = datetime(2026, 8, 21, 12, 0, 0)
        environment = Environment(
            cached_token="jwt-with-long-exp",
            token_ttl=1800,
            token_refreshed_at=now - timedelta(seconds=1799),
            token_expires_at=now + timedelta(days=7),
        )
        with patch("project.models.timezone.now", return_value=now):
            self.assertTrue(environment._cached_token_valid())
            environment.token_refreshed_at = now - timedelta(seconds=1800)
            self.assertFalse(environment._cached_token_valid())

    def test_expire_time_does_not_use_jwt_exp(self):
        refreshed_at = datetime(2026, 8, 21, 12, 0, 0)
        environment = Environment(token_ttl=1800)

        self.assertEqual(
            environment._token_expire_time(refreshed_at),
            refreshed_at + timedelta(seconds=1800),
        )


class ExpiredTokenResponseTests(SimpleTestCase):
    def test_recognizes_http_401(self):
        response = SimpleNamespace(status_code=401, json=lambda: {})
        self.assertTrue(response_indicates_expired_token(response))

    def test_recognizes_business_code_and_common_messages(self):
        for payload in (
            {"code": 1023, "msg": "jwt expired"},
            {"code": 401, "message": "authentication failed"},
            {"detail": "Token has expired"},
            {"message": "Unauthorized"},
        ):
            with self.subTest(payload=payload):
                response = SimpleNamespace(status_code=200, json=lambda payload=payload: payload)
                self.assertTrue(response_indicates_expired_token(response))

    def test_does_not_refresh_for_unrelated_failure(self):
        response = SimpleNamespace(status_code=403, json=lambda: {"message": "permission denied"})
        self.assertFalse(response_indicates_expired_token(response))


class EnvironmentSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="environment-owner")
        self.project_a = Project.objects.create(name="环境项目 A", intro="", pm=self.user)
        self.project_b = Project.objects.create(name="环境项目 B", intro="", pm=self.user)
        self.environment = Environment.objects.create(
            project=self.project_a,
            name="Dev",
            base_url="https://dev.example.com",
        )

    def test_existing_environment_can_change_project_and_name(self):
        serializer = EnvironmentSerializer(
            self.environment,
            data={
                "project": self.project_b.id,
                "name": "Test",
                "base_url": "https://test.example.com",
            },
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_duplicate_project_environment_name_is_rejected(self):
        Environment.objects.create(
            project=self.project_b,
            name="Test",
            base_url="https://existing.example.com",
        )
        serializer = EnvironmentSerializer(
            self.environment,
            data={"project": self.project_b.id, "name": "Test"},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_token_prefix_preserves_trailing_space(self):
        serializer = EnvironmentSerializer(
            self.environment,
            data={"token_prefix": "Bearer "},
            partial=True,
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        environment = serializer.save()
        environment.refresh_from_db()
        self.assertEqual(environment.token_prefix, "Bearer ")


class DynamicFunctionProjectTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dynamic-owner")
        self.project_a = Project.objects.create(name="项目 A", intro="", pm=self.user)
        self.project_b = Project.objects.create(name="项目 B", intro="", pm=self.user)

    def test_same_function_name_in_overlapping_project_is_rejected(self):
        existing = DynamicFunction.objects.create(code="def order_no():\n    return 'A'", enabled=True)
        existing.projects.add(self.project_a)

        serializer = DynamicFunctionSerializer(data={
            "projects": [self.project_a.id, self.project_b.id],
            "code": "def order_no():\n    return 'B'",
            "enabled": True,
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn("项目 A", str(serializer.errors["projects"][0]))

    def test_same_function_name_in_different_projects_is_allowed_and_isolated_at_runtime(self):
        first = DynamicFunction.objects.create(code="def project_value():\n    return 'A'", enabled=True)
        first.projects.add(self.project_a)
        second = DynamicFunction.objects.create(code="def project_value():\n    return 'B'", enabled=True)
        second.projects.add(self.project_b)

        self.assertEqual(run_dynamic_function("project_value", {}, project_id=self.project_a.id), "A")
        self.assertEqual(run_dynamic_function("project_value", {}, project_id=self.project_b.id), "B")


class SharedProjectConfigurationPermissionTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user(username="shared-member")
        self.other_owner = User.objects.create_user(username="shared-owner")
        self.project_a = Project.objects.create(name="项目 A", intro="", pm=self.member)
        self.project_b = Project.objects.create(name="项目 B", intro="", pm=self.other_owner)
        self.client = APIClient()
        self.client.force_authenticate(self.member)

    def test_member_of_only_one_project_cannot_modify_shared_dynamic_function(self):
        item = DynamicFunction.objects.create(code="def shared_value():\n    return 1", enabled=True)
        item.projects.add(self.project_a, self.project_b)

        response = self.client.patch(
            f"/api/project/dynamic-function/{item.id}/",
            {"enabled": False},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        item.refresh_from_db()
        self.assertTrue(item.enabled)

    def test_member_of_only_one_project_cannot_delete_shared_database_connection(self):
        connection = DatabaseConnection.objects.create(
            environment_name="Dev", database_type="mysql",
            function_name="execute_sql_shared", host="127.0.0.1", port=3306,
            database="demo", username="root",
        )
        connection.projects.add(self.project_a, self.project_b)

        response = self.client.delete(f"/api/project/database-connection/{connection.id}/")

        self.assertEqual(response.status_code, 403)
        self.assertTrue(DatabaseConnection.objects.filter(pk=connection.id).exists())
