from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from account.models import Tenant
from fullstack_framework.commons.api_executor import run_dynamic_function
from project.database_functions import _validate_sql, test_database_query
from project.models import DatabaseConnection, DynamicFunction, DynamicFunctionRevision, Environment, Project, response_indicates_expired_token
from project.dynamic_functions import execute_dynamic_function, validate_dynamic_code, whitelist
from project.function_worker import run_request
from project.serializers import DatabaseConnectionSerializer, DynamicFunctionSerializer, EnvironmentSerializer


class DatabaseWriteSafetyTests(SimpleTestCase):
    def test_delete_requires_where_clause(self):
        with self.assertRaisesMessage(ValueError, "DELETE 必须包含 WHERE 条件"):
            _validate_sql("DELETE FROM orders")

    def test_delete_is_disabled_by_default(self):
        with self.assertRaisesMessage(ValueError, "未开启“允许执行 DELETE”"):
            test_database_query({}, "secret", "DELETE FROM orders WHERE id = 1", confirm_write=True)

    def test_delete_requires_explicit_confirmation(self):
        with self.assertRaisesMessage(ValueError, "需明确确认写入操作"):
            test_database_query(
                {"allow_delete": True}, "secret", "DELETE FROM orders WHERE id = 1"
            )

    @patch("project.database_functions._execute_write", return_value=1)
    def test_delete_executes_when_all_safety_checks_pass(self, execute_write):
        result = test_database_query(
            {"allow_delete": True},
            "secret",
            "DELETE FROM orders WHERE id = 1",
            confirm_write=True,
        )

        self.assertEqual(result["operation"], "delete")
        self.assertEqual(result["affected_rows"], 1)
        execute_write.assert_called_once_with(
            {"allow_delete": True}, "secret", "DELETE FROM orders WHERE id = 1"
        )


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
        first = DynamicFunction.objects.create(code="def project_value():\n    return 'A'", enabled=True, approval_status=DynamicFunction.ApprovalStatus.APPROVED)
        first.projects.add(self.project_a)
        second = DynamicFunction.objects.create(code="def project_value():\n    return 'B'", enabled=True, approval_status=DynamicFunction.ApprovalStatus.APPROVED)
        second.projects.add(self.project_b)

        self.assertEqual(run_dynamic_function("project_value", {}, project_id=self.project_a.id), "A")
        self.assertEqual(run_dynamic_function("project_value", {}, project_id=self.project_b.id), "B")

    def test_runtime_rejects_object_introspection(self):
        with self.assertRaisesRegex(ValueError, "下划线开头"):
            validate_dynamic_code("def escape():\n    return ().__class__.__base__.__subclasses__()")

    def test_function_runs_in_isolated_subprocess(self):
        result = execute_dynamic_function(
            ["def build(context):\n    return {'value': context['variables']['value'] + 1}"],
            "build", {"value": 2}, timeout_seconds=2, memory_mb=128,
        )
        self.assertEqual(result, {"value": 3})

    def test_function_accepts_arguments_and_optional_platform_context(self):
        plain = execute_dynamic_function(
            ["def amount_boundary(left, right):\n    return [left, right]"],
            "amount_boundary", args=("0.01", "9999.99"), timeout_seconds=2, memory_mb=128,
        )
        contextual = execute_dynamic_function(
            ["def prefixed(context, value):\n    return str(context['variables']['prefix']) + value"],
            "prefixed", {"prefix": "TEST-"}, args=("001",), timeout_seconds=2, memory_mb=128,
        )
        self.assertEqual(plain, ["0.01", "9999.99"])
        self.assertEqual(contextual, "TEST-001")

    def test_isinstance_and_hexdigest_are_allowed(self):
        result = execute_dynamic_function(
            [
                "import hashlib\n"
                "def digest(value):\n"
                "    if not isinstance(value, str):\n"
                "        value = str(value)\n"
                "    return hashlib.sha256(value.encode('utf-8')).hexdigest()"
            ],
            "digest",
            args=(123,),
            timeout_seconds=2,
            memory_mb=128,
        )

        self.assertEqual(
            result,
            "a665a45920422f9d417e4867efdc4fb8a04a1f3fff1fa07e998e86f7f7a27ae3",
        )
        self.assertIn("isinstance", whitelist()["builtins"])
        self.assertIn("hexdigest", whitelist()["builtins"])

    def test_infinite_loop_is_terminated_by_timeout(self):
        result = run_request({
            "codes": ["def never_returns():\n    while True:\n        pass"],
            "name": "never_returns", "timeout_seconds": 1, "memory_mb": 128,
        })
        self.assertFalse(result["ok"])
        self.assertIn("已终止", result["error"])

    def test_non_json_result_is_rejected(self):
        result = run_request({
            "codes": ["def unsupported_result():\n    return {1, 2}"],
            "name": "unsupported_result", "timeout_seconds": 2, "memory_mb": 128,
        })
        self.assertFalse(result["ok"])
        self.assertIn("可序列化的 JSON", result["error"])

    @override_settings(
        DYNAMIC_FUNCTION_SOCKET="/tmp/non-existent-dynamic-function-worker.sock",
        DYNAMIC_FUNCTION_ALLOW_LOCAL_FALLBACK=False,
    )
    def test_missing_worker_is_rejected_when_fallback_is_disabled(self):
        with self.assertRaisesRegex(ValueError, "执行器不可用"):
            execute_dynamic_function(["def value():\n    return 1"], "value")

    def test_new_function_requires_admin_approval_and_keeps_revision(self):
        member_client = APIClient(); member_client.force_authenticate(self.user)
        response = member_client.post("/api/project/dynamic-function/", {
            "projects": [self.project_a.id], "code": "def approved_value():\n    return 'v1'",
            "enabled": True, "timeout_seconds": 2, "memory_mb": 128,
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        item = DynamicFunction.objects.get(pk=response.data["id"])
        self.assertEqual(item.approval_status, DynamicFunction.ApprovalStatus.DRAFT)
        with self.assertRaisesRegex(ValueError, "未配置可用"):
            run_dynamic_function("approved_value", {}, project_id=self.project_a.id)

        admin = User.objects.create_superuser("dynamic-admin", "admin@example.com", "password")
        admin_client = APIClient(); admin_client.force_authenticate(admin)
        approved = admin_client.post(f"/api/project/dynamic-function/{item.id}/approve/", {}, format="json")
        self.assertEqual(approved.status_code, 200, approved.data)
        revision = DynamicFunctionRevision.objects.get(dynamic_function=item, version=1)
        self.assertEqual(revision.code_hash, approved.data["code_hash"])
        self.assertEqual(run_dynamic_function("approved_value", {}, project_id=self.project_a.id), "v1")

        changed = member_client.patch(f"/api/project/dynamic-function/{item.id}/", {
            "code": "def approved_value():\n    return 'v2'",
        }, format="json")
        self.assertEqual(changed.status_code, 200, changed.data)
        item.refresh_from_db()
        self.assertEqual(item.version, 2)
        self.assertEqual(item.approval_status, DynamicFunction.ApprovalStatus.DRAFT)
        self.assertEqual(DynamicFunctionRevision.objects.filter(dynamic_function=item).count(), 1)

    def test_execution_policy_change_requires_a_new_approval_version(self):
        item = DynamicFunction.objects.create(
            code="def policy_value():\n    return 1", enabled=True,
            approval_status=DynamicFunction.ApprovalStatus.APPROVED,
            timeout_seconds=2, memory_mb=128,
        )
        item.projects.add(self.project_a)
        member_client = APIClient(); member_client.force_authenticate(self.user)

        changed = member_client.patch(
            f"/api/project/dynamic-function/{item.id}/",
            {"timeout_seconds": 4, "memory_mb": 256}, format="json",
        )

        self.assertEqual(changed.status_code, 200, changed.data)
        item.refresh_from_db()
        self.assertEqual(item.version, 2)
        self.assertEqual(item.approval_status, DynamicFunction.ApprovalStatus.DRAFT)

    def test_non_admin_cannot_approve_or_reject(self):
        item = DynamicFunction.objects.create(
            code="def pending_value():\n    return 1", enabled=True,
            approval_status=DynamicFunction.ApprovalStatus.DRAFT,
        )
        item.projects.add(self.project_a)
        client = APIClient(); client.force_authenticate(self.user)

        for action in ("approve", "reject"):
            with self.subTest(action=action):
                response = client.post(
                    f"/api/project/dynamic-function/{item.id}/{action}/", {}, format="json"
                )
                self.assertEqual(response.status_code, 403, response.data)

    def test_admin_can_reject_and_approval_revisions_are_unique_per_version(self):
        item = DynamicFunction.objects.create(
            code="def reviewed_value():\n    return 1", enabled=True,
            approval_status=DynamicFunction.ApprovalStatus.DRAFT,
        )
        item.projects.add(self.project_a)
        admin = User.objects.create_superuser("review-admin", "review@example.com", "password")
        client = APIClient(); client.force_authenticate(admin)

        rejected = client.post(f"/api/project/dynamic-function/{item.id}/reject/", {}, format="json")
        self.assertEqual(rejected.status_code, 200, rejected.data)
        self.assertEqual(rejected.data["approval_status"], DynamicFunction.ApprovalStatus.REJECTED)

        first = client.post(f"/api/project/dynamic-function/{item.id}/approve/", {}, format="json")
        second = client.post(f"/api/project/dynamic-function/{item.id}/approve/", {}, format="json")
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(
            DynamicFunctionRevision.objects.filter(dynamic_function=item, version=1).count(), 1
        )


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


class ProjectConfigurationTenantIsolationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            "tenant-isolation-admin", "tenant-admin@example.com", "password"
        )
        self.tenant_a = Tenant.objects.create(name="配置租户 A", slug="config-tenant-a")
        self.tenant_b = Tenant.objects.create(name="配置租户 B", slug="config-tenant-b")
        self.project_a = Project.objects.create(
            tenant=self.tenant_a, name="配置项目 A", pm=self.admin
        )
        self.project_b = Project.objects.create(
            tenant=self.tenant_b, name="配置项目 B", pm=self.admin
        )
        self.environment_a = Environment.objects.create(
            project=self.project_a, name="Dev", base_url="https://a.example.com"
        )
        self.environment_b = Environment.objects.create(
            project=self.project_b, name="Dev", base_url="https://b.example.com"
        )
        self.function_a = DynamicFunction.objects.create(code="def tenant_a():\n    return 'a'")
        self.function_a.projects.add(self.project_a)
        self.function_b = DynamicFunction.objects.create(code="def tenant_b():\n    return 'b'")
        self.function_b.projects.add(self.project_b)
        self.connection_a = self._create_connection("execute_sql_tenant_a", self.project_a)
        self.connection_b = self._create_connection("execute_sql_tenant_b", self.project_b)
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    @staticmethod
    def _create_connection(function_name, project):
        connection = DatabaseConnection.objects.create(
            environment_name="Dev",
            database_type="mysql",
            function_name=function_name,
            host="127.0.0.1",
            port=3306,
            database="demo",
            username="root",
        )
        connection.projects.add(project)
        return connection

    def _tenant_get(self, path):
        return self.client.get(path, HTTP_X_TENANT_ID=str(self.tenant_a.id))

    def test_lists_only_return_selected_tenant_configuration(self):
        cases = (
            ("/api/project/environment/", self.environment_a.id),
            ("/api/project/dynamic-function/", self.function_a.id),
            ("/api/project/database-connection/", self.connection_a.id),
        )
        for path, expected_id in cases:
            with self.subTest(path=path):
                response = self._tenant_get(path)
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual([item["id"] for item in response.data], [expected_id])

    def test_other_tenant_configuration_detail_is_not_found(self):
        paths = (
            f"/api/project/environment/{self.environment_b.id}/",
            f"/api/project/dynamic-function/{self.function_b.id}/",
            f"/api/project/database-connection/{self.connection_b.id}/",
        )
        for path in paths:
            with self.subTest(path=path):
                response = self._tenant_get(path)
                self.assertEqual(response.status_code, 404, response.data)

    def test_cross_tenant_projects_cannot_be_attached_on_create(self):
        cases = (
            ("/api/project/environment/", {
                "project": self.project_b.id,
                "name": "Test",
                "base_url": "https://cross.example.com",
            }),
            ("/api/project/dynamic-function/", {
                "projects": [self.project_b.id],
                "code": "def cross_tenant():\n    return True",
                "enabled": True,
            }),
            ("/api/project/database-connection/", {
                "projects": [self.project_b.id],
                "environment_name": "Test",
                "database_type": "mysql",
                "function_name": "execute_sql_cross_tenant",
                "host": "127.0.0.1",
                "port": 3306,
                "database": "demo",
                "username": "root",
                "enabled": True,
            }),
        )
        for path, payload in cases:
            with self.subTest(path=path):
                response = self.client.post(
                    path,
                    payload,
                    format="json",
                    HTTP_X_TENANT_ID=str(self.tenant_a.id),
                )
                self.assertEqual(response.status_code, 400, response.data)

    def test_mixed_tenant_shared_records_are_not_exposed(self):
        mixed_function = DynamicFunction.objects.create(code="def mixed():\n    return True")
        mixed_function.projects.add(self.project_a, self.project_b)
        mixed_connection = self._create_connection("execute_sql_mixed", self.project_a)
        mixed_connection.projects.add(self.project_b)

        function_response = self._tenant_get("/api/project/dynamic-function/")
        connection_response = self._tenant_get("/api/project/database-connection/")

        self.assertNotIn(mixed_function.id, [item["id"] for item in function_response.data])
        self.assertNotIn(mixed_connection.id, [item["id"] for item in connection_response.data])


class DatabaseConnectionSshTunnelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="ssh-database-owner")
        self.project = Project.objects.create(name="SSH 数据库项目", pm=self.owner)

    def base_payload(self):
        return {
            "projects": [self.project.id], "environment_name": "Test",
            "database_type": "mysql", "function_name": "execute_sql_mysql",
            "host": "127.0.0.1", "port": 3306, "database": "test_platform",
            "username": "test_platform", "password": "secret", "ssl_mode": "disabled",
            "connect_timeout": 10, "allow_write": False, "enabled": True,
        }

    def test_direct_connection_does_not_require_ssh_fields(self):
        serializer = DatabaseConnectionSerializer(data=self.base_payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_tunnel_requires_host_user_and_private_key_path(self):
        serializer = DatabaseConnectionSerializer(data={
            **self.base_payload(), "use_ssh_tunnel": True,
        })
        self.assertFalse(serializer.is_valid())
        self.assertEqual(
            set(serializer.errors),
            {"ssh_host", "ssh_username", "ssh_private_key_path"},
        )

    def test_private_key_passphrase_is_not_returned(self):
        connection = DatabaseConnection.objects.create(
            environment_name="Test", database_type="mysql",
            function_name="execute_sql_mysql", host="127.0.0.1", port=3306,
            database="test_platform", username="test_platform", use_ssh_tunnel=True,
            ssh_host="47.103.158.1", ssh_username="deployer",
            ssh_private_key_path="/run/secrets/database_ssh_key",
            ssh_private_key_passphrase="private-passphrase",
        )
        connection.projects.add(self.project)
        data = DatabaseConnectionSerializer(connection).data
        self.assertNotIn("ssh_private_key_passphrase", data)
        self.assertTrue(data["ssh_private_key_passphrase_configured"])
