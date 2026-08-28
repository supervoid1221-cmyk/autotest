import json
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from project.models import Environment, Project
from suite.models import Suite, WebhookReplayNonce
from suite.notifications import validate_notification_response
from suite.webhook_security import build_webhook_signature


class SuiteWebhookSecurityTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user("webhook-owner")
        project = Project.objects.create(name="Webhook 项目", intro="", pm=owner)
        environment = Environment.objects.create(
            project=project, name="Dev", base_url="https://example.com"
        )
        self.suite = Suite.objects.create(
            name="Webhook 套件",
            environment=environment,
            run_type=Suite.RunType.WebHook,
            hook_key="test-hook-secret",
        )
        self.path = f"/api/suite/suite/{self.suite.id}/webhook/"
        self.client = APIClient()

    def signed_headers(self, body, timestamp=None, nonce="nonce-12345678"):
        timestamp = str(timestamp if timestamp is not None else int(time.time()))
        signature = build_webhook_signature(
            self.suite.hook_key, self.path, timestamp, nonce, body
        )
        return {
            "HTTP_X_WEBHOOK_KEY": self.suite.hook_key,
            "HTTP_X_WEBHOOK_TIMESTAMP": timestamp,
            "HTTP_X_WEBHOOK_NONCE": nonce,
            "HTTP_X_WEBHOOK_SIGNATURE": signature,
        }

    def test_get_is_not_allowed(self):
        response = self.client.get(f"{self.path}?key={self.suite.hook_key}")
        self.assertEqual(response.status_code, 405)

    def test_query_key_does_not_authenticate_post(self):
        response = self.client.post(f"{self.path}?key={self.suite.hook_key}", {}, format="json")
        self.assertEqual(response.status_code, 401)

    @patch("suite.models.Suite.run", return_value=SimpleNamespace(id=987654))
    def test_valid_signed_post_starts_execution(self, run):
        body = json.dumps({"source": "ci"}, separators=(",", ":")).encode()
        response = self.client.generic(
            "POST",
            self.path,
            data=body,
            content_type="application/json",
            **self.signed_headers(body),
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["result_id"], 987654)
        self.assertEqual(WebhookReplayNonce.objects.count(), 1)
        run.assert_called_once_with(executor_name="Webhook")

    @patch("suite.models.Suite.run", return_value=SimpleNamespace(id=987654))
    def test_same_nonce_cannot_be_replayed(self, run):
        body = b"{}"
        headers = self.signed_headers(body)
        first = self.client.generic("POST", self.path, data=body, content_type="application/json", **headers)
        second = self.client.generic("POST", self.path, data=body, content_type="application/json", **headers)
        self.assertEqual(first.status_code, 202)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(run.call_count, 1)

    @override_settings(WEBHOOK_SIGNATURE_TOLERANCE_SECONDS=60)
    def test_expired_timestamp_is_rejected(self):
        body = b"{}"
        headers = self.signed_headers(body, timestamp=int(time.time()) - 61)
        response = self.client.generic(
            "POST", self.path, data=body, content_type="application/json", **headers
        )
        self.assertEqual(response.status_code, 401)
        self.assertFalse(WebhookReplayNonce.objects.exists())


class NotificationBusinessCodeTests(TestCase):
    @staticmethod
    def response(payload, status_code=200):
        response = Mock()
        response.ok = 200 <= status_code < 400
        response.status_code = status_code
        response.json.return_value = payload
        response.text = json.dumps(payload, ensure_ascii=False)
        return response

    def test_lark_http_200_with_error_code_is_failure(self):
        succeeded, detail = validate_notification_response(
            "lark", self.response({"code": 19001, "msg": "invalid token"})
        )
        self.assertFalse(succeeded)
        self.assertIn("19001", detail)

    def test_wecom_http_200_with_error_code_is_failure(self):
        succeeded, detail = validate_notification_response(
            "wecom", self.response({"errcode": 40014, "errmsg": "invalid token"})
        )
        self.assertFalse(succeeded)
        self.assertIn("40014", detail)

    def test_provider_zero_business_codes_are_success(self):
        self.assertTrue(validate_notification_response("lark", self.response({"code": 0}))[0])
        self.assertTrue(validate_notification_response("wecom", self.response({"errcode": 0}))[0])
