"""Helix WEB 请求签名兼容。

网页端会在 Axios 拦截器中对最终 JSON 字符串签名。cURL 导入平台后，
时间戳和 nonce 不能继续复用，同时请求体必须保持 JSON.stringify 的紧凑格式。
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import string
import time
from urllib.parse import parse_qsl, urlsplit

_SIGNED_HEADER_NAMES = {"x-signature", "x-nonce", "x-timestamp"}
_NONCE_ALPHABET = string.ascii_letters + string.digits
# MXN WEB 0.2.277 初始化签名 Store 时使用的默认值。浏览器抓包中的签名可用
# 该值完整复算；/_secret 返回的是轮换值，但当前 WEB 请求发出前并未切换到它。
_WEB_DEFAULT_SECRET = "9697761f6c77"


def _header_key(headers, name):
    return next((key for key in headers if str(key).lower() == name), None)


def _javascript_string(value):
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (list, tuple)):
        return ",".join(_javascript_string(item) for item in value)
    return str(value)


def _query_string(url, params):
    values = {}
    for key, value in parse_qsl(urlsplit(url).query, keep_blank_values=True):
        values[key] = value
    for key, value in (params or {}).items():
        values[str(key)] = value
    return "&".join(
        sorted(f"{key}={_javascript_string(value)}" for key, value in values.items())
    )


def _secret_for_url(url):
    return _WEB_DEFAULT_SECRET


def prepare_helix_signed_request(method, url, headers=None, params=None, json_body=None, data=None):
    """按 Helix 网页端算法刷新签名，并返回最终请求头与请求体。"""
    headers = dict(headers or {})
    parsed = urlsplit(url)
    header_names = {str(key).lower() for key in headers}
    # 仅处理从 Helix WEB cURL 导入、且明确带有三项签名头的请求。
    if not parsed.hostname or not parsed.hostname.endswith("helix.city"):
        return headers, data, json_body
    if not _SIGNED_HEADER_NAMES.issubset(header_names):
        return headers, data, json_body

    compact_body = None
    body_hash_source = ""
    if json_body is not None:
        compact_body = json.dumps(json_body, ensure_ascii=False, separators=(",", ":"))
        body_hash_source = compact_body
    elif data is not None:
        body_hash_source = data.decode("utf-8") if isinstance(data, bytes) else str(data)

    timestamp = int(time.time())
    nonce = "".join(secrets.choice(_NONCE_ALPHABET) for _ in range(6))
    body_hash = hashlib.md5(body_hash_source.encode("utf-8")).hexdigest()
    canonical = "\n".join((
        str(timestamp),
        nonce,
        str(method or "").upper(),
        parsed.path or "",
        _query_string(url, params),
        body_hash,
    ))
    signature = hmac.new(
        _secret_for_url(url).encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    replacements = {
        "x-signature": signature,
        "x-nonce": nonce,
        "x-timestamp": str(timestamp),
    }
    for name, value in replacements.items():
        headers[_header_key(headers, name) or name] = value

    # 签名和实际发送必须使用同一份 JSON.stringify 结果。
    if compact_body is not None:
        return headers, compact_body, None
    return headers, data, json_body
