from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from datetime import timedelta
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from types import SimpleNamespace
import tempfile
import json
from pathlib import Path

from project.models import Project
from account.tenant_runtime import ensure_tenant_storage_capacity, tenant_path, tenant_storage_usage

from .models import Profile, Tenant, TenantMembership
from .authentication import platform_token_expires_at


def join_login_tenant(user, *, tenant_status=Tenant.Status.ACTIVE, membership_status=TenantMembership.Status.ACTIVE):
    tenant = Tenant.objects.create(name="登录租户", slug="login-tenant", status=tenant_status)
    return TenantMembership.objects.create(
        tenant=tenant,
        user=user,
        status=membership_status,
    )


def test_login(user, api_client):
    join_login_tenant(user)
    resp = api_client.post(
        "/api/account/profile/login/",
        {
            "username": "test_user",
            "password": "test_user_pass",
        },
        format="json",
    )

    assert resp.status_code == 200, resp.status_code
    assert resp.data["token"]
    expires_at = resp.data["token_expires_at"]
    assert expires_at
    remaining = timezone.datetime.fromisoformat(str(expires_at)) - timezone.now()
    assert timedelta(minutes=59) < remaining <= timedelta(hours=1)


def test_login_rotates_existing_token(user, api_client):
    join_login_tenant(user)
    old_token = Token.objects.create(user=user)

    resp = api_client.post(
        "/api/account/profile/login/",
        {"username": "test_user", "password": "test_user_pass"},
        format="json",
    )

    assert resp.status_code == 200, resp.data
    assert resp.data["token"] != old_token.key
    assert not Token.objects.filter(key=old_token.key).exists()


def test_expired_platform_token_is_rejected(user, api_client):
    token = Token.objects.create(user=user)
    Token.objects.filter(pk=token.pk).update(created=timezone.now() - timedelta(hours=1, seconds=1))
    api_client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    resp = api_client.get("/api/account/profile/profile/")

    assert resp.status_code == 401, resp.data
    assert "已过期" in str(resp.data)


def test_login_ignores_stale_token(user, api_client):
    join_login_tenant(user)
    api_client.credentials(HTTP_AUTHORIZATION="Token stale-token-from-browser")

    resp = api_client.post(
        "/api/account/profile/login/",
        {
            "username": "test_user",
            "password": "test_user_pass",
        },
        format="json",
    )

    assert resp.status_code == 200, resp.data


def test_login_rejects_user_without_tenant(user, api_client):
    resp = api_client.post(
        "/api/account/profile/login/",
        {"username": "test_user", "password": "test_user_pass"},
        format="json",
    )

    assert resp.status_code == 400, resp.data
    assert "未加入可用租户" in str(resp.data["msg"][0])


def test_login_rejects_disabled_tenant_membership(user, api_client):
    join_login_tenant(user, membership_status=TenantMembership.Status.DISABLED)

    resp = api_client.post(
        "/api/account/profile/login/",
        {"username": "test_user", "password": "test_user_pass"},
        format="json",
    )

    assert resp.status_code == 400, resp.data
    assert "未加入可用租户" in str(resp.data["msg"][0])


def test_login_rejects_membership_in_suspended_tenant(user, api_client):
    join_login_tenant(user, tenant_status=Tenant.Status.SUSPENDED)

    resp = api_client.post(
        "/api/account/profile/login/",
        {"username": "test_user", "password": "test_user_pass"},
        format="json",
    )

    assert resp.status_code == 400, resp.data
    assert "未加入可用租户" in str(resp.data["msg"][0])


def test_platform_admin_can_login_without_tenant(api_client, django_user_model):
    django_user_model.objects.create_superuser(
        username="login-platform-admin",
        email="login-platform-admin@example.com",
        password="admin-password",
    )

    resp = api_client.post(
        "/api/account/profile/login/",
        {"username": "login-platform-admin", "password": "admin-password"},
        format="json",
    )

    assert resp.status_code == 200, resp.data


def test_reset_password(user: User, user_api_client):
    join_login_tenant(user)
    resp = user_api_client.post(
        "/api/account/profile/reset_password/",
        {
            "new_password": "1234567",
            "confirm_password": "1234567",
        },
        format="json",
    )

    assert resp.status_code == 204, resp.status_code

    # 通过数据库方式验证新密码
    user.refresh_from_db()  # 加载新数据内容
    assert user.check_password("1234567")

    # 通过接口的方式验证新密码
    user_api_client.logout()  # 退出登录
    resp = user_api_client.post(
        "/api/account/profile/login/",
        {  # 尝试重新登录
            "username": "test_user",
            "password": "1234567",
        },
        format="json",
    )

    assert resp.status_code == 200, resp.status_code


def test_api_401(api_client):
    resp = api_client.get("/api/account/profile/profile/")

    assert resp.status_code == 401, resp.status_code


def test_get_profile(user_api_client, user):
    resp = user_api_client.get("/api/account/profile/profile/")

    assert resp.status_code == 200, resp.status_code

    assert resp.data["user"] == user.id


class TenantLoginAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="login-member",
            password="login-password",
        )
        self.client = APIClient()

    def login(self):
        return self.client.post(
            "/api/account/profile/login/",
            {"username": "login-member", "password": "login-password"},
            format="json",
        )

    def test_user_without_tenant_cannot_login(self):
        response = self.login()

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("未加入可用租户", str(response.data["msg"][0]))

    def test_user_with_active_membership_in_active_tenant_can_login(self):
        join_login_tenant(self.user)

        response = self.login()

        self.assertEqual(response.status_code, 200, response.data)

    def test_disabled_membership_cannot_login(self):
        join_login_tenant(self.user, membership_status=TenantMembership.Status.DISABLED)

        response = self.login()

        self.assertEqual(response.status_code, 400, response.data)

    def test_suspended_tenant_member_cannot_login(self):
        join_login_tenant(self.user, tenant_status=Tenant.Status.SUSPENDED)

        response = self.login()

        self.assertEqual(response.status_code, 400, response.data)

    def test_platform_admin_without_tenant_can_login(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])

        response = self.login()

        self.assertEqual(response.status_code, 200, response.data)


class PlatformTokenExpiryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="token-session-user",
            password="token-session-password",
        )
        join_login_tenant(self.user)
        self.client = APIClient()

    def login(self):
        return self.client.post(
            "/api/account/profile/login/",
            {"username": "token-session-user", "password": "token-session-password"},
            format="json",
        )

    def test_login_returns_one_hour_expiry(self):
        response = self.login()

        self.assertEqual(response.status_code, 200, response.data)
        token = Token.objects.get(user=self.user)
        expected = platform_token_expires_at(token)
        if timezone.is_naive(expected):
            expected = timezone.make_aware(expected, timezone.get_current_timezone())
        self.assertEqual(response.data["token_expires_at"], expected.isoformat())
        self.assertEqual(platform_token_expires_at(token) - token.created, timedelta(hours=1))

    def test_relogin_rotates_existing_token(self):
        old_token = Token.objects.create(user=self.user)

        response = self.login()

        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotEqual(response.data["token"], old_token.key)
        self.assertFalse(Token.objects.filter(key=old_token.key).exists())

    def test_expired_token_is_rejected(self):
        token = Token.objects.create(user=self.user)
        Token.objects.filter(pk=token.pk).update(
            created=timezone.now() - timedelta(hours=1, seconds=1)
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.get("/api/account/profile/profile/")

        self.assertEqual(response.status_code, 401, response.data)
        self.assertIn("已过期", str(response.data))

    def test_active_session_can_be_renewed(self):
        self.login()
        token = Token.objects.get(user=self.user)
        old_created = timezone.now() - timedelta(minutes=45)
        Token.objects.filter(pk=token.pk).update(created=old_created)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.post("/api/account/profile/renew-session/", {}, format="json")

        self.assertEqual(response.status_code, 200, response.data)
        token.refresh_from_db()
        self.assertGreater(token.created, old_created)
        renewed_expires_at = timezone.datetime.fromisoformat(response.data["token_expires_at"])
        self.assertGreater(renewed_expires_at, timezone.now() + timedelta(minutes=59))

    def test_expired_session_cannot_be_renewed(self):
        token = Token.objects.create(user=self.user)
        Token.objects.filter(pk=token.pk).update(
            created=timezone.now() - timedelta(hours=1, seconds=1)
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

        response = self.client.post("/api/account/profile/renew-session/", {}, format="json")

        self.assertEqual(response.status_code, 401, response.data)


class TenantFoundationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tenant-member")
        self.other = User.objects.create_user(username="other-tenant-member")
        self.tenant_a = Tenant.objects.create(name="租户 A", slug="tenant-a")
        self.tenant_b = Tenant.objects.create(name="租户 B", slug="tenant-b")
        TenantMembership.objects.create(tenant=self.tenant_a, user=self.user)
        TenantMembership.objects.create(tenant=self.tenant_b, user=self.other)
        self.project_a = Project.objects.create(tenant=self.tenant_a, name="项目 A", pm=self.user)
        Project.objects.create(tenant=self.tenant_b, name="项目 B", pm=self.other)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_tenant_list_only_returns_memberships(self):
        response = self.client.get("/api/account/tenant/")

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["id"] for item in response.data], [str(self.tenant_a.id)])

    def test_project_list_uses_selected_tenant(self):
        response = self.client.get(
            "/api/project/project/",
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual([item["id"] for item in response.data], [self.project_a.id])

    def test_user_cannot_select_tenant_without_membership(self):
        response = self.client.get(
            "/api/project/project/",
            HTTP_X_TENANT_ID=str(self.tenant_b.id),
        )

        self.assertEqual(response.status_code, 403, response.data)

    @staticmethod
    def _response_items(response):
        return response.data.get("list", response.data.get("results", [])) \
            if isinstance(response.data, dict) else response.data

    def test_user_management_is_tenant_scoped_for_regular_user(self):
        response = self.client.get(
            "/api/account/user/",
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            [item["id"] for item in self._response_items(response)],
            [self.user.id],
        )

    def test_platform_admin_can_view_all_users_across_tenants(self):
        admin = User.objects.create_superuser(
            "all-user-admin", "all-user-admin@example.com", "password"
        )
        self.client.force_authenticate(admin)

        response = self.client.get(
            "/api/account/user/",
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        self.assertEqual(response.status_code, 200, response.data)
        ids = {item["id"] for item in self._response_items(response)}
        self.assertEqual(ids, {self.user.id, self.other.id, admin.id})

    def test_project_creation_uses_selected_tenant(self):
        admin = User.objects.create_superuser("tenant-admin", "admin@example.com", "password")
        TenantMembership.objects.create(
            tenant=self.tenant_b,
            user=admin,
            role=TenantMembership.Role.OWNER,
        )
        self.client.force_authenticate(admin)

        response = self.client.post(
            "/api/project/project/",
            {"name": "新项目", "intro": "", "pm": admin.id, "user_list": [admin.id]},
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant_b.id),
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Project.objects.get(pk=response.data["id"]).tenant_id, self.tenant_b.id)

    def test_platform_admin_can_create_tenant_and_manage_members(self):
        admin = User.objects.create_superuser("platform-owner", "owner@example.com", "password")
        client = APIClient()
        client.force_authenticate(admin)

        created = client.post(
            "/api/account/tenant/",
            {
                "name": "新租户",
                "slug": "new-tenant",
                "status": "active",
                "max_performance_concurrent_executions": 3,
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["max_performance_concurrent_executions"], 3)
        tenant_id = created.data["id"]
        self.assertEqual(
            Tenant.objects.get(pk=tenant_id).max_performance_concurrent_executions, 3,
        )
        self.assertTrue(TenantMembership.objects.filter(
            tenant_id=tenant_id, user=admin, role=TenantMembership.Role.OWNER,
        ).exists())

        added = client.post(
            f"/api/account/tenant/{tenant_id}/members/",
            {"username": self.user.username, "role": TenantMembership.Role.ADMIN},
            format="json",
        )
        self.assertEqual(added.status_code, 201, added.data)
        self.assertEqual(added.data["role"], TenantMembership.Role.ADMIN)

        updated = client.patch(
            f"/api/account/tenant/{tenant_id}/members/{self.user.id}/",
            {"role": TenantMembership.Role.VIEWER},
            format="json",
        )
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data["role"], TenantMembership.Role.VIEWER)

    def test_tenant_owner_cannot_change_performance_worker_quota(self):
        TenantMembership.objects.filter(tenant=self.tenant_a, user=self.user).update(
            role=TenantMembership.Role.OWNER,
        )

        response = self.client.patch(
            f"/api/account/tenant/{self.tenant_a.id}/",
            {"max_performance_concurrent_executions": 4},
            format="json",
        )

        self.assertEqual(response.status_code, 403, response.data)
        self.tenant_a.refresh_from_db()
        self.assertEqual(self.tenant_a.max_performance_concurrent_executions, 1)

    def test_tenant_owner_can_search_and_select_platform_user(self):
        TenantMembership.objects.filter(tenant=self.tenant_a, user=self.user).update(
            role=TenantMembership.Role.OWNER,
        )

        candidates = self.client.get(
            f"/api/account/tenant/{self.tenant_a.id}/member-candidates/",
            {"search": "other-tenant"},
        )
        added = self.client.post(
            f"/api/account/tenant/{self.tenant_a.id}/members/",
            {"user": self.other.id, "role": TenantMembership.Role.MEMBER},
            format="json",
        )

        self.assertEqual(candidates.status_code, 200, candidates.data)
        self.assertEqual(candidates.data, [{
            "id": self.other.id,
            "username": self.other.username,
            "is_member": False,
        }])
        self.assertEqual(added.status_code, 201, added.data)
        self.assertTrue(TenantMembership.objects.filter(
            tenant=self.tenant_a, user=self.other,
        ).exists())

    def test_last_tenant_manager_cannot_be_demoted(self):
        TenantMembership.objects.filter(tenant=self.tenant_a, user=self.user).update(
            role=TenantMembership.Role.OWNER,
        )
        response = self.client.patch(
            f"/api/account/tenant/{self.tenant_a.id}/members/{self.user.id}/",
            {"role": TenantMembership.Role.MEMBER},
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)


class SchemaDocumentationTests(TestCase):
    def test_anonymous_schema_loads_without_weakening_business_api(self):
        client = APIClient()
        schema = client.get("/api/schema/openapi.json")
        self.assertEqual(schema.status_code, 200)
        self.assertIn("json", schema["Content-Type"])
        self.assertIn("schema.json", schema["Content-Disposition"])
        document = json.loads(schema.content)
        self.assertIn("/api/project/project/", document["paths"])
        for prefix in ("/api/account/", "/api/case_api/", "/api/case_ui/", "/api/case_app/", "/api/monitor/", "/api/performance/"):
            self.assertTrue(any(path.startswith(prefix) for path in document["paths"]), prefix)

        browser = client.get(
            "/api/schema/openapi.json",
            HTTP_ACCEPT="text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        )
        self.assertEqual(browser.status_code, 200)
        self.assertIn("json", browser["Content-Type"])
        self.assertEqual(set(json.loads(browser.content)["paths"]), set(document["paths"]))

        business = client.get("/api/project/project/")
        self.assertIn(business.status_code, (401, 403))


class TenantStorageQuotaTests(SimpleTestCase):
    def test_usage_and_quota_are_scoped_to_tenant_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            tenant_a = "11111111-1111-1111-1111-111111111111"
            tenant_b = "22222222-2222-2222-2222-222222222222"
            path_a = tenant_path(base / "upload_yaml", tenant_a, "result-a", "report.json")
            path_b = tenant_path(base / "upload_yaml", tenant_b, "result-b", "report.json")
            path_a.parent.mkdir(parents=True)
            path_b.parent.mkdir(parents=True)
            path_a.write_bytes(b"a" * 8)
            path_b.write_bytes(b"b" * 20)

            self.assertEqual(tenant_storage_usage(tenant_a, base_dir=base), 8)
            tenant = SimpleNamespace(pk=tenant_a, storage_quota_bytes=10)
            self.assertEqual(ensure_tenant_storage_capacity(tenant, 2, base_dir=base), 8)
            with self.assertRaisesRegex(ValueError, "存储配额不足"):
                ensure_tenant_storage_capacity(tenant, 3, base_dir=base)


