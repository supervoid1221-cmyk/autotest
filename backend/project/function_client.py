"""动态函数隔离执行器客户端。"""
import json
import socket
import struct
from django.conf import settings


def _receive(connection, size):
    data = bytearray()
    while len(data) < size:
        chunk = connection.recv(min(65536, size - len(data)))
        if not chunk:
            raise ConnectionError("动态函数执行器响应不完整。")
        data.extend(chunk)
    return bytes(data)


def execute_isolated_function(payload):
    timeout = max(1, min(10, int(payload.get("timeout_seconds") or settings.DYNAMIC_FUNCTION_TIMEOUT_SECONDS)))
    payload["timeout_seconds"] = timeout
    payload["memory_mb"] = max(64, min(512, int(payload.get("memory_mb") or settings.DYNAMIC_FUNCTION_MEMORY_MB)))
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(data) > 2_000_000:
        raise ValueError("动态函数输入数据超过 2 MB。")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(timeout + 2)
            connection.connect(str(settings.DYNAMIC_FUNCTION_SOCKET))
            connection.sendall(struct.pack("!I", len(data)) + data)
            size = struct.unpack("!I", _receive(connection, 4))[0]
            if size > 1_100_000:
                raise ValueError("动态函数返回数据超过限制。")
            response = json.loads(_receive(connection, size).decode("utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if not settings.DYNAMIC_FUNCTION_ALLOW_LOCAL_FALLBACK:
            raise ValueError("动态函数执行器不可用，请联系管理员。") from exc
        from .function_worker import run_request
        response = run_request(payload)
    if not response.get("ok"):
        raise ValueError(str(response.get("error") or "动态函数执行失败。"))
    return response.get("result")
