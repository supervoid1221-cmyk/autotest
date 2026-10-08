from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from project.models import Environment


class EnvironmentAuthenticationUnitTests(SimpleTestCase):
    def _environment(self):
        return Environment(
            project_id=1,
            name="Test",
            base_url="https://api-test1-mx.helix.city",
            auth_enabled=True,
            login_url="/api/v1/auth/login",
            login_method="POST",
            login_json={"identifier": "user", "password": "password"},
            token_jsonpath="$.data.token.authorization",
        )

    @patch("project.models.requests.request")
    def test_http_200_business_error_is_reported_before_jsonpath_error(self, request):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"code": 1099, "msg": "Captcha required", "data": None}
        request.return_value = response

        with self.assertRaisesRegex(
            ValueError, "自动登录失败（业务码 1099）：Captcha required"
        ):
            self._environment()._login_and_extract_token()

    @patch("project.models.requests.request")
    def test_extracts_api_authorization_token(self, request):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "code": 0,
            "data": {"token": {"authorization": "header.payload.signature"}},
        }
        request.return_value = response

        self.assertEqual(
            self._environment()._login_and_extract_token(),
            "header.payload.signature",
        )
