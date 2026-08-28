from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from project.models import Environment, Project
from suite.models import Suite

from .models import ExecutionTemplate


class ExecutionTemplateDeleteTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="template-admin", is_staff=True)
        self.member = User.objects.create_user(username="template-member")
        self.project = Project.objects.create(name="模板项目", intro="", pm=self.admin)
        self.project.user_list.add(self.member)
        self.environment = Environment.objects.create(
            project=self.project,
            name=Environment.Name.DEV,
            base_url="https://example.com",
        )
        self.suite = Suite.objects.create(name="模板套件", environment=self.environment)
        self.template = ExecutionTemplate.objects.create(
            name="可删除模板",
            description="用于验证删除流程",
            project=self.project,
            suite=self.suite,
        )
        self.client = APIClient()

    def test_admin_can_delete_template(self):
        self.client.force_authenticate(self.admin)

        response = self.client.delete(f"/api/template/{self.template.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ExecutionTemplate.objects.filter(pk=self.template.id).exists())

    def test_non_admin_cannot_delete_template(self):
        self.client.force_authenticate(self.member)

        response = self.client.delete(f"/api/template/{self.template.id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(ExecutionTemplate.objects.filter(pk=self.template.id).exists())
