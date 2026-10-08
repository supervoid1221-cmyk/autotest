"""场景条件分支的统一执行与条件计算。"""
from __future__ import annotations

import re
from typing import Any, Callable

import jsonpath


def _nested_value(value: Any, key: str):
    current = value
    for part in str(key or "").split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _json_path(value: Any, expression: str):
    if not expression:
        return value
    found = jsonpath.jsonpath(value, expression)
    if found is False or not found:
        return None
    return found[0] if len(found) == 1 else found


def _resolve_expected(value: Any, variables: dict):
    if not isinstance(value, str):
        return value
    match = re.fullmatch(r"(?:\$\{\s*([\w.]+)\s*\}|\{\{\s*([\w.]+)\s*\}\})", value.strip())
    if match:
        return _nested_value(variables, match.group(1) or match.group(2))
    return value


def _coerce_pair(actual: Any, expected: Any):
    if isinstance(actual, bool):
        return actual, str(expected).lower() in {"true", "1", "yes"}
    if isinstance(actual, (int, float)) and isinstance(expected, str):
        try:
            return actual, float(expected)
        except ValueError:
            pass
    return actual, expected


def evaluate_condition(item: dict, variables: dict, responses: dict):
    """安全判断单个条件，返回实际值、期望值和结果供页面/报告展示。"""
    source = item.get("source", "variable")
    if source == "step":
        result = responses.get(str(item.get("step_id"))) or responses.get(item.get("step_id")) or {}
        actual = _json_path(result.get("response_json"), str(item.get("path") or ""))
    else:
        actual = _nested_value(variables, str(item.get("variable") or ""))
        if item.get("path"):
            actual = _json_path(actual, str(item.get("path")))
    expected = _resolve_expected(item.get("expected"), variables)
    operator = str(item.get("operator") or "equals")
    left, right = _coerce_pair(actual, expected)
    try:
        if operator == "exists":
            matched = actual is not None
        elif operator == "not_exists":
            matched = actual is None
        elif operator == "equals":
            matched = left == right
        elif operator == "not_equals":
            matched = left != right
        elif operator == "gt":
            matched = left > right
        elif operator == "gte":
            matched = left >= right
        elif operator == "lt":
            matched = left < right
        elif operator == "lte":
            matched = left <= right
        elif operator == "contains":
            matched = right in left if left is not None else False
        elif operator == "not_contains":
            matched = right not in left if left is not None else True
        elif operator == "regex":
            matched = bool(re.search(str(right or ""), str(left or "")))
        elif operator == "in":
            values = right if isinstance(right, list) else [part.strip() for part in str(right or "").split(",")]
            matched = left in values or str(left) in [str(value) for value in values]
        else:
            matched = False
    except (TypeError, ValueError, re.error):
        matched = False
    return {"matched": bool(matched), "actual": actual, "expected": expected, "operator": operator, "source": source}


def _branch_matches(branch: dict, variables: dict, responses: dict):
    details = [evaluate_condition(item, variables, responses) for item in branch.get("conditions", [])]
    logic = str(branch.get("condition_logic") or branch.get("node_logic") or "and").lower()
    matched = any(item["matched"] for item in details) if logic == "or" else bool(details) and all(item["matched"] for item in details)
    return matched, details


def execute_flow(nodes: list[dict], variables: dict, run_endpoint: Callable[[dict], dict], on_skip=None):
    """执行主流程或分支流程。

    run_endpoint 接收 endpoint 节点并返回带 passed、step_id、response_json 的字典。
    第一版固定为按分支优先级选择首个命中的分支，分支结束后回到外层流程。
    """
    results, decisions, responses, errors = [], [], {}, []
    stopped = False

    def step_value(node, key, default=None):
        step = node.get("step")
        return step.get(key, default) if isinstance(step, dict) else getattr(step, key, default)

    def skip_node(node, reason):
        item = {"step_id": step_value(node, "id") or node.get("step_id"), "passed": None, "skipped": True, "skip_reason": reason}
        results.append(item)
        if on_skip:
            on_skip(node, reason)

    def run_nodes(items):
        nonlocal stopped
        for node in sorted(items, key=lambda item: (item.get("order", 0), item.get("id", 0))):
            if node.get("enabled", True) is False:
                if node.get("node_type") == "endpoint":
                    skip_node(node, "步骤已停用。")
                else:
                    decisions.append({"node_id": node.get("id"), "name": node.get("name"), "status": "disabled", "branches": []})
                    for branch in node.get("branches", []):
                        for child in branch.get("nodes", []):
                            skip_node(child, "所属判断节点已停用。")
                continue
            if stopped:
                if node.get("node_type") == "endpoint":
                    skip_node(node, "前序接口执行失败，流程已停止。")
                else:
                    for branch in node.get("branches", []):
                        for child in branch.get("nodes", []):
                            skip_node(child, "前序接口执行失败，流程已停止。")
                continue
            if node.get("node_type") == "endpoint":
                result = run_endpoint(node) or {}
                results.append(result)
                step_id = result.get("step_id") or step_value(node, "id") or node.get("step_id")
                responses[step_id] = result
                responses[str(step_id)] = result
                # 接口步骤默认采用“失败继续”。只有用户明确关闭该开关时，
                # 当前步骤失败才会终止后续流程；场景最终结果仍会保持失败。
                if not result.get("passed") and step_value(node, "continue_on_failure", True) is False:
                    stopped = True
                continue

            branches = sorted(node.get("branches", []), key=lambda item: (item.get("order", 0), item.get("id", 0)))
            selected, detail_records = None, []
            for branch in branches:
                matched, details = _branch_matches({**branch, "node_logic": node.get("condition_logic", "and")}, variables, responses)
                detail_records.append({"branch_id": branch.get("id"), "branch_name": branch.get("name"), "matched": matched, "conditions": details})
                if matched and selected is None:
                    selected = branch
            decisions.append({
                "node_id": node.get("id"), "name": node.get("name"), "status": "matched" if selected else "no_match",
                "selected_branch_id": selected.get("id") if selected else None,
                "selected_branch_name": selected.get("name") if selected else None,
                "branches": detail_records,
            })
            for branch in branches:
                if selected and branch.get("id") == selected.get("id"):
                    run_nodes(branch.get("nodes", []))
                else:
                    reason = "未命中条件分支。" if selected else "没有满足条件的分支。"
                    for child in branch.get("nodes", []):
                        skip_node(child, reason)
            if selected is None:
                errors.append(f"判断分支「{node.get('name') or node.get('id')}」没有满足条件的分支。")
                stopped = True

    run_nodes(nodes)
    executed = [item for item in results if item.get("passed") is not None]
    return {"passed": all(item.get("passed") for item in executed) and not stopped, "results": results, "decisions": decisions, "errors": errors, "stopped": stopped}


def scenario_flow_data(scenario):
    """将数据库场景转为可供页面调试执行的轻量流程结构。"""
    main_nodes = scenario.flow_nodes.filter(parent_branch__isnull=True).select_related("step", "step__endpoint").prefetch_related("branches", "branches__nodes", "branches__nodes__step", "branches__nodes__step__endpoint").order_by("order", "id")
    nodes = []
    for node in main_nodes:
        item = {"id": node.id, "node_type": node.node_type, "name": node.name, "order": node.order, "condition_logic": node.condition_logic, "enabled": node.enabled}
        if node.step_id:
            item["step"] = node.step
        if node.node_type == "condition":
            item["branches"] = [
                {"id": branch.id, "name": branch.name, "order": branch.order,
                 "conditions": branch.conditions or [], "nodes": [
                    {"id": child.id, "node_type": child.node_type, "name": child.name, "order": child.order, "step": child.step, "enabled": child.enabled}
                    for child in branch.nodes.all().order_by("order", "id")
                 ]}
                for branch in node.branches.all().order_by("order", "id")
            ]
        nodes.append(item)
    return nodes


def execute_scenario_flow(scenario, variables, run_step):
    return execute_flow(scenario_flow_data(scenario), variables, lambda node: run_step(node["step"]))
