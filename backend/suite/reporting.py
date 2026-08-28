"""原生执行报告的状态汇总与异常收口。"""
from datetime import datetime
from copy import deepcopy
from pathlib import Path
import json
import re

import yaml


STEP_STATUSES = ("passed", "failed", "running", "pending", "skipped")
SENSITIVE_VARIABLE_KEY = re.compile(
    r"(?:token|password|passwd|secret|authorization|cookie|api[_-]?key|access[_-]?key|refresh[_-]?token|private[_-]?key|webhook|hook[_-]?key)",
    re.IGNORECASE,
)


def _snapshot_value(value, sensitive=False):
    if sensitive:
        return "***"
    if isinstance(value, dict):
        return {
            str(key): _snapshot_value(item, SENSITIVE_VARIABLE_KEY.search(str(key)) is not None)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_snapshot_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def sanitize_variable_snapshot(variables):
    """生成可写入原生报告的最终变量快照，并遮罩明显的敏感变量。"""
    return _snapshot_value(dict(variables or {}))


def load_variable_snapshot(run_path):
    """从运行目录读取最新变量文件，供异常收口时写入报告。"""
    try:
        from pathlib import Path
        import yaml

        extract_path = Path(run_path) / "extract.yaml"
        if not extract_path.exists():
            return {}
        with extract_path.open(encoding="utf-8") as file:
            return sanitize_variable_snapshot(yaml.safe_load(file) or {})
    except Exception:
        return {}


VARIABLE_SOURCE_LABELS = {
    "project": "项目参数",
    "environment_token": "环境 Token",
    "template": "模板参数",
    "api_extract": "接口提取",
    "ui_extract": "UI 提取",
}


def hydrate_api_flow_snapshots(report):
    """为迁移前的 API 报告补齐当前场景流程树。

    新执行记录在创建时已经保存 ``flow_nodes``，必须优先使用执行时快照；
    历史记录只有步骤和 decisions，只能按当前场景编排恢复展示结构。该函数
    只修改返回副本，不回写历史结果，避免读取报告产生数据库副作用。
    """
    hydrated = deepcopy(report or {})
    api_groups = [
        group
        for group in hydrated.get("scenarios", [])
        if group.get("type") == "api" and not group.get("flow_nodes")
    ]
    if not api_groups:
        return hydrated

    try:
        from case_api.models import Scenario, ScenarioFlowNode

        scenario_ids = []
        for group in api_groups:
            try:
                scenario_ids.append(int(group.get("id")))
            except (TypeError, ValueError):
                continue
        scenarios = {scenario.id: scenario for scenario in Scenario.objects.filter(id__in=scenario_ids)}

        def serialize_nodes(scenario, parent_branch=None):
            nodes = (
                ScenarioFlowNode.objects.filter(scenario=scenario, parent_branch=parent_branch)
                .select_related("step")
                .prefetch_related("branches")
                .order_by("order", "id")
            )
            values = []
            for node in nodes:
                if node.node_type == ScenarioFlowNode.NodeType.ENDPOINT:
                    values.append({
                        "node_type": "endpoint",
                        "node_id": node.id,
                        "order": node.order,
                        "source_step_id": node.step_id,
                    })
                    continue
                values.append({
                    "node_type": "condition",
                    "node_id": node.id,
                    "name": node.name or "判断分支",
                    "order": node.order,
                    "condition_logic": node.condition_logic or "and",
                    "branches": [
                        {
                            "id": branch.id,
                            "name": branch.name or "未命名分支",
                            "order": branch.order,
                            "conditions": branch.conditions or [],
                            "nodes": serialize_nodes(scenario, branch),
                        }
                        for branch in node.branches.all().order_by("order", "id")
                    ],
                })
            return values

        for group in api_groups:
            try:
                scenario = scenarios.get(int(group.get("id")))
            except (TypeError, ValueError):
                scenario = None
            if scenario:
                group["flow_nodes"] = serialize_nodes(scenario)
                group["flow_snapshot_source"] = "current_scenario"
    except Exception:
        # 历史拓扑恢复失败不能影响报告主体读取。
        return hydrated
    return hydrated


def _variable_resolution_path(run_path):
    return Path(run_path) / "variable_resolution.yaml"


def record_variable_resolution(run_path, source, variables, **context):
    """记录变量的产生和覆盖轨迹；报告文件中不写入敏感明文。"""
    if not variables:
        return
    path = _variable_resolution_path(run_path)
    try:
        if path.exists():
            with path.open(encoding="utf-8") as file:
                events = yaml.safe_load(file) or []
        else:
            events = []
        latest_sources = {str(item.get("name")): item.get("source") for item in events}
        occurred_at = datetime.now().astimezone().isoformat()
        for name, value in dict(variables).items():
            key = str(name)
            event = {
                "name": key,
                "source": source,
                "source_label": VARIABLE_SOURCE_LABELS.get(source, source),
                "value": _snapshot_value(value, SENSITIVE_VARIABLE_KEY.search(key) is not None),
                "occurred_at": occurred_at,
                "overrode_source": latest_sources.get(key),
            }
            event.update({key: value for key, value in context.items() if value not in (None, "")})
            events.append(event)
            latest_sources[key] = source
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as file:
            yaml.safe_dump(events, file, allow_unicode=True, sort_keys=False)
    except Exception:
        # 变量轨迹不能影响测试主流程。
        return


def load_variable_resolution(run_path):
    """读取变量解析轨迹，并标记每个变量最后生效的记录。"""
    try:
        path = _variable_resolution_path(run_path)
        if not path.exists():
            return []
        with path.open(encoding="utf-8") as file:
            events = yaml.safe_load(file) or []
        last_indexes = {}
        for index, event in enumerate(events):
            last_indexes[str(event.get("name"))] = index
        return [
            {**event, "effective": last_indexes.get(str(event.get("name"))) == index}
            for index, event in enumerate(events)
        ]
    except Exception:
        return []


def merge_ui_runtime_results(report, run_path):
    """将 UI 执行器的步骤快照合并到原生报告。

    UI/Playwright 运行在 pytest 子进程中。步骤快照使进度接口无需
    等待整个 pytest 结束，也能避免 SQLite 短暂写锁导致实时状态丢失。
    """
    report = report or {}
    run_path = Path(run_path)
    result_files = [
        *run_path.glob("ui_native_result_*.json"),
        *run_path.glob("playwright_native_result_*.json"),
    ]
    for result_file in result_files:
        try:
            execution_report = json.loads(result_file.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            # 写入使用临时文件原子替换，这里仍容忍运行目录的历史异常文件。
            continue

        case_id = execution_report.get("case_id")
        engine = str(execution_report.get("engine") or "")
        group_id = f"playwright-ui-{case_id}" if engine == "playwright" else f"ui-{case_id}"
        group = next(
            (item for item in report.get("scenarios", []) if str(item.get("id")) == group_id),
            None,
        )
        if not group:
            continue
        native_steps = {str(item.get("source_step_id")): item for item in group.get("steps", [])}
        for executed_step in execution_report.get("steps", []):
            target = native_steps.get(str(executed_step.get("id")))
            if not target:
                continue
            for key in (
                "status", "passed", "started_at", "finished_at", "duration_ms",
                "action_key", "element_name", "by", "locator", "detail",
                "assertions", "extracted", "skip_reason", "exception",
            ):
                if key in executed_step:
                    target[key] = executed_step[key]
            if executed_step.get("action"):
                target["action_key"] = executed_step["action"]
            if executed_step.get("target"):
                target["target"] = executed_step["target"]
            if executed_step.get("tab_key"):
                target["tab_key"] = executed_step["tab_key"]
            if "errors" in executed_step:
                target["errors"] = executed_step.get("errors") or []
            elif executed_step.get("error"):
                target["errors"] = [executed_step["error"]]
                target["exception"] = executed_step["error"]
            if target.get("status") != "skipped":
                target.pop("skip_reason", None)

    return recalculate_native_report(report)


def recalculate_native_report(report):
    """统一计算步骤汇总和场景状态，API/UI 执行器共用。"""
    report = report or {}
    groups = report.setdefault("scenarios", [])
    all_steps = []
    for group in groups:
        steps = group.setdefault("steps", [])
        all_steps.extend(steps)
        statuses = [step.get("status", "pending") for step in steps]
        if any(status == "failed" for status in statuses):
            group["status"] = "failed"
        elif any(status == "running" for status in statuses):
            group["status"] = "running"
        elif any(status == "pending" for status in statuses):
            group["status"] = "pending"
        elif statuses and all(status == "skipped" for status in statuses):
            group["status"] = "skipped"
        elif statuses:
            group["status"] = "passed"
        else:
            group["status"] = "skipped"

        started = [step.get("started_at") for step in steps if step.get("started_at")]
        finished = [step.get("finished_at") for step in steps if step.get("finished_at")]
        if started:
            group["started_at"] = min(started)
        if finished and not any(status in {"pending", "running"} for status in statuses):
            group["finished_at"] = max(finished)
        group["duration_ms"] = round(sum(float(step.get("duration_ms") or 0) for step in steps), 2)

    counts = {
        status: sum(1 for step in all_steps if step.get("status", "pending") == status)
        for status in STEP_STATUSES
    }
    report["summary"] = {
        "total": len(all_steps),
        **counts,
        "completed": counts["passed"] + counts["failed"] + counts["skipped"],
    }
    return report


def finalize_unfinished_steps(report, reason, finished_at=None):
    """将因中断、启动失败或前序失败而未执行的步骤明确标记为跳过。"""
    finished_at = finished_at or datetime.now().astimezone().isoformat()
    report = report or {}
    for group in report.get("scenarios", []):
        for step in group.get("steps", []):
            if step.get("status") in {"pending", "running"}:
                step.update({
                    "status": "skipped",
                    "passed": None,
                    "finished_at": finished_at,
                    "duration_ms": float(step.get("duration_ms") or 0),
                    "skip_reason": reason,
                })
    return recalculate_native_report(report)
