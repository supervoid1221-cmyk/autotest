"""单次动态函数子进程。仅通过 stdin/stdout 接收和返回 JSON。"""
import ast
import builtins
import hashlib
import inspect
import json
import os
import random
import resource
import string
import sys
import time
import uuid
from datetime import datetime

ALLOWED_MODULES = {"time", "random", "hashlib", "datetime"}
ALLOWED_BUILTINS = ("str", "int", "float", "bool", "len", "min", "max", "round", "range", "enumerate", "list", "dict", "tuple", "set", "abs", "isinstance")
FORBIDDEN_NAMES = {"breakpoint", "compile", "eval", "exec", "globals", "locals", "vars", "dir", "getattr", "setattr", "delattr", "input", "help", "memoryview", "object", "super", "type"}
FORBIDDEN_NODES = (ast.ClassDef, ast.Lambda, ast.Global, ast.Nonlocal, ast.With, ast.AsyncWith, ast.Await, ast.Yield, ast.YieldFrom, ast.Delete)


def validate(code):
    tree = ast.parse(code)
    nodes = list(ast.walk(tree))
    if len(code) > 50_000 or len(nodes) > 2_000:
        raise ValueError("函数代码超过执行器限制。")
    for node in nodes:
        if isinstance(node, FORBIDDEN_NODES):
            raise ValueError(f"不允许使用 {node.__class__.__name__}。")
        if isinstance(node, ast.Attribute) and str(node.attr).startswith("_"):
            raise ValueError("不允许访问下划线开头的属性。")
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise ValueError(f"不允许使用 {node.id}。")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [a.name.split(".")[0] for a in node.names] if isinstance(node, ast.Import) else [(node.module or "").split(".")[0]]
            if any(module not in ALLOWED_MODULES for module in modules):
                raise ValueError("导入模块不在白名单。")


def apply_limits(timeout_seconds, memory_mb):
    cpu = max(1, min(10, int(timeout_seconds)))
    memory = max(64, min(512, int(memory_mb))) * 1024 * 1024
    for kind, value in ((resource.RLIMIT_CPU, cpu), (resource.RLIMIT_AS, memory), (resource.RLIMIT_FSIZE, 1024 * 1024), (resource.RLIMIT_NOFILE, 16), (resource.RLIMIT_NPROC, 0)):
        try:
            resource.setrlimit(kind, (value, value))
        except (ValueError, OSError):
            pass


def execute(payload):
    apply_limits(payload.get("timeout_seconds") or 3, payload.get("memory_mb") or 128)
    os.environ.clear()
    modules = {"time": time, "random": random, "hashlib": hashlib, "datetime": sys.modules["datetime"]}
    def safe_import(module, *args, **kwargs):
        root = module.split(".")[0]
        if root not in ALLOWED_MODULES:
            raise ImportError(f"不允许导入模块：{module}")
        return modules[root]
    safe_builtins = {"__import__": safe_import, **{name: getattr(builtins, name) for name in ALLOWED_BUILTINS}}
    scope = {"__builtins__": safe_builtins, "random_int": lambda left, right: random.randint(int(left), int(right)), "random_string": lambda length=8: "".join(random.choice(string.ascii_letters + string.digits) for _ in range(int(length))), "uuid": lambda: str(uuid.uuid4()), "timestamp": lambda: int(time.time()), "date": lambda fmt="%Y-%m-%d": datetime.now().strftime(fmt), "md5": lambda value: hashlib.md5(str(value).encode("utf-8")).hexdigest()}
    for code in payload.get("codes") or []:
        validate(code)
        exec(compile(code, "<dynamic-function>", "exec"), scope, scope)
    function = scope.get(str(payload.get("name") or ""))
    if not callable(function):
        raise ValueError(f"动态函数「{payload.get('name')}」未定义可执行函数。")
    args, kwargs = list(payload.get("args") or []), dict(payload.get("kwargs") or {})
    context = {"timestamp": int(time.time()), "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "variables": payload.get("variables") or {}}
    signature = inspect.signature(function)
    parameters = list(signature.parameters.values())
    if "context" in kwargs:
        raise ValueError("context 由平台注入，不允许通过调用参数覆盖。")
    if parameters and parameters[0].name == "context":
        if parameters[0].kind is inspect.Parameter.KEYWORD_ONLY:
            kwargs["context"] = context
        elif parameters[0].kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
            args.insert(0, context)
    try:
        signature.bind(*args, **kwargs)
    except TypeError as exc:
        raise ValueError(f"函数调用参数不匹配：{exc}") from exc
    return function(*args, **kwargs)


def main():
    try:
        payload = json.loads(sys.stdin.buffer.read(2_000_001).decode("utf-8"))
        output = {"ok": True, "result": execute(payload)}
    except BaseException as exc:
        output = {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"}
    try:
        data = json.dumps(output, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError):
        data = json.dumps({"ok": False, "error": "函数返回值必须是可序列化的 JSON 数据。"}, ensure_ascii=False).encode("utf-8")
    if len(data) > 1_000_000:
        data = json.dumps({"ok": False, "error": "函数返回数据超过 1 MB。"}, ensure_ascii=False).encode("utf-8")
    sys.stdout.buffer.write(data)


if __name__ == "__main__":
    main()
