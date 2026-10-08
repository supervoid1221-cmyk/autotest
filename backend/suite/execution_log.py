"""套件执行的平台级实时日志。

业务日志与 pytest 调试日志分开，避免向用户暴露本地路径、框架收集信息和敏感变量。
"""
from datetime import datetime
import json
from pathlib import Path
import re

from django.conf import settings
from account.tenant_runtime import tenant_path


LOG_FILE = Path("logs") / "execution.log"
JWT_PATTERN = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
SECRET_PATTERN = re.compile(
    r"(?i)(token|password|passwd|pwd|secret|authorization|cookie|api[_-]?key|access[_-]?key)"
    r"(['\"]?\s*[:=]\s*['\"]?)([^,\s'\"}]+)"
)
SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(token|password|passwd|pwd|secret|authorization|cookie|api[_-]?key|access[_-]?key|密钥|密码)"
)


def write_execution_log(message, level="INFO", base_path=None, tenant_id=None):
    if base_path:
        root = Path(base_path)
        path = root / LOG_FILE
    elif tenant_id:
        root = tenant_path(Path(settings.BASE_DIR) / "logs", tenant_id)
        path = root / "execution.log"
    else:
        root = Path.cwd()
        path = root / LOG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
    safe_message = sanitize_log_text(message)
    with path.open("a", encoding="utf-8") as output:
        output.write(f"[{timestamp}] [{str(level).upper()}] {safe_message}\n")
        output.flush()


def sanitize_log_text(content):
    """历史底层日志回退展示时也不允许暴露凭证。"""
    text = JWT_PATTERN.sub("***", str(content or ""))
    return SECRET_PATTERN.sub(lambda match: f"{match.group(1)}{match.group(2)}***", text)


def _safe_log_value(value, key="", depth=0):
    """递归清洗即将展示在实时日志中的请求数据。"""
    if key and SENSITIVE_KEY_PATTERN.search(str(key)):
        return "***"
    if depth >= 8:
        return "…"
    if isinstance(value, dict):
        return {
            str(child_key): _safe_log_value(child_value, child_key, depth + 1)
            for child_key, child_value in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_safe_log_value(item, key, depth + 1) for item in value]
    if isinstance(value, bytes):
        return f"<{len(value)} bytes>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return sanitize_log_text(value)


def format_log_payload(value, max_chars=4000):
    """将请求参数格式化为单行 JSON，避免敏感信息和超长内容污染日志。"""
    try:
        content = json.dumps(
            _safe_log_value(value),
            ensure_ascii=False,
            separators=(",", ":"),
            default=lambda item: sanitize_log_text(item),
        )
    except (TypeError, ValueError):
        content = sanitize_log_text(value)
    if len(content) <= max_chars:
        return content
    return f"{content[:max_chars]}…（内容已截断）"
