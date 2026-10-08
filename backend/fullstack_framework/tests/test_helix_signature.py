import hashlib
import hmac
import json
from unittest.mock import patch

from django.test import SimpleTestCase

from fullstack_framework.commons.helix_signature import prepare_helix_signed_request


class HelixSignatureTests(SimpleTestCase):
    @patch("fullstack_framework.commons.helix_signature._secret_for_url", return_value="test-secret")
    @patch("fullstack_framework.commons.helix_signature.secrets.choice", side_effect=list("Ab12Cd"))
    @patch("fullstack_framework.commons.helix_signature.time.time", return_value=1789715191)
    def test_refreshes_signature_and_uses_compact_json(self, _time, _choice, _secret):
        headers, data, json_body = prepare_helix_signed_request(
            "post",
            "https://api-test1-mx.helix.city/api/v1/pay/deposit",
            headers={
                "X-Signature": "old",
                "X-Nonce": "old",
                "X-Timestamp": "1",
                "Content-Type": "application/json;charset=UTF-8",
            },
            json_body={
                "amount": "10",
                "paymentChannelId": 4,
                "referer": "https://www-test1-mx.helix.city/en",
            },
        )

        expected_body = json.dumps(
            {
                "amount": "10",
                "paymentChannelId": 4,
                "referer": "https://www-test1-mx.helix.city/en",
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        body_hash = hashlib.md5(expected_body.encode()).hexdigest()
        canonical = "\n".join((
            "1789715191", "Ab12Cd", "POST", "/api/v1/pay/deposit", "", body_hash,
        ))
        expected_signature = hmac.new(
            b"test-secret", canonical.encode(), hashlib.sha256,
        ).hexdigest()

        self.assertEqual(data, expected_body)
        self.assertIsNone(json_body)
        self.assertEqual(headers["X-Nonce"], "Ab12Cd")
        self.assertEqual(headers["X-Timestamp"], "1789715191")
        self.assertEqual(headers["X-Signature"], expected_signature)

    def test_does_not_touch_unsigned_requests(self):
        headers = {"Authorization": "token"}
        result = prepare_helix_signed_request(
            "POST", "https://example.com/api", headers=headers, json_body={"a": 1},
        )
        self.assertEqual(result, (headers, None, {"a": 1}))
