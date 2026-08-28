"""套件统一执行入口：按配置顺序交错执行 API 步骤和 UI 用例。"""
from pathlib import Path

import pytest
import yaml

from fullstack_framework.commons import case_util
from fullstack_framework.commons.models import CaseInfo
from fullstack_framework.commons.ui_executor import execute_ui_case
from case_ui.playwright_executor import execute_playwright_case


def _load_execution_plan():
    path = Path.cwd() / "execution_plan.yaml"
    if not path.exists():
        raise ValueError("未找到套件执行计划 execution_plan.yaml。")
    with open(path, encoding="utf-8") as file:
        items = yaml.safe_load(file) or []
    if not isinstance(items, list) or not items:
        raise ValueError("套件执行计划为空或格式不正确。")
    return items


def _item_name(item):
    case = item.get("case") or {}
    prefix = "API" if item.get("type") in {"api", "api_flow"} else "Playwright UI" if item.get("type") == "playwright_ui" else "UI"
    return f"{prefix} · {case.get('test_name') or case.get('name') or '未命名'}"


def _reload_api_variables():
    values = case_util.yaml_file.read() or {}
    case_util.extrac_data.clear()
    case_util.extrac_data.update(values)


execution_items = _load_execution_plan()


@pytest.mark.parametrize("execution_item", execution_items, ids=[_item_name(item) for item in execution_items])
def test_execution_item(execution_item):
    item_type = execution_item.get("type")
    case_data = execution_item.get("case") or {}
    if item_type == "api":
        _reload_api_variables()
        case_info = CaseInfo(**case_data)
        case_util.run_case([case_info])
        return
    if item_type == "api_flow":
        _reload_api_variables()
        case_util.run_flow(case_data)
        return
    if item_type == "ui":
        try:
            execute_ui_case(case_data)
        finally:
            # UI 步骤可能提取新变量，后续 API 必须立即读到。
            _reload_api_variables()
        return
    if item_type == "playwright_ui":
        execute_playwright_case(case_data)
        return
    raise ValueError(f"不支持的套件执行项类型：{item_type}")
