"""
@Filename:   commons/case_util
@Author:
@Time:
@Describe:    ...
"""
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import yaml
from fullstack_framework.commons import settings
from fullstack_framework.commons.ddt_util import ddt
from fullstack_framework.commons.models import CaseInfo
from fullstack_framework.commons.session import BeifanSession
from fullstack_framework.commons.yaml_util import YamlUtil
from fullstack_framework.commons.api_executor import (
    execute_api_step,
    execute_api_step_with_failure_retry,
    run_dynamic_function,
    substitute_text,
)
from project.models import Environment, response_indicates_expired_token
from project.runtime_token import RuntimeTokenState
from suite.reporting import load_variable_resolution, recalculate_native_report, record_variable_resolution

logger = logging.getLogger(__name__)
NATIVE_RESPONSE_BODY_PREVIEW_BYTES = 100 * 1024
DEFAULT_API_STEP_INTERVAL_SECONDS = 1.0
_last_api_step_finished_at = None


def _api_step_interval_seconds():
    """返回套件内相邻接口的最小间隔。

    默认为 1 秒，可通过 PLATFORM_API_STEP_INTERVAL_SECONDS 调整；
    配置为 0 可关闭。非套件调试没有前置步骤，不会产生额外等待。
    """
    raw_value = os.environ.get(
        "PLATFORM_API_STEP_INTERVAL_SECONDS", str(DEFAULT_API_STEP_INTERVAL_SECONDS)
    )
    try:
        return max(0.0, float(raw_value))
    except (TypeError, ValueError):
        logger.warning(
            "PLATFORM_API_STEP_INTERVAL_SECONDS=%r 无效，使用默认值 %.1f 秒。",
            raw_value,
            DEFAULT_API_STEP_INTERVAL_SECONDS,
        )
        return DEFAULT_API_STEP_INTERVAL_SECONDS


def _wait_for_api_step_interval(case_name=""):
    """在上一个接口结束后留出最小稳定时间。"""
    if not os.environ.get("PLATFORM_RUN_RESULT_ID"):
        return
    interval = _api_step_interval_seconds()
    if interval <= 0 or _last_api_step_finished_at is None:
        return
    remaining = interval - (time.monotonic() - _last_api_step_finished_at)
    if remaining > 0:
        logger.info("下一接口「%s」执行前等待 %.2f 秒。", case_name or "未命名", remaining)
        time.sleep(remaining)

def _run_dynamic_function(name, variables, arguments=""):
    """兼容旧调用入口，实际执行统一委托给共享步骤执行器。"""
    return run_dynamic_function(name, variables, arguments)

session = BeifanSession()
yaml_file = YamlUtil(settings.extract_path)

extrac_data = yaml_file.read() or {}
project_fallback_path = Path.cwd() / "project_variable_fallbacks.yaml"
if project_fallback_path.exists():
    with project_fallback_path.open(encoding="utf-8") as project_fallback_file:
        project_token_fallbacks = yaml.safe_load(project_fallback_file) or {}
else:
    project_token_fallbacks = {}
runtime_token_state = RuntimeTokenState(extrac_data, project_token_fallbacks)

logger.info(f"{extrac_data=}")


def substitute_variables(content: str, variables=None, project_id=None, environment_name=None) -> str:
    """兼容旧调用入口；未解析表达式现在会立即抛出明确错误。"""
    variables = extrac_data if variables is None else variables
    return substitute_text(content, variables, project_id, environment_name)


def load_case():
    base_path = Path(settings.test_case_path)  # 测试用例的存放目录

    yaml_path_list = list(base_path.glob(settings.test_glob))  # 此列表的内容、顺序，决定用例的内容和顺序
    yaml_path_list.sort()

    logger.info(f"从{base_path} 加载到 {len(yaml_path_list)}个yaml文件：")
    logger.info(f"{yaml_path_list}")

    case_info_list = []  # 用例内容
    case_name_list = []  # 用例名称

    for yaml_path in yaml_path_list:
        data = YamlUtil(yaml_path).read()  # 加载yaml内容

        if isinstance(data, dict):  # 如果data是字典，属于普通用例，每个接口属于各自的用例
            if "parametrize" in data:  # 是否使用数据驱动测试
                for data in ddt(data):  # 进行DDT处理 ：一个用例变成多个用例
                    case_data_to_case_list(data, case_info_list, case_name_list)
            else:
                case_data_to_case_list(data, case_info_list, case_name_list)

        elif isinstance(data, list):
            # 场景 YAML 中每一项都是一个接口。将其展开成独立 pytest 用例，
            # 这样原生报告的接口统计与实际接口数量一致。
            # 参数化顺序保持 YAML 中步骤顺序，运行期提取变量仍由同一进程共享。

            for case_info_data in data:
                # 场景 YAML 中的单个接口同样支持 parametrize；每一行数据展开为
                # 独立 pytest 参数和原生报告条目。
                expanded_cases = ddt(case_info_data) if isinstance(case_info_data, dict) and "parametrize" in case_info_data else [case_info_data]
                for expanded_case in expanded_cases:
                    try:
                        _case_info = CaseInfo(**expanded_case)  # 校验yaml格式

                        if "bbs" in str(yaml_path):  # 根据路径，自动标注模块
                            _case_info.feature = "论坛模块"
                        elif "weixin" in str(yaml_path):
                            _case_info.feature = "微信模块"

                        case_info_list.append([_case_info])
                        case_name_list.append(_case_info.test_name)

                    except Exception as e:
                        raise ValueError(f"{e.args} ({yaml_path})")  # 报错，发出提示

            logger.info(f"{yaml_path} 加载到 {len(data)} 个接口用例")

    logger.info(f"共加载到用例：{len(case_info_list)}个")
    return case_info_list, case_name_list


def case_data_to_case_list(data, case_info_list, case_name_list):
    _case_info = CaseInfo(**data)  # 校验yaml格式
    case_info_list.append([_case_info])  # yaml中所有的内容，作为一个用例
    case_name_list.append(_case_info.test_name)  # 将用例名称放入列表


def run_case(all_case_info):
    """执行场景中的接口，每个接口写入独立原生报告步骤。"""
    for case_info in all_case_info:
        _run_case([case_info])


def _persist_extracted(values, case_info=None):
    for name, value in values.items():
        extrac_data[name] = value
        if case_info and getattr(case_info, "project_id", None):
            extrac_data[f"project_{case_info.project_id}.{name}"] = value
        logger.info(f"提取到变量 {name} = {value}")
        if name.startswith("session_"):
            params = session.params or {}
            params[name[8:]] = value
            session.params = params
    if values:
        yaml_file.write(extrac_data)
        extract_rules = getattr(case_info, "extract", None) or {}
        for name, value in values.items():
            rule = extract_rules.get(name)
            if isinstance(rule, dict):
                expression = rule.get("expression")
            else:
                expression = rule[1] if isinstance(rule, (list, tuple)) and len(rule) > 1 else rule
            record_variable_resolution(
                Path.cwd(), "api_extract", {name: value},
                step_id=getattr(case_info, "source_step_id", None),
                step_name=getattr(case_info, "test_name", ""),
                expression=str(expression or ""),
            )


def _report_safe(value):
    """把 requests 对象等不可 JSON 序列化的值转换为报告可保存的数据。"""
    try:
        return yaml.safe_load(yaml.safe_dump(value, allow_unicode=True))
    except Exception:
        return str(value)


def _report_headers(headers):
    sensitive = {"authorization", "cookie", "set-cookie", "x-token", "token", "proxy-authorization"}
    return {
        str(key): ("***" if str(key).lower() in sensitive else str(value))
        for key, value in dict(headers or {}).items()
    }


def _response_body_preview(value):
    """原生报告最多保存 100KB UTF-8 正文，超出部分仅以省略号表示。"""
    text = str(value or "")
    encoded = text.encode("utf-8")
    if len(encoded) <= NATIVE_RESPONSE_BODY_PREVIEW_BYTES:
        return text
    suffix = "..."
    available = NATIVE_RESPONSE_BODY_PREVIEW_BYTES - len(suffix.encode("utf-8"))
    return encoded[:available].decode("utf-8", errors="ignore") + suffix


def _append_native_step(case_info, request, response=None, errors=None, assertions=None,
                        extracted=None, attempts=1, duration=0, exception=None, started_at=None):
    """将一个接口步骤的最终执行结果写入当前运行记录；写入失败不影响测试本身。"""
    result_id = os.environ.get("PLATFORM_RUN_RESULT_ID")
    if not result_id:
        return
    try:
        from suite.models import RunResult

        result = RunResult.objects.get(id=int(result_id))
        report = result.native_report or {}
        report.setdefault("suite", result.suite.name)
        report.setdefault("environment", getattr(result.suite.environment, "name", ""))
        scenarios = report.setdefault("scenarios", [])
        scenario_id = case_info.scenario_id or case_info.feature or "default"
        scenario_name = case_info.scenario_name or case_info.feature or "未分组场景"
        scenario = next((item for item in scenarios if str(item.get("id")) == str(scenario_id)), None)
        if scenario is None:
            scenario = {"id": scenario_id, "name": scenario_name, "steps": []}
            scenarios.append(scenario)

        body = ""
        status_code = None
        response_headers = {}
        if response is not None:
            status_code = response.status_code
            body = _response_body_preview(response.text)
            response_headers = _report_headers(response.headers)
        passed = not errors and exception is None
        step_data = {
            "source_step_id": case_info.source_step_id,
            "name": case_info.test_name,
            "method": str((request or {}).get("method", "")).upper(),
            "url": (request or {}).get("url", ""),
            "status": "passed" if passed else "failed",
            "passed": passed,
            "status_code": status_code,
            "started_at": started_at or "",
            "finished_at": datetime.now().astimezone().isoformat(),
            "duration_ms": round(duration * 1000, 2),
            "attempts": attempts,
            "request": {
                "headers": _report_headers((request or {}).get("headers")),
                "params": _report_safe((request or {}).get("params") or {}),
                "data": _report_safe((request or {}).get("data") or {}),
                "json": _report_safe((request or {}).get("json") or {}),
            },
            "response": {"headers": response_headers, "body": body},
            "assertions": assertions or [],
            "extracted": _report_safe(extracted or {}),
            "errors": errors or [],
            "exception": str(exception or ""),
        }
        report["variable_resolution"] = load_variable_resolution(Path.cwd())
        # 步骤名称可以重复，优先用稳定的源步骤 ID 定位。
        steps = scenario.setdefault("steps", [])
        target = next((item for item in steps if str(item.get("source_step_id")) == str(case_info.source_step_id) and item.get("status") in ("pending", "running")), None)
        if target is None:
            target = next((item for item in steps if item.get("name") == case_info.test_name and item.get("status") in ("pending", "running")), None)
        if target is None:
            steps.append(step_data)
        else:
            target.update(step_data)
        recalculate_native_report(report)
        result.native_report = report
        result.save(update_fields=["native_report", "update_datetime"])
    except Exception:
        logger.exception("写入平台原生执行报告失败")


def _mark_native_step_running(case_info, started_at):
    """在真正发请求前标记当前接口，前端可实时显示“执行中”。"""
    result_id = os.environ.get("PLATFORM_RUN_RESULT_ID")
    if not result_id:
        return
    try:
        from suite.models import RunResult
        result = RunResult.objects.get(id=int(result_id))
        report = result.native_report or {}
        scenario_id = case_info.scenario_id or case_info.feature or "default"
        scenario = next((item for item in report.get("scenarios", []) if str(item.get("id")) == str(scenario_id)), None)
        if not scenario:
            return
        step = next((item for item in scenario.get("steps", []) if str(item.get("source_step_id")) == str(case_info.source_step_id) and item.get("status") == "pending"), None)
        if step:
            step.update({"status": "running", "passed": None, "started_at": started_at})
            recalculate_native_report(report)
            result.native_report = report
            result.save(update_fields=["native_report", "update_datetime"])
    except Exception:
        logger.exception("更新原生报告执行中状态失败")


def _execute_case_info(case_info):
    """执行一条接口并写入原生报告，返回结果供条件分支复用。"""
    global _last_api_step_finished_at
    _wait_for_api_step_interval(case_info.test_name)
    started_at_display = datetime.now().astimezone().isoformat()
    _mark_native_step_running(case_info, started_at_display)

    auth_refreshed = False

    def request_func(request_data, timeout, attempt):
        nonlocal auth_refreshed
        request_payload = dict(request_data)
        request_payload.setdefault("timeout", timeout)
        request_payload["interface_name"] = case_info.test_name
        environment = Environment.objects.filter(
            project_id=case_info.project_id, name=case_info.environment_name
        ).first()
        if environment:
            runtime_token_state.apply(environment, request_payload)
        response = session.request(**request_payload)
        if (
            environment
            and response_indicates_expired_token(response)
            and runtime_token_state.discard_runtime_token(environment)
        ):
            runtime_token_state.apply(environment, request_payload)
            response = session.request(**request_payload)
        # 网关可能用 HTTP 200 返回 code=1023/jwt expired，不能只依赖
        # token_expires_at 的预判；强制刷新后重试本次请求一次。
        if not auth_refreshed and response_indicates_expired_token(response):
            if environment:
                refreshed_headers = environment.prepare_auth(
                    Path.cwd(), str(environment.name), force_refresh=True
                )
                case_info.request.setdefault("headers", {}).update(refreshed_headers)
                request_payload["headers"] = {**request_payload.get("headers", {}), **refreshed_headers}
                auth_refreshed = True
                response = session.request(**request_payload)
        return response

    try:
        execution = execute_api_step_with_failure_retry(
            lambda: execute_api_step(
                request_template=case_info.request, extract=case_info.extract, validate=case_info.validate,
                polling=case_info.polling, post_sql=case_info.post_sql, variables=extrac_data,
                project_id=case_info.project_id, environment_name=case_info.environment_name,
                request_func=request_func,
                on_success=lambda values: (
                    _persist_extracted(values, case_info),
                    runtime_token_state.observe_extracted(environment, values) if environment else None,
                ),
            ),
            enabled=case_info.retry_on_failure,
            retry_count=case_info.failure_retry_count,
        )
        _append_native_step(
            case_info, execution.request, response=execution.response, errors=execution.errors,
            assertions=execution.assertions, extracted=execution.extracted, attempts=len(execution.attempts),
            duration=execution.duration_seconds, exception=execution.exception, started_at=started_at_display,
        )
        return execution
    finally:
        # 无论请求、断言还是报告写入是否异常，后续接口都从此时开始计算间隔。
        _last_api_step_finished_at = time.monotonic()


def _run_case(all_case_info):
    for case_info in all_case_info:
        execution = _execute_case_info(case_info)
        if not execution.passed:
            if execution.exception:
                raise execution.exception
            raise AssertionError("；".join(execution.errors))


def _update_flow_report(scenario_id, decisions=None, skip_step_id=None, reason=""):
    result_id = os.environ.get("PLATFORM_RUN_RESULT_ID")
    if not result_id:
        return
    try:
        from suite.models import RunResult
        result = RunResult.objects.get(id=int(result_id))
        report = result.native_report or {}
        group = next((item for item in report.get("scenarios", []) if str(item.get("id")) == str(scenario_id)), None)
        if not group:
            return
        if decisions is not None:
            group["decisions"] = decisions
        if skip_step_id is not None:
            target = next((item for item in group.get("steps", []) if str(item.get("source_step_id")) == str(skip_step_id)), None)
            if target and target.get("status") == "pending":
                target.update({"status": "skipped", "passed": None, "skip_reason": reason,
                               "finished_at": datetime.now().astimezone().isoformat(), "duration_ms": 0})
        recalculate_native_report(report)
        result.native_report = report
        result.save(update_fields=["native_report", "update_datetime"])
    except Exception:
        logger.exception("更新条件分支原生报告失败")


def run_flow(flow):
    """执行套件中的接口场景流程，支持单层条件分支。"""
    from case_api.flow import execute_flow

    def normalize(items):
        normalized = []
        for item in items or []:
            node = dict(item)
            if node.get("node_type") == "endpoint":
                case = dict(node.get("case") or {})
                node["step"] = {"id": case.get("source_step_id"), "continue_on_failure": case.get("continue_on_failure", True)}
            else:
                node["branches"] = [{**branch, "nodes": normalize(branch.get("nodes", []))} for branch in node.get("branches", [])]
            normalized.append(node)
        return normalized

    def run_endpoint(node):
        data = dict(node.get("case") or {})
        expanded = ddt(data) if data.get("parametrize") else [data]
        executions = []
        for case_data in expanded:
            case_info = CaseInfo(**case_data)
            execution = _execute_case_info(case_info)
            executions.append(execution)
            if not execution.passed:
                break
        final = executions[-1]
        return {
            "step_id": data.get("source_step_id"), "passed": all(item.passed for item in executions),
            "response_json": final.response_json, "errors": [error for item in executions for error in item.errors],
        }

    scenario_id = flow.get("id")
    payload = execute_flow(
        normalize(flow.get("nodes", [])), extrac_data, run_endpoint,
        on_skip=lambda node, reason: _update_flow_report(scenario_id, skip_step_id=(node.get("step") or {}).get("id"), reason=reason),
    )
    _update_flow_report(scenario_id, decisions=payload.get("decisions", []))
    if not payload.get("passed"):
        raise AssertionError("场景流程执行失败或未命中分支。")
    return payload
