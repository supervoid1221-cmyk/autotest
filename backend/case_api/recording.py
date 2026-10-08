"""浏览器网络录制数据的标准化、脱敏与 HAR 兼容处理。"""
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import parse_qs, urlsplit


SENSITIVE_NAME = re.compile(r"(?:authorization|token|secret|password|passwd|cookie|api[-_]?key|session)", re.I)
# HTTP/2 的 :authority、:method、:path、:scheme 是伪请求头，不能作为
# requests 的普通 Header 发送；浏览器运行时信息也不应持久化为接口配置。
DROP_HEADER = re.compile(r"^(?::|host|content-length|connection|accept-encoding|cookie|set-cookie|origin|referer|user-agent|proxy-connection|sec-)", re.I)
# 这些头由客户端按当次请求生成，录制值在回放时已过期，并且会触发网关的防重放校验。
VOLATILE_HEADER_NAMES = frozenset({"x-timestamp", "x-nonce", "x-signature"})


def _as_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _headers(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        entries = value.items()
    elif isinstance(value, list):
        entries = ((item.get("name"), item.get("value")) for item in value if isinstance(item, dict))
    else:
        entries = []
    return {str(key): str(item) for key, item in entries if key and item is not None}


def sanitize_recorded_headers(value: Any) -> dict[str, str]:
    """只保留可安全回放的录制请求头。

    解析 HAR 和导入落库都必须调用该函数，避免客户端绕过解析阶段后
    把一次性签名、时间戳或认证信息重新写入接口配置。
    """
    return {
        key: _redact(item, key)
        for key, item in _headers(value).items()
        if not DROP_HEADER.search(key)
        and not SENSITIVE_NAME.search(key)
        and key.strip().lower() not in VOLATILE_HEADER_NAMES
    }


def _redact(value: Any, key: str = "") -> Any:
    if SENSITIVE_NAME.search(key):
        return "${token}" if re.search(r"token|authorization|session", key, re.I) else "${masked}"
    if isinstance(value, dict):
        return {str(name): _redact(item, str(name)) for name, item in value.items()}
    if isinstance(value, list):
        return [_redact(item, key) for item in value]
    return value


def _name_from_path(path: str) -> str:
    part = next((item for item in reversed(path.split("/")) if item), "录制接口")
    return re.sub(r"[-_]", " ", part)[:32] or "录制接口"


def _body_to_object(text: Any, content_type: str) -> tuple[dict[str, Any], str]:
    if isinstance(text, (dict, list)):
        return (_redact(text) if isinstance(text, dict) else {"items": _redact(text)}, "json")
    text = str(text or "").strip()
    if not text:
        return {}, "json"
    try:
        value = json.loads(text)
        return (_redact(value) if isinstance(value, dict) else {"items": _redact(value)}, "json")
    except json.JSONDecodeError:
        pass
    if "x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        return _redact({key: values[-1] if len(values) == 1 else values for key, values in parse_qs(text, keep_blank_values=True).items()}), "data"
    return {"raw": text[:20000]}, "data"


def normalize_record(raw: dict[str, Any], index: int = 0) -> dict[str, Any]:
    """兼容 DevTools HAR entry 与扩展/前端发送的简化请求结构。"""
    request = raw.get("request") if isinstance(raw.get("request"), dict) else raw
    response = raw.get("response") if isinstance(raw.get("response"), dict) else {}
    method = str(request.get("method") or raw.get("method") or "GET").upper()
    original_url = str(request.get("url") or raw.get("url") or "")
    parsed = urlsplit(original_url)
    url = parsed.path or "/"
    params = {key: values[-1] if len(values) == 1 else values for key, values in parse_qs(parsed.query, keep_blank_values=True).items()}
    headers = _headers(request.get("headers") or raw.get("headers"))
    content_type = next((value for key, value in headers.items() if key.lower() == "content-type"), "").lower()
    post_data = request.get("postData") or raw.get("postData") or raw.get("body") or raw.get("data")
    if isinstance(post_data, dict) and "text" in post_data:
        post_data = post_data.get("text")
    body, body_type = _body_to_object(post_data, content_type)
    # 认证信息由项目的“环境与认证”统一注入；不能保存一次性的
    # Authorization/Token，否则会覆盖运行期认证并导致回放失败。
    kept_headers = sanitize_recorded_headers(headers)
    status_code = int(response.get("status") or raw.get("status_code") or raw.get("status") or 0)
    response_content = response.get("content", {}) if isinstance(response.get("content"), dict) else {}
    response_body = raw.get("response_body") or raw.get("responseBody") or response_content.get("text", "")
    tokenized_headers = [key for key in headers if SENSITIVE_NAME.search(key)]
    record = {
        "record_id": str(raw.get("_id") or raw.get("id") or index), "selected": True,
        "name": str(raw.get("name") or _name_from_path(url)), "method": method, "url": url,
        "original_url": original_url, "base_url": f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else "",
        "headers": kept_headers, "params": _redact(params), "data": body if body_type == "data" else {},
        "json": body if body_type == "json" else {}, "status_code": status_code,
        "auth_variables": [{"header": key, "variable": "${token}"} for key in tokenized_headers],
        "duration_ms": int(raw.get("duration_ms") or raw.get("time") or 0),
        "response_preview": str(response_body or "")[:20000],
        "auth_suggestion": "检测到认证信息，已替换为变量占位符；保存后建议由“环境与认证”统一注入。" if tokenized_headers else "",
        "recommended_assertions": {"equals": {f"HTTP 状态码相等 {status_code}": ["$.status_code", str(status_code)]}} if 200 <= status_code < 400 else {},
    }
    return record


def parse_recording_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    har = payload.get("har") or payload.get("log")
    if isinstance(har, str):
        try:
            har = json.loads(har)
        except json.JSONDecodeError:
            har = None
    if isinstance(har, dict):
        har = har.get("log", har)
        records = har.get("entries", []) if isinstance(har, dict) else []
    else:
        records = payload.get("records", [])
    return [normalize_record(item, index) for index, item in enumerate(records) if isinstance(item, dict) and (item.get("request") or item.get("url"))]
