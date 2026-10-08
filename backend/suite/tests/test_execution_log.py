from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

from suite.execution_log import format_log_payload, sanitize_log_text, write_execution_log


class ExecutionLogTests(SimpleTestCase):
    def test_structured_log_is_written_with_level(self):
        with TemporaryDirectory() as directory:
            write_execution_log("步骤 1/2 执行通过", "SUCCESS", base_path=directory)
            content = (Path(directory) / "logs/execution.log").read_text(encoding="utf-8")

        self.assertIn("[SUCCESS] 步骤 1/2 执行通过", content)

    def test_sensitive_values_are_masked_in_fallback_log(self):
        token = "eyJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoxfQ.abcdefghijklmnop"
        content = sanitize_log_text(f"extrac_data={{'token': '{token}', 'password': 'demo123'}}")

        self.assertNotIn(token, content)
        self.assertNotIn("demo123", content)
        self.assertIn("token': '***", content)
        self.assertIn("password': '***", content)

    def test_structured_log_masks_sensitive_message(self):
        with TemporaryDirectory() as directory:
            write_execution_log("authorization=Bearer-secret-token", base_path=directory)
            content = (Path(directory) / "logs/execution.log").read_text(encoding="utf-8")

        self.assertNotIn("Bearer-secret-token", content)
        self.assertIn("authorization=***", content)

    def test_request_payload_masks_nested_credentials(self):
        content = format_log_payload({
            "headers": {"Authorization": "Bearer demo-token", "X-Trace": "trace-1"},
            "params": {"page": 1, "token": "query-token"},
            "json": {"profile": {"password": "demo123", "name": "张三"}},
        })

        self.assertNotIn("demo-token", content)
        self.assertNotIn("query-token", content)
        self.assertNotIn("demo123", content)
        self.assertIn('"X-Trace":"trace-1"', content)
        self.assertIn('"page":1', content)
        self.assertIn('"name":"张三"', content)

    def test_request_payload_is_truncated(self):
        content = format_log_payload({"data": "x" * 100}, max_chars=30)

        self.assertLessEqual(len(content), 38)
        self.assertTrue(content.endswith("…（内容已截断）"))
