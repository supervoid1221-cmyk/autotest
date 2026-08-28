import hashlib
import hmac
import re
import time
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import WebhookReplayNonce


HEADER_KEY = "HTTP_X_WEBHOOK_KEY"
HEADER_TIMESTAMP = "HTTP_X_WEBHOOK_TIMESTAMP"
HEADER_NONCE = "HTTP_X_WEBHOOK_NONCE"
HEADER_SIGNATURE = "HTTP_X_WEBHOOK_SIGNATURE"
_NONCE_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def build_webhook_signature(secret, path, timestamp, nonce, body=b""):
    """生成 POST Webhook 的稳定签名；调用方须使用完全相同的原始请求体。"""
    body_digest = hashlib.sha256(body or b"").hexdigest()
    canonical = f"POST\n{path}\n{timestamp}\n{nonce}\n{body_digest}".encode()
    return hmac.new(str(secret).encode(), canonical, hashlib.sha256).hexdigest()


def verify_and_consume_webhook_request(request, suite):
    """验证 Hook Key、时间戳与签名，并原子登记 Nonce 防止重复使用。"""
    supplied_key = str(request.META.get(HEADER_KEY) or "")
    timestamp_text = str(request.META.get(HEADER_TIMESTAMP) or "")
    nonce = str(request.META.get(HEADER_NONCE) or "")
    supplied_signature = str(request.META.get(HEADER_SIGNATURE) or "").lower()

    if not supplied_key or not hmac.compare_digest(supplied_key, suite.hook_key or ""):
        return False, "invalid"
    try:
        request_timestamp = int(timestamp_text)
    except (TypeError, ValueError):
        return False, "invalid"

    tolerance = int(getattr(settings, "WEBHOOK_SIGNATURE_TOLERANCE_SECONDS", 300))
    if abs(int(time.time()) - request_timestamp) > tolerance:
        return False, "expired"
    if not _NONCE_PATTERN.fullmatch(nonce) or not re.fullmatch(r"[0-9a-fA-F]{64}", supplied_signature):
        return False, "invalid"

    expected_signature = build_webhook_signature(
        suite.hook_key, request.path, timestamp_text, nonce, request.body
    )
    if not hmac.compare_digest(supplied_signature, expected_signature):
        return False, "invalid"

    nonce_digest = hashlib.sha256(nonce.encode()).hexdigest()
    try:
        with transaction.atomic():
            WebhookReplayNonce.objects.create(
                suite=suite,
                nonce_digest=nonce_digest,
                request_timestamp=request_timestamp,
            )
    except IntegrityError:
        return False, "replayed"

    # 只保留大于签名窗口两倍的少量审计数据；过期请求本身已无法通过时间校验。
    retention_seconds = max(tolerance * 2, 600)
    WebhookReplayNonce.objects.filter(
        created_at__lt=timezone.now() - timedelta(seconds=retention_seconds)
    ).delete()
    return True, "ok"
