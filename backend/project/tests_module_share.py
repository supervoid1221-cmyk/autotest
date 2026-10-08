"""项目级共享目录：接口 / UI 元素 / App 元素三个页面读写同一套数据。

改造前三个模块各有一张目录表，同一个业务模块要在三个页面各建一遍。这里锁定
改造后的契约：只有一行目录，三处资产都挂在它上面；删除时三个域一起受影响。
"""

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from case_api.models import Endpoint
from case_app.models import AppApplication, AppElement
from case_ui.models import Element
from project.models import Module, Project


def unwrap_list(payload):
    """列表接口可能带分页信封，也可能直接返回数组。"""
    if isinstance(payload, dict):
        return payload.get("list", payload.get("results", []))
    return payload


class SharedModuleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="module-owner")
        self.project = Project.objects.create(name="共享目录项目", pm=self.user)
        self.module = Module.objects.create(project=self.project, name="登录")
        self.application = AppApplication.objects.create(
            project=self.project, name="测试 App", package_name="com.example.app",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _make_endpoint(self):
        return Endpoint.objects.create(
            project=self.project, module=self.module, name="登录接口", method="POST", url="/login",
        )

    def _make_ui_element(self):
        return Element.objects.create(
            project=self.project, module=self.module, name="登录按钮", by="ID", value="login",
        )

    def _make_app_element(self):
        return AppElement.objects.create(
            project=self.project, application=self.application, module=self.module,
            name="登录按钮", locator_type="id", locator_value="com.example.app:id/login",
        )

    def test_one_module_row_serves_all_three_managers(self):
        """三个模块的资产挂在同一行目录上，而不是各自一套同名目录。"""
        endpoint = self._make_endpoint()
        ui_element = self._make_ui_element()
        app_element = self._make_app_element()

        self.assertEqual(endpoint.module_id, self.module.id)
        self.assertEqual(ui_element.module_id, self.module.id)
        self.assertEqual(app_element.module_id, self.module.id)
        self.assertEqual(Module.objects.filter(project=self.project, name="登录").count(), 1)

    def test_list_reports_counts_for_every_domain(self):
        self._make_endpoint()
        self._make_ui_element()
        self._make_app_element()

        response = self.client.get("/api/project/module/", {"project": self.project.id})

        self.assertEqual(response.status_code, 200)
        row = next(item for item in unwrap_list(response.data) if item["id"] == self.module.id)
        self.assertEqual(row["endpoint_count"], 1)
        self.assertEqual(row["ui_element_count"], 1)
        self.assertEqual(row["app_element_count"], 1)

    def test_list_only_returns_modules_of_the_requested_project(self):
        other_project = Project.objects.create(name="另一个项目", pm=self.user)
        Module.objects.create(project=other_project, name="订单")

        response = self.client.get("/api/project/module/", {"project": self.project.id})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in unwrap_list(response.data)], [self.module.id])

    def test_delete_without_cascade_unassigns_every_domain(self):
        endpoint = self._make_endpoint()
        ui_element = self._make_ui_element()
        app_element = self._make_app_element()

        response = self.client.delete(f"/api/project/module/{self.module.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["cascade"])
        self.assertEqual(
            response.data["counts"],
            {"endpoint_count": 1, "ui_element_count": 1, "app_element_count": 1},
        )
        self.assertFalse(Module.objects.filter(pk=self.module.id).exists())
        for instance in (endpoint, ui_element, app_element):
            instance.refresh_from_db()
            self.assertIsNone(instance.module_id)

    def test_delete_with_cascade_removes_every_domain(self):
        self._make_endpoint()
        self._make_ui_element()
        self._make_app_element()

        response = self.client.delete(f"/api/project/module/{self.module.id}/?cascade=true")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["cascade"])
        self.assertFalse(Endpoint.objects.filter(module_id=self.module.id).exists())
        self.assertFalse(Element.objects.filter(module_id=self.module.id).exists())
        self.assertFalse(AppElement.objects.filter(module_id=self.module.id).exists())

    def test_same_name_is_allowed_in_another_project(self):
        other_project = Project.objects.create(name="另一个项目", pm=self.user)
        Module.objects.create(project=other_project, name="登录")

        self.assertEqual(Module.objects.filter(name="登录").count(), 2)

    def test_duplicate_name_within_a_project_is_rejected(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Module.objects.create(project=self.project, name="登录")

    def test_duplicate_name_returns_a_client_error_not_a_server_error(self):
        response = self.client.post(
            "/api/project/module/", {"project": self.project.id, "name": "登录"}, format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
