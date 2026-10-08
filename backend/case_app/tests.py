import tempfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from account.models import Tenant, TenantMembership
from project.models import Project

from .inspector import parse_page_source
from .executor import _step_execution_detail, _step_start_log
from .health import check_appium_node, check_appium_nodes, refresh_stale_appium_nodes
from .models import AppApplication, AppCase, AppDevice, AppExecutionNode, AppRun


class InspectorPageSourceTests(SimpleTestCase):
    def test_parses_bounds_hierarchy_and_locator_priority(self):
        source = """<?xml version="1.0" encoding="UTF-8"?>
        <hierarchy>
          <node class="android.widget.FrameLayout" bounds="[0,0][1080,2340]">
            <node class="android.widget.Button" text="登录" resource-id="com.demo:id/login"
                  content-desc="登录按钮" clickable="true" enabled="true" bounds="[420,1680][660,1780]" />
          </node>
        </hierarchy>"""

        elements = parse_page_source(source)
        button = elements[-1]

        self.assertEqual(button["parent_id"], elements[-2]["node_id"])
        self.assertEqual(button["bounds"], [420, 1680, 660, 1780])
        self.assertTrue(button["clickable"])
        self.assertEqual(button["candidates"][0]["type"], "accessibility id")
        self.assertEqual(button["candidates"][1]["type"], "id")
        self.assertIn("android.widget.Button[1]", button["xpath"])

    def test_keeps_correct_xpath_index_for_same_class_siblings(self):
        source = """<hierarchy><node class="android.widget.ListView">
          <node class="android.widget.TextView" text="A" />
          <node class="android.widget.TextView" text="B"><node class="android.widget.Button" text="C" /></node>
        </node></hierarchy>"""
        elements = parse_page_source(source)
        second = next(item for item in elements if item["text"] == "B")
        child = next(item for item in elements if item["text"] == "C")

        self.assertTrue(second["xpath"].endswith("android.widget.TextView[2]"))
        self.assertIn("android.widget.TextView[2]/android.widget.Button[1]", child["xpath"])


class AppStepExecutionDetailTests(SimpleTestCase):
    def test_records_resolved_input_and_locator(self):
        step = SimpleNamespace(
            value="${mobile}", action="input", options={}, target={}, element_id=1,
            element=SimpleNamespace(
                name="手机号", page_name="登录页", locator_type="id",
                locator_value="com.example:id/mobile", element_class="android.widget.EditText",
            ),
        )

        detail = _step_execution_detail(step, {"mobile": "13800138000"})

        self.assertEqual(detail["value"], "13800138000")
        self.assertEqual(detail["element_name"], "手机号")
        self.assertEqual(detail["locator_value"], "com.example:id/mobile")

    def test_masks_sensitive_input(self):
        step = SimpleNamespace(
            value="real-secret", action="input", options={}, target={}, element_id=1,
            element=SimpleNamespace(
                name="登录密码", page_name="登录页", locator_type="id",
                locator_value="com.example:id/password", element_class="android.widget.EditText",
            ),
        )

        detail = _step_execution_detail(step, {})

        self.assertEqual(detail["value"], "******")
        self.assertTrue(detail["value_masked"])

    def test_input_value_is_included_in_step_log(self):
        result = SimpleNamespace(name="输入文本 · 手机号", detail={"value": "13800138000"})
        step = SimpleNamespace(action="input")

        message = _step_start_log(2, 3, result, step)

        self.assertEqual(message, "步骤 2/3：输入文本 · 手机号，输入内容：13800138000")


class AppiumNodeHealthTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Appium 健康租户", slug="appium-health")
        self.user = User.objects.create_user("appium-health-user")
        self.project = Project.objects.create(
            tenant=self.tenant, name="Appium 健康项目", pm=self.user,
        )
        self.node = AppExecutionNode.objects.create(
            project=self.project, name="Appium 健康节点", server_url="http://127.0.0.1:4723",
        )

    @patch("case_app.health.AppiumClient.status", return_value={"ready": True})
    def test_successful_probe_updates_online_status_and_heartbeat(self, status):
        connected, value = check_appium_node(self.node)

        self.node.refresh_from_db()
        self.assertTrue(connected)
        self.assertEqual(value, {"ready": True})
        self.assertEqual(self.node.status, "online")
        self.assertIsNotNone(self.node.last_seen_at)
        status.assert_called_once_with()

    @patch("case_app.health.AppiumClient.status", side_effect=ConnectionError("连接失败"))
    def test_failed_probe_marks_offline_and_keeps_last_successful_heartbeat(self, status):
        previous_heartbeat = timezone.now() - timedelta(minutes=5)
        AppExecutionNode.objects.filter(pk=self.node.pk).update(
            status="online", last_seen_at=previous_heartbeat,
        )
        self.node.refresh_from_db()

        connected, value = check_appium_node(self.node)

        self.node.refresh_from_db()
        self.assertFalse(connected)
        self.assertIsNone(value)
        self.assertEqual(self.node.status, "offline")
        self.assertEqual(self.node.last_seen_at, previous_heartbeat)
        self.assertIn("连接失败", self.node.last_message)
        status.assert_called_once_with()

    @override_settings(APPIUM_NODE_OFFLINE_SECONDS=60)
    def test_stale_online_node_is_marked_offline(self):
        AppExecutionNode.objects.filter(pk=self.node.pk).update(
            status="online", last_seen_at=timezone.now() - timedelta(minutes=2),
        )

        changed = refresh_stale_appium_nodes()

        self.node.refresh_from_db()
        self.assertEqual(changed, 1)
        self.assertEqual(self.node.status, "offline")
        self.assertIn("心跳超时", self.node.last_message)

    @patch("case_app.health.AppiumClient.status", return_value={"ready": True})
    def test_periodic_check_only_probes_enabled_nodes(self, status):
        AppExecutionNode.objects.create(
            project=self.project, name="停用节点", enabled=False,
            server_url="http://127.0.0.1:4724",
        )

        result = check_appium_nodes()

        self.assertEqual(result["checked"], 1)
        self.assertEqual(result["online"], 1)
        self.assertEqual(result["offline"], 0)
        status.assert_called_once_with()


class AppRunDestroyCleanupTests(TestCase):
    """删除 App 执行记录时，只清理该租户命名空间下的运行目录。

    运行产物固定由 ``case_app/executor.py`` 建在
    ``app_runs/tenant_<租户>/<执行编号>/`` 下。此前 ``perform_destroy`` 在租户目录
    不存在时会回退去删 ``app_runs/<执行编号>/``，一旦磁盘上存在同名扁平目录就会被
    误删。这里锁住两点：租户目录被清理、同名扁平目录不受影响。
    """

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        settings_override = override_settings(BASE_DIR=self.base)
        settings_override.enable()
        self.addCleanup(settings_override.disable)

        self.tenant = Tenant.objects.create(name="App 清理租户", slug="app-cleanup")
        self.user = User.objects.create_user(username="app-cleanup-user")
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.user, role=TenantMembership.Role.OWNER
        )
        self.project = Project.objects.create(
            tenant=self.tenant, name="App 清理项目", pm=self.user
        )
        application = AppApplication.objects.create(
            project=self.project, name="测试 App", package_name="com.example.cleanup"
        )
        node = AppExecutionNode.objects.create(project=self.project, name="本地 Appium")
        device = AppDevice.objects.create(
            project=self.project, node=node, name="Pixel 5", udid="emulator-5554",
            state=AppDevice.State.ONLINE,
        )
        case = AppCase.objects.create(
            project=self.project, application=application, default_device=device, name="App 登录"
        )
        self.run = AppRun.objects.create(
            tenant=self.tenant, case=case, project=self.project, application=application,
            device=device, execution_no=77001, status=AppRun.Status.PASSED,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def _make_dir(self, path):
        path.mkdir(parents=True, exist_ok=True)
        (path / "artifact.txt").write_text("x", encoding="utf-8")
        return path

    def test_destroy_removes_only_the_tenant_scoped_directory(self):
        tenant_dir = self._make_dir(
            self.base / "app_runs" / f"tenant_{self.tenant.pk}" / str(self.run.execution_no)
        )
        flat_dir = self._make_dir(self.base / "app_runs" / str(self.run.execution_no))

        response = self.client.delete(
            f"/api/case_app/run/{self.run.id}/",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(AppRun.objects.filter(pk=self.run.pk).exists())
        self.assertFalse(tenant_dir.exists(), "租户命名空间下的运行目录应被清理")
        self.assertTrue(flat_dir.exists(), "同名扁平目录不属于本次执行，不能误删")
        self.assertTrue((flat_dir / "artifact.txt").exists())

    def test_destroy_does_not_fall_back_to_a_same_named_flat_directory(self):
        """租户目录不存在时，不能回退去删同名扁平目录。

        这是已删除的「扁平布局回退」分支的直接回归防线：旧实现会在租户目录缺失时
        把 ``app_runs/<执行编号>/`` 当成本次执行的产物删掉，而那个目录可能属于
        别的用途，删了无法恢复。
        """
        flat_dir = self._make_dir(self.base / "app_runs" / str(self.run.execution_no))
        tenant_dir = (
            self.base / "app_runs" / f"tenant_{self.tenant.pk}" / str(self.run.execution_no)
        )
        self.assertFalse(tenant_dir.exists(), "本用例要求租户目录缺失")

        response = self.client.delete(
            f"/api/case_app/run/{self.run.id}/",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(AppRun.objects.filter(pk=self.run.pk).exists())
        self.assertTrue(flat_dir.exists(), "扁平目录不在租户命名空间内，不能回退删除")
        self.assertTrue((flat_dir / "artifact.txt").exists())

    def test_destroy_succeeds_when_the_run_directory_is_absent(self):
        """历史记录的执行目录可能已被清理，此时删除记录仍应成功。"""
        response = self.client.delete(
            f"/api/case_app/run/{self.run.id}/",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(AppRun.objects.filter(pk=self.run.pk).exists())
