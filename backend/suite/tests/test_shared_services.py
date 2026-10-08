from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied

from Tesla.ssh import configured_ssh_client, ssh_connection_options
from project.access import save_project_asset_update
from suite.notifications import deliver_notification, notification_payload


class SharedServicesTests(SimpleTestCase):
    def test_notification_protocol_and_markdown_are_preserved(self):
        self.assertEqual(notification_payload("lark", "a\nb"), {"msg_type": "text", "content": {"text": "a\nb"}})
        self.assertEqual(notification_payload("wecom", "a\nb")["markdown"]["content"], "a\n> b")
        self.assertEqual(notification_payload("wecom", "a\nb", markdown_separator="  \n")["markdown"]["content"], "a  \nb")

    @patch("suite.notifications.requests.post")
    def test_business_error_is_not_recorded_as_success(self, post):
        channel = SimpleNamespace(platform="wecom", webhook_url="https://example.com/hook")
        post.return_value = SimpleNamespace(ok=True, status_code=200, text="denied", json=lambda: {"errcode": 40001})
        delivery = Mock(status="failed")
        deliver_notification(channel, {}, delivery, timeout=10)
        self.assertEqual(delivery.status, "failed")
        self.assertIn("40001", delivery.response_summary)
        post.assert_called_once_with(channel.webhook_url, json={}, timeout=10)

    @patch("suite.notifications.requests.post")
    def test_success_and_network_failure_are_saved(self, post):
        channel = SimpleNamespace(platform="lark", webhook_url="https://example.com/hook")
        post.return_value = SimpleNamespace(ok=True, status_code=200, text="ok", json=lambda: {"code": 0})
        delivery = Mock(status="failed")
        deliver_notification(channel, {}, delivery)
        self.assertEqual(delivery.status, "sent")
        delivery.save.assert_called_once()
        post.side_effect = requests.Timeout("x" * 700)
        failed = Mock(status="failed")
        deliver_notification(channel, {}, failed)
        self.assertEqual(failed.status, "failed")
        self.assertEqual(len(failed.response_summary), 500)
        failed.save.assert_called_once()

    def test_strict_ssh_never_uses_auto_add(self):
        paramiko = Mock()
        client = configured_ssh_client(paramiko, True)
        client.load_system_host_keys.assert_called_once()
        client.set_missing_host_key_policy.assert_called_once_with(paramiko.RejectPolicy.return_value)
        paramiko.AutoAddPolicy.assert_not_called()
        options = ssh_connection_options("host", 2222, "user", 8)
        self.assertFalse(options["look_for_keys"])
        self.assertFalse(options["allow_agent"])
        self.assertEqual(options["banner_timeout"], 8)

    @patch("project.access.require_project_access")
    def test_asset_transfer_rejects_inaccessible_destination(self, require):
        require.side_effect = [None, PermissionDenied("denied")]
        source, destination, user = object(), object(), object()
        serializer = Mock(validated_data={"project": destination})
        with self.assertRaises(PermissionDenied):
            save_project_asset_update(user, SimpleNamespace(project=source), serializer)
        serializer.save.assert_not_called()
        self.assertEqual([c.args for c in require.call_args_list], [(user, source), (user, destination)])

    @patch("project.access.require_project_access", side_effect=PermissionDenied("denied"))
    def test_asset_update_rejects_inaccessible_source(self, require):
        serializer = Mock(validated_data={})
        with self.assertRaises(PermissionDenied):
            save_project_asset_update(object(), SimpleNamespace(project=object()), serializer)
        serializer.save.assert_not_called()
