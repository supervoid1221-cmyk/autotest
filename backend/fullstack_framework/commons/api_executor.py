"""页面调试与 pytest 套件共用的接口步骤执行器。"""
from __future__ import annotations

import logging
import base64
import json
import re
import time
from datetime import datetime
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Callable
from urllib.parse import quote, unquote
from zoneinfo import ZoneInfo

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


def _is_empty_extracted_value(value):
    return value is None or value == "" or value == "no data" or value == [] or value == {}


def _processor_number(value):
    if isinstance(value, bool):
        return int(value)
    number = Decimal(str(value).strip())
    return int(number) if number == number.to_integral_value() else float(number)


def _processor_boolean(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        return value != 0
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y", "on", "是", "真"}:
        return True
    if normalized in {"false", "0", "no", "n", "off", "", "否", "假"}:
        return False
    raise ValueError(f"无法将「{value}」转换为布尔值")


def _processor_timezone(config):
    name = str(config.get("timezone") or "Asia/Shanghai")
    try:
        return ZoneInfo(name)
    except Exception as exc:
        raise ValueError(f"无效时区「{name}」") from exc


def _datetime_to_timestamp(value, config):
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()
        value_format = str(config.get("format") or "").strip()
        try:
            parsed = datetime.strptime(text, value_format) if value_format else datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError("日期时间格式不匹配，请配置正确的格式") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=_processor_timezone(config))
    timestamp = parsed.timestamp()
    return int(timestamp * 1000) if config.get("unit") == "milliseconds" else int(timestamp)


def _timestamp_to_datetime(value, config):
    try:
        timestamp = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("时间戳必须为数字") from exc
    unit = str(config.get("unit") or "auto")
    if unit == "milliseconds" or (unit == "auto" and abs(timestamp) >= 100_000_000_000):
        timestamp /= 1000
    value_format = str(config.get("format") or "%Y-%m-%d %H:%M:%S")
    return datetime.fromtimestamp(timestamp, _processor_timezone(config)).strftime(value_format)


def apply_extract_processor(value, processor):
    """执行单个白名单处理器；不执行任意表达式或 eval。"""
    if not isinstance(processor, dict):
        raise ValueError("处理器配置必须为对象")
    processor_type = str(processor.get("type") or "").strip()
    if processor_type == "default":
        return processor.get("value") if _is_empty_extracted_value(value) else value
    if processor_type == "trim":
        return str(value).strip()
    if processor_type == "prefix":
        return f"{processor.get('value', '')}{value}"
    if processor_type == "suffix":
        return f"{value}{processor.get('value', '')}"
    if processor_type == "replace":
        search = str(processor.get("search") or "")
        if not search:
            raise ValueError("字符串替换的查找内容不能为空")
        raw_count = processor.get("count", -1)
        count = -1 if raw_count in (None, "") else int(raw_count)
        return str(value).replace(search, str(processor.get("replacement") or ""), count)
    if processor_type == "regex":
        pattern = str(processor.get("pattern") or "")
        if not pattern:
            raise ValueError("正则表达式不能为空")
        return extract_with_regex(value, pattern, int(processor.get("group", 0) or 0))
    if processor_type == "split":
        separator = processor.get("separator")
        parts = str(value).split(str(separator)) if separator not in (None, "") else str(value).split()
        index = int(processor.get("index", 0) or 0)
        try:
            return parts[index]
        except IndexError as exc:
            raise ValueError(f"分割结果不存在索引 {index}") from exc
    if processor_type == "json_parse":
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(str(value))
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError(f"JSON 字符串解析失败：{exc}") from exc
    if processor_type == "cast":
        target = str(processor.get("target") or "string")
        if target == "string":
            if isinstance(value, (dict, list)):
                return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            return str(value)
        if target == "number":
            try:
                return _processor_number(value)
            except (InvalidOperation, ValueError) as exc:
                raise ValueError(f"无法将「{value}」转换为数字") from exc
        if target == "boolean":
            return _processor_boolean(value)
        raise ValueError(f"不支持的目标类型「{target}」")
    if processor_type == "base64_encode":
        return base64.b64encode(str(value).encode("utf-8")).decode("ascii")
    if processor_type == "base64_decode":
        try:
            return base64.b64decode(str(value), validate=True).decode("utf-8")
        except Exception as exc:
            raise ValueError("Base64 解码失败") from exc
    if processor_type == "url_encode":
        return quote(str(value), safe=str(processor.get("safe") or ""))
    if processor_type == "url_decode":
        return unquote(str(value))
    if processor_type == "datetime_to_timestamp":
        return _datetime_to_timestamp(value, processor)
    if processor_type == "timestamp_to_datetime":
        return _timestamp_to_datetime(value, processor)
    if processor_type == "array_item":
        if not isinstance(value, (list, tuple)):
            raise ValueError("当前值不是数组")
        position = str(processor.get("position") or "first")
        index = 0 if position == "first" else -1 if position == "last" else int(processor.get("index", 0) or 0)
        try:
            return value[index]
        except IndexError as exc:
            raise ValueError(f"数组不存在索引 {index}") from exc
    if processor_type == "object_pick":
        if not isinstance(value, dict):
            raise ValueError("当前值不是对象")
        keys = processor.get("keys") or []
        if isinstance(keys, str):
            keys = [item.strip() for item in keys.split(",") if item.strip()]
        return {str(key): value[str(key)] for key in keys if str(key) in value}
    if processor_type == "object_rename":
        if not isinstance(value, dict):
            raise ValueError("当前值不是对象")
        mapping = processor.get("mapping") or {}
        if isinstance(mapping, str):
            mapping = {
                old.strip(): new.strip()
                for item in (part.strip() for part in mapping.split(","))
                if item and ":" in item
                for old, new in [item.split(":", 1)]
                if old.strip()
            }
        if not isinstance(mapping, dict):
            raise ValueError("字段重命名映射必须为对象")
        return {str(mapping.get(str(key), key)): item for key, item in value.items()}
    raise ValueError(f"不支持的数据处理器「{processor_type}」")


def apply_extract_processors(variable_name, value, processors):
    for index, processor in enumerate(processors or [], start=1):
        try:
            value = apply_extract_processor(value, processor)
        except Exception as exc:
            processor_type = processor.get("type", "") if isinstance(processor, dict) else ""
            raise ValueError(
                f"变量「{variable_name}」的第 {index} 个处理步骤「{processor_type}」失败：{exc}"
            ) from exc
    return value


def extract_values(response, response_json, extract):
    values = {}
    for variable_name, raw_config in (extract or {}).items():
        processors = []
        if isinstance(raw_config, dict):
            mode = str(raw_config.get("mode") or "jsonpath")
            source_name = str(raw_config.get("source") or ("text" if mode == "re" else "json"))
            expression_text = str(raw_config.get("expression") or "")
            result_index = int(raw_config.get("index", 0) or 0)
            expression = (
                ["re", source_name, expression_text, result_index]
                if mode == "re"
                else [source_name, expression_text, result_index]
            )
            processors = raw_config.get("processors") or []
        else:
            expression = raw_config
        if not isinstance(expression, list):
            raise ValueError(f"变量「{variable_name}」的数据提取配置必须为数组或对象。")
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
        values[variable_name] = apply_extract_processors(variable_name, value, processors)
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
