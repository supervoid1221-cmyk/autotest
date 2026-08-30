from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from project.models import Project
from .models import ServerConnection


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
