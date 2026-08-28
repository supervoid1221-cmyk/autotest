"""动态函数的受限执行环境，供正式运行与页面调试共用。"""
import builtins
import ast
import hashlib
import inspect
import random
import re
import string
import time
import uuid
from datetime import datetime


ALLOWED_MODULES = ("time", "random", "hashlib", "datetime")
ALLOWED_BUILTINS = ("str", "int", "float", "bool", "len", "min", "max", "round", "range", "enumerate", "list", "dict", "tuple", "set", "abs")
ALLOWED_HELPERS = ("random_int", "random_string", "uuid", "timestamp", "date", "md5")
FORBIDDEN_CODE = ("__import__", "exec(", "eval(", "open(", "os.", "subprocess", "socket")


def validate_dynamic_code(value):
    if any(item in value for item in FORBIDDEN_CODE):
        raise ValueError("函数代码包含不允许的操作。")
    if not re.search(r"def\s+[A-Za-z_]\w*\s*\(", value):
        raise ValueError("代码必须至少定义一个函数。")
    imports = re.findall(r"^\s*import\s+([A-Za-z_]\w*)|^\s*from\s+([A-Za-z_]\w*)", value, re.M)
    if any((left or right) not in ALLOWED_MODULES for left, right in imports):
        raise ValueError("仅允许导入 time、random、hashlib、datetime。")
    return value


def function_names(code):
    return re.findall(r"^\s*def\s+([A-Za-z_]\w*)\s*\(", code or "", re.M)


def parse_dynamic_arguments(argument_text):
    """安全解析 ${func("text", count=1)} 中的字面量参数。"""
    if not str(argument_text or "").strip():
        return (), {}
    try:
        call = ast.parse(f"_({argument_text})", mode="eval").body
        if not isinstance(call, ast.Call) or call.args and any(isinstance(item, ast.Starred) for item in call.args):
            raise ValueError
        args = tuple(ast.literal_eval(item) for item in call.args)
        kwargs = {item.arg: ast.literal_eval(item.value) for item in call.keywords if item.arg}
        if len(kwargs) != len(call.keywords):
            raise ValueError
        return args, kwargs
    except (SyntaxError, ValueError, TypeError) as exc:
        raise ValueError("函数参数仅支持字符串、数字、布尔值、列表、字典与关键字参数。") from exc


def execute_dynamic_function(codes, name, variables=None, args=None, kwargs=None):
    """执行指定函数；仅提供白名单模块、内置函数及平台辅助函数。"""
    allowed_modules = {
        "time": __import__("time"), "random": random, "hashlib": hashlib, "datetime": __import__("datetime"),
    }

    def safe_import(module, *args, **kwargs):
        if module.split(".")[0] not in allowed_modules:
            raise ImportError(f"不允许导入模块：{module}")
        return builtins.__import__(module, *args, **kwargs)

    safe_builtins = {"__import__": safe_import}
    safe_builtins.update({name: getattr(builtins, name) for name in ALLOWED_BUILTINS})
    safe_globals = {
        "__builtins__": safe_builtins,
        "random_int": lambda left, right: random.randint(int(left), int(right)),
        "random_string": lambda length=8: "".join(random.choice(string.ascii_letters + string.digits) for _ in range(int(length))),
        "uuid": lambda: str(uuid.uuid4()),
        "timestamp": lambda: int(time.time()),
        "date": lambda fmt="%Y-%m-%d": datetime.now().strftime(fmt),
        "md5": lambda value: hashlib.md5(str(value).encode("utf-8")).hexdigest(),
    }
    scope = safe_globals
    for code in codes:
        validate_dynamic_code(code)
        exec(code, safe_globals, scope)
    function = scope.get(name)
    if not callable(function):
        raise ValueError(f"动态函数「{name}」未定义可执行函数")
    context = {"timestamp": int(time.time()), "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "variables": variables or {}}
    parameters = list(inspect.signature(function).parameters.values())
    required = [
        parameter for parameter in parameters
        if parameter.default is inspect.Parameter.empty
        and parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
    ]
    # 只有显式声明必填 context 时才注入上下文；例如 date(format="...")
    # 这类带默认参数的函数应直接调用，使其默认值生效。
    args, kwargs = tuple(args or ()), dict(kwargs or {})
    if not required:
        return function(*args, **kwargs)
    if len(required) == 1 and required[0].name == "context":
        return function(context, *args, **kwargs)
    names = "、".join(parameter.name for parameter in required)
    raise ValueError(f"动态函数仅支持无必填参数，或一个必填 context 参数；当前必填参数：{names}")


def whitelist():
    return {
        "modules": list(ALLOWED_MODULES),
        "builtins": list(ALLOWED_BUILTINS),
        "helpers": list(ALLOWED_HELPERS),
        "context": ["timestamp", "datetime", "variables"],
    }
