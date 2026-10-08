"""无网络动态函数服务，通过 Unix Socket 接收任务并为每次调用启动子进程。"""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import struct
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

MAX_REQUEST_BYTES = 2_000_000
MAX_RESPONSE_BYTES = 1_100_000


def _receive(connection, size):
    data = bytearray()
    while len(data) < size:
        chunk = connection.recv(min(65536, size - len(data)))
        if not chunk:
            raise ConnectionError("动态函数请求不完整。")
        data.extend(chunk)
    return bytes(data)


def run_request(payload):
    timeout = max(1, min(10, int(payload.get("timeout_seconds") or 3)))
    runner = Path(__file__).with_name("function_sandbox.py")
    with tempfile.TemporaryDirectory(prefix="dynamic-function-") as directory:
        try:
            completed = subprocess.run([sys.executable, "-I", "-S", str(runner)], input=json.dumps(payload, ensure_ascii=False).encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=directory, env={}, timeout=timeout + 1, check=False)
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"函数执行超过 {timeout} 秒，已终止。"}
    if completed.returncode < 0:
        return {"ok": False, "error": "函数执行超过 CPU 或内存限制，已终止。"}
    if completed.returncode != 0:
        return {"ok": False, "error": "函数执行器异常退出。"}
    try:
        return json.loads(completed.stdout[:MAX_RESPONSE_BYTES].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"ok": False, "error": "函数执行器返回了无效结果。"}


def serve(socket_path):
    path = Path(socket_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path)); os.chmod(path, 0o660); server.listen(32)
    stopping = False
    def stop(*_):
        nonlocal stopping
        stopping = True
        server.close()
    signal.signal(signal.SIGTERM, stop); signal.signal(signal.SIGINT, stop)
    def handle(connection):
        with connection:
            try:
                size = struct.unpack("!I", _receive(connection, 4))[0]
                if size > MAX_REQUEST_BYTES:
                    raise ValueError("动态函数请求超过 2 MB。")
                response = run_request(json.loads(_receive(connection, size).decode("utf-8")))
            except Exception as exc:
                response = {"ok": False, "error": str(exc)}
            data = json.dumps(response, ensure_ascii=False).encode("utf-8")
            connection.sendall(struct.pack("!I", len(data)) + data)
    executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="dynamic-function")
    try:
        while not stopping:
            try:
                connection, _ = server.accept()
            except OSError:
                break
            executor.submit(handle, connection)
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--socket", required=True)
    serve(parser.parse_args().socket)
