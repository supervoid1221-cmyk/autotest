"""动态函数语法校验与隔离执行入口。"""
import ast

ALLOWED_MODULES = ("time", "random", "hashlib", "datetime")
ALLOWED_BUILTINS = ("str", "int", "float", "bool", "len", "min", "max", "round", "range", "enumerate", "list", "dict", "tuple", "set", "abs", "isinstance")
ALLOWED_METHODS = ("hexdigest",)
ALLOWED_HELPERS = ("random_int", "random_string", "uuid", "timestamp", "date", "md5")
FORBIDDEN_NODES = (ast.ClassDef, ast.Lambda, ast.Global, ast.Nonlocal, ast.With, ast.AsyncWith, ast.Await, ast.Yield, ast.YieldFrom, ast.Delete)
FORBIDDEN_NAMES = {"breakpoint", "compile", "eval", "exec", "globals", "locals", "vars", "dir", "getattr", "setattr", "delattr", "input", "help", "memoryview", "object", "super", "type"}
MAX_CODE_LENGTH = 50_000
MAX_AST_NODES = 2_000


def validate_dynamic_code(value):
    """AST 仅负责输入校验；真正安全边界由独立执行器提供。"""
    value = str(value or "")
    if len(value) > MAX_CODE_LENGTH:
        raise ValueError(f"函数代码不能超过 {MAX_CODE_LENGTH} 个字符。")
    try:
        tree = ast.parse(value)
    except SyntaxError as exc:
        raise ValueError(f"函数代码语法错误：第 {exc.lineno or 0} 行。") from exc
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES:
        raise ValueError("函数代码结构过于复杂。")
    if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in nodes):
        raise ValueError("代码必须至少定义一个函数。")
    for node in nodes:
        if isinstance(node, FORBIDDEN_NODES):
            raise ValueError(f"函数代码不允许使用 {node.__class__.__name__}。")
        if isinstance(node, ast.Attribute) and str(node.attr).startswith("_"):
            raise ValueError("函数代码不允许访问下划线开头的属性。")
        if isinstance(node, ast.Name) and node.id in FORBIDDEN_NAMES:
            raise ValueError(f"函数代码不允许使用 {node.id}。")
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [alias.name.split(".")[0] for alias in node.names] if isinstance(node, ast.Import) else [(node.module or "").split(".")[0]]
            if any(module not in ALLOWED_MODULES for module in modules):
                raise ValueError("仅允许导入 time、random、hashlib、datetime。")
    return value


def function_names(code):
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return []
    return [node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def parse_dynamic_arguments(argument_text):
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


def execute_dynamic_function(codes, name, variables=None, args=None, kwargs=None, *, timeout_seconds=None, memory_mb=None):
    normalized_codes = [validate_dynamic_code(code) for code in codes]
    from .function_client import execute_isolated_function
    return execute_isolated_function({"codes": normalized_codes, "name": name, "variables": variables or {}, "args": list(args or ()), "kwargs": dict(kwargs or {}), "timeout_seconds": timeout_seconds, "memory_mb": memory_mb})


def whitelist():
    return {"modules": list(ALLOWED_MODULES), "builtins": list(ALLOWED_BUILTINS + ALLOWED_METHODS), "helpers": list(ALLOWED_HELPERS), "context": ["timestamp", "datetime", "variables"], "isolation": "function-worker", "network": "disabled"}
