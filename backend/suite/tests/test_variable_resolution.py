import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from suite.reporting import load_variable_resolution, record_variable_resolution


class VariableResolutionTests(SimpleTestCase):
    def test_records_sources_overrides_and_effective_value(self):
        with tempfile.TemporaryDirectory() as directory:
            run_path = Path(directory)
            record_variable_resolution(run_path, "project", {"region": "BR", "count": 1})
            record_variable_resolution(run_path, "template", {"count": 2})
            record_variable_resolution(
                run_path, "api_extract", {"order_id": 1001},
                step_id=8, step_name="创建订单",
            )

            details = load_variable_resolution(run_path)

            self.assertEqual([item["source"] for item in details], ["project", "project", "template", "api_extract"])
            self.assertFalse(details[1]["effective"])
            self.assertEqual(details[2]["overrode_source"], "project")
            self.assertTrue(details[2]["effective"])
            self.assertEqual(details[3]["step_name"], "创建订单")

    def test_masks_sensitive_values_in_resolution_file(self):
        with tempfile.TemporaryDirectory() as directory:
            run_path = Path(directory)
            record_variable_resolution(
                run_path, "environment_token",
                {"authorization": "Bearer secret", "tenant": "demo"},
            )

            details = load_variable_resolution(run_path)

            self.assertEqual(details[0]["value"], "***")
            self.assertEqual(details[1]["value"], "demo")
            self.assertNotIn("Bearer secret", (run_path / "variable_resolution.yaml").read_text(encoding="utf-8"))
