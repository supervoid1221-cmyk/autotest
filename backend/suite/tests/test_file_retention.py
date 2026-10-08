import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from account.models import Tenant
from case_app.models import AppApplication, AppCase, AppDevice, AppExecutionNode, AppRun
from project.models import Project
from suite.retention import cleanup_expired_files
from suite import tasks


class FileRetentionTests(SimpleTestCase):
    def _touch_tree(self, path, modified_at):
        timestamp = modified_at.timestamp()
        for item in sorted(path.rglob("*"), reverse=True):
            os.utime(item, (timestamp, timestamp))
        os.utime(path, (timestamp, timestamp))

    @override_settings(FILE_RETENTION_DAYS=15)
    def test_removes_expired_outputs_and_protects_active_run(self):
        now = datetime(2026, 8, 21, 12, 0, 0)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            upload = base / "upload_yaml"
            old_run = upload / "result_old"
            recent_run = upload / "result_recent"
            active_run = upload / "result_active"
            for path in (old_run, recent_run, active_run):
                (path / "logs").mkdir(parents=True)
                (path / "logs" / "runner.log").write_text("log", encoding="utf-8")
            legacy_log = base / "logs" / "old.log"
            legacy_log.parent.mkdir(parents=True)
            legacy_log.write_text("log", encoding="utf-8")

            old_time = now - timedelta(days=16)
            self._touch_tree(old_run, old_time)
            self._touch_tree(active_run, old_time)
            self._touch_tree(recent_run, now - timedelta(days=2))
            os.utime(legacy_log, (old_time.timestamp(), old_time.timestamp()))

            result = cleanup_expired_files(
                base_dir=base,
                active_paths=[active_run],
                now=now,
            )

            self.assertFalse(old_run.exists())
            self.assertFalse(legacy_log.exists())
            self.assertTrue(recent_run.exists())
            self.assertTrue(active_run.exists())
            self.assertEqual(result["removed_count"], 2)
            self.assertEqual(result["errors"], [])

    def test_dry_run_only_lists_expired_output(self):
        now = datetime(2026, 8, 21, 12, 0, 0)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            old_run = base / "upload_yaml" / "result_old"
            old_run.mkdir(parents=True)
            self._touch_tree(old_run, now - timedelta(days=20))

            result = cleanup_expired_files(
                15, dry_run=True, base_dir=base, active_paths=[], now=now
            )

            self.assertTrue(old_run.exists())
            self.assertEqual(result["removed"], [str(old_run.resolve())])
            self.assertTrue(result["dry_run"])

    def test_recent_child_prevents_old_directory_from_being_removed(self):
        now = datetime(2026, 8, 21, 12, 0, 0)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            run = base / "upload_yaml" / "result_mixed"
            run.mkdir(parents=True)
            recent_file = run / "runner.log"
            recent_file.write_text("running", encoding="utf-8")
            old_time = now - timedelta(days=20)
            os.utime(run, (old_time.timestamp(), old_time.timestamp()))
            recent_time = now - timedelta(days=1)
            os.utime(recent_file, (recent_time.timestamp(), recent_time.timestamp()))

            cleanup_expired_files(15, base_dir=base, active_paths=[], now=now)

            self.assertTrue(run.exists())

    def test_daily_cleanup_is_compatible_with_timezone_disabled(self):
        original_cleanup_date = tasks._last_cleanup_date
        tasks._last_cleanup_date = None
        try:
            with self.settings(USE_TZ=False):
                with self.subTest("首次执行"):
                    with patch("suite.tasks.cleanup_expired_files") as cleanup:
                        tasks._cleanup_once_daily()
                        tasks._cleanup_once_daily()
                        cleanup.assert_called_once_with()
        finally:
            tasks._last_cleanup_date = original_cleanup_date


class AppRunRetentionLayoutTests(TestCase):
    """过期 App 执行记录的目录清理只认租户命名空间。

    运行产物固定由 ``case_app/executor.py`` 建在
    ``app_runs/tenant_<租户>/<执行编号>/`` 下。此前 ``cleanup_expired_files`` 在租户
    目录不存在时会回退去删 ``app_runs/<执行编号>/``，一旦磁盘上存在同名扁平目录就会
    被误删。这里锁住两点：租户目录被清理、同名扁平目录不受影响。
    """

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        settings_override = override_settings(BASE_DIR=self.base)
        settings_override.enable()
        self.addCleanup(settings_override.disable)

        tenant = Tenant.objects.create(name="保留期租户", slug="retention-tenant")
        user = User.objects.create_user(username="retention-user")
        project = Project.objects.create(tenant=tenant, name="保留期项目", pm=user)
        application = AppApplication.objects.create(
            project=project, name="测试 App", package_name="com.example.retention"
        )
        node = AppExecutionNode.objects.create(project=project, name="本地 Appium")
        device = AppDevice.objects.create(
            project=project, node=node, name="Pixel 5", udid="emulator-5554",
            state=AppDevice.State.ONLINE,
        )
        case = AppCase.objects.create(
            project=project, application=application, default_device=device, name="App 登录"
        )
        self.tenant = tenant
        self.run = AppRun.objects.create(
            tenant=tenant, case=case, project=project, application=application,
            device=device, execution_no=88001, status=AppRun.Status.PASSED,
            finished_at=timezone.now() - timedelta(days=30),
        )

    def _make_run_dir(self, path):
        (path / "logs").mkdir(parents=True, exist_ok=True)
        (path / "logs" / "runner.log").write_text("log", encoding="utf-8")
        return path

    def _cleanup(self):
        # base_dir 会默认关掉数据库记录清理，这里显式打开以覆盖 App 记录分支。
        return cleanup_expired_files(
            15, base_dir=self.base, include_database_records=True, active_paths=[],
        )

    def test_expired_run_directory_is_removed_from_the_tenant_namespace(self):
        tenant_dir = self._make_run_dir(
            self.base / "app_runs" / f"tenant_{self.tenant.pk}" / str(self.run.execution_no)
        )

        self._cleanup()

        self.assertFalse(AppRun.objects.filter(pk=self.run.pk).exists())
        self.assertFalse(tenant_dir.exists(), "租户命名空间下的过期运行目录应被清理")

    def test_expired_run_does_not_delete_a_same_named_flat_directory(self):
        """这是已删除的「扁平布局回退」分支的直接回归防线。"""
        flat_dir = self._make_run_dir(self.base / "app_runs" / str(self.run.execution_no))
        tenant_dir = (
            self.base / "app_runs" / f"tenant_{self.tenant.pk}" / str(self.run.execution_no)
        )
        self.assertFalse(tenant_dir.exists(), "本用例要求租户目录缺失")

        self._cleanup()

        self.assertFalse(AppRun.objects.filter(pk=self.run.pk).exists())
        self.assertTrue(flat_dir.exists(), "扁平目录不在租户命名空间内，不能回退删除")
        self.assertTrue((flat_dir / "logs" / "runner.log").exists())
