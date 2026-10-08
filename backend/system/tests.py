import base64
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from project.models import Project
from account.models import Tenant
from .models import ServerConnection, SystemConfiguration


class ServerConnectionPermissionTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user(username="server-member", password="test-password")
        self.manager = User.objects.create_user(username="server-manager", password="test-password")
        self.admin = User.objects.create_user(username="server-admin", password="test-password", is_staff=True)
        self.project = Project.objects.create(name="测试项目", pm=self.manager)
        self.connection = ServerConnection.objects.create(
            name="测试服务器", host="127.0.0.1", username="deployer",
            auth_type=ServerConnection.AuthType.PRIVATE_KEY, private_key_path="/tmp/test-key",
            project=self.project, created_by=self.admin,
        )

    def test_member_cannot_read_or_configure_server_connections(self):
        client = APIClient()
        client.force_authenticate(self.member)
        self.assertEqual(client.get("/api/system/server-connection/").status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            client.post("/api/system/server-connection/", {
                "name": "越权服务器", "host": "10.0.0.1", "port": 22, "username": "root",
                "auth_type": "private_key", "private_key_path": "/tmp/key", "strict_host_key": True,
            }, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_admin_can_create_server_connection_without_returning_secrets(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        response = client.post("/api/system/server-connection/", {
            "project": self.project.id, "name": "管理员服务器", "host": "10.0.0.2", "port": 22, "username": "deployer",
            "auth_type": "password", "password": "secret", "strict_host_key": True,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertNotIn("password", response.data)
        self.assertTrue(response.data["password_configured"])

    def test_project_manager_can_maintain_connections_in_own_project(self):
        client = APIClient()
        client.force_authenticate(self.manager)
        self.assertEqual(client.get("/api/system/server-connection/").status_code, status.HTTP_200_OK)
        response = client.post("/api/system/server-connection/", {
            "project": self.project.id, "name": "项目服务器", "host": "10.0.0.3", "port": 22,
            "username": "deployer", "auth_type": "password", "password": "secret",
            "strict_host_key": True,
        }, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_platform_admin_only_sees_and_writes_current_tenant_connections(self):
        tenant_a = self.project.tenant
        tenant_b = Tenant.objects.create(name="服务器租户 B", slug="server-tenant-b")
        project_b = Project.objects.create(name="租户 B 项目", tenant=tenant_b, pm=self.admin)
        connection_b = ServerConnection.objects.create(
            tenant=tenant_b, project=project_b, name="租户 B 服务器", host="10.0.1.1",
            username="deployer", auth_type=ServerConnection.AuthType.PRIVATE_KEY,
            private_key_path="/tmp/test-key", created_by=self.admin,
        )
        client = APIClient()
        client.force_authenticate(self.admin)

        response = client.get(
            "/api/system/server-connection/", HTTP_X_TENANT_ID=str(tenant_a.id),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([item["id"] for item in response.data], [self.connection.id])
        self.assertEqual(
            client.get(
                f"/api/system/server-connection/{connection_b.id}/",
                HTTP_X_TENANT_ID=str(tenant_a.id),
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )

        cross_tenant = client.post(
            "/api/system/server-connection/",
            {
                "project": project_b.id, "name": "跨租户服务器", "host": "10.0.1.2",
                "port": 22, "username": "root", "auth_type": "private_key",
                "private_key_path": "/tmp/key", "strict_host_key": True,
            },
            format="json", HTTP_X_TENANT_ID=str(tenant_a.id),
        )
        self.assertEqual(cross_tenant.status_code, status.HTTP_400_BAD_REQUEST)

        same_name = client.post(
            "/api/system/server-connection/",
            {
                "project": project_b.id, "name": self.connection.name, "host": "10.0.1.3",
                "port": 22, "username": "root", "auth_type": "private_key",
                "private_key_path": "/tmp/key", "strict_host_key": True,
            },
            format="json", HTTP_X_TENANT_ID=str(tenant_b.id),
        )
        self.assertEqual(same_name.status_code, status.HTTP_201_CREATED, same_name.data)
        self.assertEqual(ServerConnection.objects.get(pk=same_name.data["id"]).tenant_id, tenant_b.id)


class SystemBrandingConfigurationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="branding-admin", password="test-password", is_staff=True,
        )

    def test_branding_is_public_and_admin_can_upload_images(self):
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            client = APIClient()
            public_response = client.get("/api/system/branding/")
            self.assertEqual(public_response.status_code, status.HTTP_200_OK)
            client.credentials(HTTP_AUTHORIZATION="Token invalid-token")
            self.assertEqual(client.get("/api/system/branding/").status_code, status.HTTP_200_OK)
            client.credentials()
            self.assertEqual(public_response.data["platform_logo_light_url"], "")
            self.assertEqual(public_response.data["platform_logo_dark_url"], "")
            self.assertNotIn("platform_icon_url", public_response.data)

            client.force_authenticate(self.admin)
            image = SimpleUploadedFile(
                "platform.png",
                base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="),
                content_type="image/png",
            )
            dark_image = SimpleUploadedFile(
                "platform-dark.png",
                base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="),
                content_type="image/png",
            )
            response = client.put(
                "/api/system/configuration/",
                {
                    "report_retention_days": 30,
                    "platform_icon": image,
                    "platform_icon_dark": dark_image,
                },
                format="multipart",
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
            self.assertIn(
                "/api/system/branding/platform_icon/",
                response.data["platform_logo_light_url"],
            )
            self.assertIn(
                "/api/system/branding/platform_icon_dark/",
                response.data["platform_logo_dark_url"],
            )
            self.assertEqual(response.data["favicon_url"], response.data["platform_logo_light_url"])
            self.assertNotIn("platform_icon_url", response.data)
            self.assertNotIn("platform_icon", response.data)
            self.assertNotIn("platform_icon_dark", response.data)

            client.force_authenticate(user=None)
            client.credentials(HTTP_AUTHORIZATION="Token invalid-token")
            asset_response = client.get("/api/system/branding/platform_icon/")
            self.assertEqual(asset_response.status_code, status.HTTP_200_OK)
            self.assertEqual(asset_response["Content-Type"], "image/png")
            favicon_response = client.get("/api/system/branding/favicon/")
            self.assertEqual(favicon_response.status_code, status.HTTP_200_OK)
            dark_asset_response = client.get("/api/system/branding/platform_icon_dark/")
            self.assertEqual(dark_asset_response.status_code, status.HTTP_200_OK)
            self.assertEqual(dark_asset_response["Content-Type"], "image/png")

    def test_non_image_upload_is_rejected(self):
        with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
            client = APIClient()
            client.force_authenticate(self.admin)
            invalid = SimpleUploadedFile("notes.txt", b"not-an-image", content_type="text/plain")
            response = client.put(
                "/api/system/configuration/",
                {"report_retention_days": 15, "platform_icon": invalid},
                format="multipart",
            )
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertFalse(SystemConfiguration.objects.get(pk=1).platform_icon)

    def test_admin_can_configure_platform_worker_limit(self):
        client = APIClient()
        client.force_authenticate(self.admin)

        response = client.put(
            "/api/system/configuration/",
            {
                "report_retention_days": 15,
                "max_worker_count": 6,
                "max_performance_worker_count": 3,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["max_worker_count"], 6)
        self.assertEqual(response.data["max_performance_worker_count"], 3)
        configuration = SystemConfiguration.objects.get(pk=1)
        self.assertEqual(configuration.max_worker_count, 6)
        self.assertEqual(configuration.max_performance_worker_count, 3)

        from .runtime import configured_max_performance_worker_count, configured_max_worker_count

        self.assertEqual(configured_max_worker_count(), 6)
        self.assertEqual(configured_max_performance_worker_count(), 3)

    def test_worker_limit_rejects_values_outside_supported_range(self):
        client = APIClient()
        client.force_authenticate(self.admin)

        response = client.put(
            "/api/system/configuration/",
            {"report_retention_days": 15, "max_worker_count": 65},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("max_worker_count", response.data)

        response = client.put(
            "/api/system/configuration/",
            {
                "report_retention_days": 15,
                "max_worker_count": 2,
                "max_performance_worker_count": 33,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("max_performance_worker_count", response.data)
