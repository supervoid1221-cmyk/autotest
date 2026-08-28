import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Tesla.settings")
import django

django.setup()

from fullstack_framework.commons.api_executor import (
    StepExecutionResult,
    UnresolvedVariableError,
    execute_api_step,
    execute_api_step_with_failure_retry,
)
from fullstack_framework.commons.case_util import (
    NATIVE_RESPONSE_BODY_PREVIEW_BYTES,
    _execute_case_info,
    _response_body_preview,
)
from fullstack_framework.commons.models import CaseInfo


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code
        self.headers = {"Content-Type": "application/json"}
        self.text = '{"data":{"id":123}}'

    def json(self):
        return self.payload


class SharedApiExecutorTests(unittest.TestCase):
    def test_generated_suite_case_continues_on_failure_by_default(self):
        case = CaseInfo(
            test_name="充值记录",
            request={"method": "GET", "url": "https://example.com/deposit/list"},
            validate={},
        )

        self.assertTrue(case.continue_on_failure)

    def test_generated_suite_case_accepts_continue_on_failure(self):
        case = CaseInfo(
            test_name="充值记录",
            request={"method": "GET", "url": "https://example.com/deposit/list"},
            validate={},
            continue_on_failure=False,
            environment_name="Dev",
        )

        self.assertFalse(case.continue_on_failure)

    def test_generated_suite_case_disables_failure_retry_by_default(self):
        case = CaseInfo(
            test_name="充值记录",
            request={"method": "GET", "url": "https://example.com/deposit/list"},
            validate={},
        )

        self.assertFalse(case.retry_on_failure)
        self.assertEqual(case.failure_retry_count, 1)

    def test_failure_retry_runs_again_and_merges_attempts(self):
        execute_once = Mock(side_effect=[
            StepExecutionResult(
                False, errors=["断言失败"], attempts=[{"attempt": 1, "errors": ["断言失败"]}],
                duration_seconds=0.1,
            ),
            StepExecutionResult(
                True, attempts=[{"attempt": 1, "errors": []}], duration_seconds=0.2,
            ),
        ])

        result = execute_api_step_with_failure_retry(
            execute_once, enabled=True, retry_count=1
        )

        self.assertTrue(result.passed)
        self.assertEqual(execute_once.call_count, 2)
        self.assertEqual(len(result.attempts), 2)
        self.assertEqual(result.attempts[0]["execution_attempt"], 1)
        self.assertEqual(result.attempts[1]["execution_attempt"], 2)
        self.assertAlmostEqual(result.duration_seconds, 0.3)

    def test_disabled_failure_retry_executes_only_once(self):
        execute_once = Mock(return_value=StepExecutionResult(False, errors=["失败"]))

        result = execute_api_step_with_failure_retry(
            execute_once, enabled=False, retry_count=5
        )

        self.assertFalse(result.passed)
        execute_once.assert_called_once_with()

    @patch("fullstack_framework.commons.case_util._append_native_step")
    @patch("fullstack_framework.commons.case_util._mark_native_step_running")
    @patch("fullstack_framework.commons.case_util.Environment")
    @patch("fullstack_framework.commons.case_util.session")
    def test_expired_token_refresh_writes_to_current_run_directory(
        self, api_session, environment_model, _mark_running, _append_step
    ):
        expired = FakeResponse({"code": 1023, "data": None, "msg": "jwt expired"})
        success = FakeResponse({"code": 0, "data": {"currency": "BRL"}})
        api_session.request.side_effect = [expired, success]
        environment = Mock(name="environment")
        environment.name = "Dev"
        environment.prepare_auth.return_value = {"Authorization": "Bearer refreshed"}
        environment_model.objects.filter.return_value.first.return_value = environment
        case = CaseInfo(
            test_name="获取余额",
            request={"method": "GET", "url": "https://example.com/wallet", "headers": {}},
            validate={}, project_id=5, environment_name="Dev",
        )

        result = _execute_case_info(case)

        self.assertTrue(result.passed)
        environment.prepare_auth.assert_called_once_with(Path.cwd(), "Dev", force_refresh=True)
        self.assertEqual(api_session.request.call_count, 2)
        self.assertEqual(api_session.request.call_args_list[1].kwargs["headers"]["Authorization"], "Bearer refreshed")

    @patch("fullstack_framework.commons.api_executor.run_dynamic_function")
    def test_unresolved_variable_fails_before_request(self, dynamic_function):
        dynamic_function.side_effect = ValueError("不存在")
        request_func = Mock()
        result = execute_api_step(
            request_template={"method": "GET", "url": "https://example.com/${missing}"},
            variables={},
            request_func=request_func,
        )
        self.assertFalse(result.passed)
        self.assertIsInstance(result.exception, UnresolvedVariableError)
        self.assertIn("missing", result.errors[0])
        request_func.assert_not_called()

    def test_shared_executor_extracts_validates_and_updates_variables(self):
        variables = {"member_id": 123}
        request_func = Mock(return_value=FakeResponse({"data": {"id": 123}}))
        result = execute_api_step(
            request_template={
                "method": "GET",
                "url": "https://example.com/member/${member_id}",
            },
            extract={"result_id": ["json", "$.data.id", 0]},
            validate={"equals": {"ID一致": ["$.data.id", "${member_id}"]}},
            variables=variables,
            request_func=request_func,
        )
        self.assertTrue(result.passed)
        self.assertEqual(variables["result_id"], 123)
        self.assertEqual(result.request["url"], "https://example.com/member/123")
        self.assertEqual(result.assertions[0]["passed"], True)

    def test_legacy_variable_syntax_fails_with_migration_hint(self):
        request_func = Mock()
        result = execute_api_step(
            request_template={"method": "GET", "url": "https://example.com/$member_id"},
            variables={"member_id": 123},
            request_func=request_func,
        )
        self.assertFalse(result.passed)
        self.assertIsInstance(result.exception, UnresolvedVariableError)
        self.assertIn("${member_id}", result.errors[0])
        request_func.assert_not_called()

    def test_full_variable_expression_preserves_original_type(self):
        request_func = Mock(return_value=FakeResponse({"ok": True}))
        result = execute_api_step(
            request_template={
                "method": "POST",
                "url": "https://example.com/member",
                "json": {"member_id": "${member_id}", "enabled": "{{enabled}}"},
            },
            variables={"member_id": 123, "enabled": True},
            request_func=request_func,
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.request["json"], {"member_id": 123, "enabled": True})

    def test_malformed_current_syntax_fails_before_request(self):
        request_func = Mock()
        result = execute_api_step(
            request_template={"method": "GET", "url": "https://example.com/${member_id"},
            variables={"member_id": 123},
            request_func=request_func,
        )
        self.assertFalse(result.passed)
        self.assertIsInstance(result.exception, UnresolvedVariableError)
        self.assertIn("${变量名}", result.errors[0])
        request_func.assert_not_called()


class NativeReportBodyPreviewTests(unittest.TestCase):
    def test_large_unicode_body_is_limited_to_100kb_and_ends_with_ellipsis(self):
        preview = _response_body_preview("中" * NATIVE_RESPONSE_BODY_PREVIEW_BYTES)
        self.assertLessEqual(len(preview.encode("utf-8")), NATIVE_RESPONSE_BODY_PREVIEW_BYTES)
        self.assertTrue(preview.endswith("..."))

    def test_small_body_is_not_modified(self):
        self.assertEqual(_response_body_preview("正常响应"), "正常响应")


if __name__ == "__main__":
    unittest.main()
