import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

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
