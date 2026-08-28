"""页面调试与 pytest 套件共用的接口步骤执行器。"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

import jsonpath
import yaml


logger = logging.getLogger(__name__)

VARIABLE_PATTERN = re.compile(
    r"(?:"
    r"\$\{\s*(?:(?P<dollar_function>[A-Za-z_]\w*)\s*\((?P<dollar_arguments>[^{}]*)\)|"
    r"(?P<dollar_variable>[\w.]+))\s*\}"
    r"|"
    r"\{\{\s*(?:(?P<brace_function>[A-Za-z_]\w*)\s*\((?P<brace_arguments>[^{}]*)\)|"
    r"(?P<brace_variable>[\w.]+))\s*\}\}"
    r")"
)
LEGACY_VARIABLE_PATTERN = re.compile(
    r"\$(?!ddt\{)(?P<plain>[A-Za-z_]\w*)"
)


class UnresolvedVariableError(ValueError):
    """请求或断言中存在无法解析的变量/函数表达式。"""


@dataclass
class StepExecutionResult:
    passed: bool
    request: dict = field(default_factory=dict)
    response: Any = None
    response_json: Any = None
    response_body: str = ""
    errors: list[str] = field(default_factory=list)
    assertions: list[dict] = field(default_factory=list)
    extracted: dict = field(default_factory=dict)
    attempts: list[dict] = field(default_factory=list)
    duration_seconds: float = 0
    exception: Exception | None = None


def run_dynamic_function(name, variables, arguments="", project_id=None):
    """执行启用的动态函数，供两种执行入口统一调用。"""
    try:
        from project.models import DynamicFunction
        from project.dynamic_functions import execute_dynamic_function, parse_dynamic_arguments

        queryset = DynamicFunction.objects.filter(enabled=True)
        if project_id:
            queryset = queryset.filter(projects__id=project_id)
        codes = list(queryset.distinct().order_by("id").values_list("code", flat=True))
        if not codes:
            raise ValueError("未配置可用的动态函数")
        args, kwargs = parse_dynamic_arguments(arguments)
        return execute_dynamic_function(codes, name, variables, args=args, kwargs=kwargs)
    except Exception as exc:
        raise ValueError(f"动态函数「{name}」执行失败：{exc}") from exc


def resolve_template_expression(match, variables, project_id=None):
    """解析单个 ${...} 或 {{...}} 表达式，并保留结果的原始类型。"""
    function_name = match.group("dollar_function") or match.group("brace_function")
    variable_name = (
        function_name
        or match.group("dollar_variable")
        or match.group("brace_variable")
    )
    arguments = match.group("dollar_arguments") or match.group("brace_arguments") or ""
    expression = match.group(0)
    if variable_name in variables and variables[variable_name] is not None:
        return variables[variable_name]

    if function_name or "." not in variable_name:
        try:
            value = run_dynamic_function(
                variable_name, variables, arguments, project_id
            )
        except Exception as exc:
            raise UnresolvedVariableError(
                f"表达式「{expression}」未解析：变量不存在，且未找到可执行的同名动态函数。"
            ) from exc
        if value is not None:
            return value

    raise UnresolvedVariableError(f"变量「{variable_name}」未定义，无法解析表达式「{expression}」。")


def substitute_text(content: str, variables=None, project_id=None, environment_name=None) -> str:
    """严格替换变量、动态函数和数据库函数；无法解析时立即失败。"""
    variables = variables or {}
    if "${execute_sql_" in content:
        if not project_id or not environment_name:
            raise UnresolvedVariableError("数据库函数缺少项目或执行环境上下文。")
        from project.database_functions import substitute_database_functions

        content = substitute_database_functions(content, variables, project_id, environment_name)
        if "${execute_sql_" in content:
            raise UnresolvedVariableError("数据库函数表达式未能完成解析。")

    legacy_match = LEGACY_VARIABLE_PATTERN.search(content)
    if legacy_match:
        expression = legacy_match.group(0)
        variable_name = legacy_match.group("plain")
        raise UnresolvedVariableError(
            f"变量表达式「{expression}」仍在使用旧语法，请优先改为「${{{variable_name}}}」，"
            f"也兼容「{{{{{variable_name}}}}}」。"
        )
    unmatched_content = VARIABLE_PATTERN.sub("", content)
    if "${" in unmatched_content or "{{" in unmatched_content or "}}" in unmatched_content:
        raise UnresolvedVariableError(
            "变量表达式格式不正确，请使用 ${变量名}（推荐）或 {{变量名}}。"
        )
    return VARIABLE_PATTERN.sub(
        lambda match: str(resolve_template_expression(match, variables, project_id)), content
    )


def substitute_data(value, variables=None, project_id=None, environment_name=None):
    """递归替换结构化请求数据；独占字段值的表达式保留原始类型。"""
    variables = variables or {}
    if isinstance(value, dict):
        return {
            substitute_text(key, variables, project_id, environment_name)
            if isinstance(key, str) else key:
            substitute_data(item, variables, project_id, environment_name)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            substitute_data(item, variables, project_id, environment_name)
            for item in value
        ]
    if not isinstance(value, str):
        return value
    match = VARIABLE_PATTERN.fullmatch(value)
    if match:
        return resolve_template_expression(match, variables, project_id)
    return substitute_text(value, variables, project_id, environment_name)


def extract_with_regex(source, expression, group_index):
    if isinstance(source, (dict, list)):
        source = yaml.safe_dump(source, allow_unicode=True)
    try:
        match = re.search(str(expression), str(source), re.S)
        if not match:
            return "no data"
        return match.group(int(group_index))
    except (re.error, IndexError, ValueError) as exc:
        raise ValueError(f"正则表达式或捕获组无效：{exc}") from exc


def extract_values(response, response_json, extract):
    values = {}
    for variable_name, expression in (extract or {}).items():
        if not isinstance(expression, list):
            raise ValueError(f"变量「{variable_name}」的数据提取配置必须为数组。")
        if expression and expression[0] == "re":
            if len(expression) != 4:
                raise ValueError(
                    f"变量「{variable_name}」的 re 提取格式应为 "
                    '["re", "text", "正则表达式", 分组序号]。'
                )
            source = response_json if expression[1] == "json" else getattr(response, expression[1], "")
            value = extract_with_regex(source, expression[2], expression[3])
        else:
            if len(expression) != 3:
                raise ValueError(
                    f"变量「{variable_name}」的 JSONPath 提取格式应为 "
                    '["json", "$.路径", 结果序号]。'
                )
            source = response_json if expression[0] == "json" else getattr(response, expression[0], response_json)
            matches = jsonpath.jsonpath(source, expression[1]) or []
            try:
                value = matches[int(expression[2])] if matches else "no data"
            except (IndexError, TypeError, ValueError) as exc:
                raise ValueError(f"变量「{variable_name}」的结果序号无效。") from exc
        values[variable_name] = value
    return values


def resolve_response_value(response, response_json, reference, variables=None):
    variables = variables or {}
    reference = str(reference)
    if reference.startswith("$"):
        context = {
            "status_code": response.status_code,
            "text": response.text,
            "json": response_json,
            "headers": dict(response.headers),
            "variables": variables,
        }
        values = jsonpath.jsonpath(context, reference) or []
        if not values and isinstance(response_json, (dict, list)):
            values = jsonpath.jsonpath(response_json, reference) or []
        return values[0] if values else "no data"
    return getattr(response, reference, variables.get(reference, "no data"))


def _equal(actual, expected):
    try:
        return Decimal(str(actual)) == Decimal(str(expected))
    except (InvalidOperation, ValueError):
        return str(actual) == str(expected)


def validate_response(response, response_json, validate, variables, project_id=None, environment_name=None):
    errors = [f"HTTP {response.status_code}"] if response.status_code >= 400 else []
    details = []
    for assertion_type, expressions in (validate or {}).items():
        for message, expression in (expressions or {}).items():
            if not isinstance(expression, list) or len(expression) < 2:
                raise ValueError(f"断言「{message}」配置格式不正确。")
            actual = resolve_response_value(response, response_json, expression[0], variables)
            expected = substitute_text(str(expression[1]), variables, project_id, environment_name)
            if assertion_type == "equals":
                passed = _equal(actual, expected)
            elif assertion_type == "not_equals":
                passed = not _equal(actual, expected)
            elif assertion_type in {"greater_than", "less_than"}:
                try:
                    actual_number = Decimal(str(actual))
                    expected_number = Decimal(str(expected))
                    passed = actual_number > expected_number if assertion_type == "greater_than" else actual_number < expected_number
                except (InvalidOperation, ValueError):
                    passed = False
            elif assertion_type == "contains":
                passed = str(expected) in str(actual)
            else:
                raise ValueError(f"不支持的断言方式：{assertion_type}")
            details.append({
                "type": assertion_type,
                "actual_path": expression[0],
                "actual": str(actual),
                "expected": str(expected),
                "passed": passed,
            })
            if not passed:
                errors.append(f"{message}：实际值 {actual!s}，期望值 {expected!s}")
    return errors, details


def polling_config(value):
    value = value or {}
    return {
        "enabled": bool(value.get("enabled", False)),
        "timeout": max(1, int(value.get("timeout", 60) or 60)),
        "interval": max(1, int(value.get("interval", 3) or 3)),
        "initial_delay": max(0, int(value.get("initial_delay", 0) or 0)),
        "retry_http_error": bool(value.get("retry_http_error", True)),
        "retry_assertion": bool(value.get("retry_assertion", True)),
    }


def run_post_sql(post_sql, variables, project_id, environment_name):
    for expression in post_sql or []:
        if not isinstance(expression, str) or "${execute_sql_" not in expression:
            raise ValueError('后置数据库操作必须使用 ${execute_sql_xxx("SQL")} 语法。')
        substitute_text(expression, variables, project_id, environment_name)


def execute_api_step(
    *,
    request_template: dict,
    extract=None,
    validate=None,
    polling=None,
    post_sql=None,
    variables=None,
    project_id=None,
    environment_name=None,
    request_func: Callable[[dict, int, int], Any],
    on_attempt_complete: Callable[[int, Any, list[str]], None] | None = None,
    on_success: Callable[[dict], None] | None = None,
) -> StepExecutionResult:
    """执行一个接口步骤，两种入口仅负责提供 HTTP 请求函数和展示钩子。"""
    variables = variables if variables is not None else {}
    config = polling_config(polling)
    started_at = time.perf_counter()
    attempts = []
    last_request = {}
    last_response = None
    last_json = None
    last_body = ""
    last_errors = []
    assertion_details = []
    candidate_values = {}

    if config["enabled"] and not validate:
        error = ValueError("启用轮询时至少需要配置一条断言作为成功条件。")
        return StepExecutionResult(False, errors=[str(error)], exception=error)
    if config["enabled"] and config["initial_delay"]:
        time.sleep(min(config["initial_delay"], config["timeout"]))

    attempt = 0
    while True:
        attempt += 1
        attempt_started_at = time.perf_counter()
        try:
            last_request = substitute_data(
                request_template, variables, project_id, environment_name
            )
            elapsed = time.perf_counter() - started_at
            request_timeout = (
                min(30, max(1, int(config["timeout"] - elapsed)))
                if config["enabled"] else 30
            )
            last_response = request_func(last_request, request_timeout, attempt)
            last_body = last_response.text or ""
            try:
                last_json = last_response.json()
            except ValueError:
                last_json = {"msg": "is not json data"}
            candidate_values = extract_values(last_response, last_json, extract)
            candidate_context = {**variables, **candidate_values}
            last_errors, assertion_details = validate_response(
                last_response, last_json, validate, candidate_context,
                project_id, environment_name,
            )
        except Exception as exc:
            duration = time.perf_counter() - started_at
            error_text = str(exc)
            attempts.append({
                "attempt": attempt,
                "status_code": getattr(last_response, "status_code", None),
                "duration_ms": round((time.perf_counter() - attempt_started_at) * 1000, 2),
                "errors": [error_text],
            })
            if on_attempt_complete:
                on_attempt_complete(attempt, last_response, [error_text])
            return StepExecutionResult(
                False, last_request, last_response, last_json, last_body,
                [error_text], assertion_details, candidate_values, attempts,
                duration, exc,
            )

        attempts.append({
            "attempt": attempt,
            "status_code": last_response.status_code,
            "duration_ms": round((time.perf_counter() - attempt_started_at) * 1000, 2),
            "errors": list(last_errors),
        })
        if on_attempt_complete:
            on_attempt_complete(attempt, last_response, last_errors)

        if not last_errors:
            try:
                variables.update(candidate_values)
                if on_success:
                    on_success(candidate_values)
                run_post_sql(post_sql, variables, project_id, environment_name)
            except Exception as exc:
                duration = time.perf_counter() - started_at
                return StepExecutionResult(
                    False, last_request, last_response, last_json, last_body,
                    [str(exc)], assertion_details, candidate_values, attempts,
                    duration, exc,
                )
            return StepExecutionResult(
                True, last_request, last_response, last_json, last_body,
                [], assertion_details, candidate_values, attempts,
                time.perf_counter() - started_at,
            )

        elapsed = time.perf_counter() - started_at
        retry = config["enabled"] and elapsed < config["timeout"]
        if last_response.status_code >= 400 and not config["retry_http_error"]:
            retry = False
        if last_response.status_code < 400 and not config["retry_assertion"]:
            retry = False
        if not retry:
            return StepExecutionResult(
                False, last_request, last_response, last_json, last_body,
                last_errors, assertion_details, candidate_values, attempts,
                time.perf_counter() - started_at,
            )
        time.sleep(min(config["interval"], max(0, config["timeout"] - elapsed)))


def execute_api_step_with_failure_retry(
    execute_once: Callable[[], StepExecutionResult],
    *,
    enabled: bool = False,
    retry_count: int = 1,
) -> StepExecutionResult:
    """在完整接口步骤失败后重试，并合并各轮轮询/请求尝试记录。"""
    try:
        normalized_retry_count = max(1, min(5, int(retry_count or 1)))
    except (TypeError, ValueError):
        normalized_retry_count = 1
    maximum_executions = 1 + (normalized_retry_count if enabled else 0)
    combined_attempts = []
    total_duration = 0.0
    final_result = None

    for execution_attempt in range(1, maximum_executions + 1):
        result = execute_once()
        final_result = result
        total_duration += float(result.duration_seconds or 0)
        source_attempts = result.attempts or [{
            "status_code": getattr(result.response, "status_code", None),
            "duration_ms": round(float(result.duration_seconds or 0) * 1000, 2),
            "errors": list(result.errors or []),
        }]
        for source_attempt in source_attempts:
            combined_attempts.append({
                **source_attempt,
                "polling_attempt": source_attempt.get("attempt", 1),
                "execution_attempt": execution_attempt,
                "attempt": len(combined_attempts) + 1,
            })
        if result.passed:
            break

    final_result.attempts = combined_attempts
    final_result.duration_seconds = total_duration
    return final_result
