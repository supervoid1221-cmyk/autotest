"""Browser interaction recording -> Playwright smart-case steps.

The browser extension deliberately sends a small, framework-neutral event
payload.  This module is the single place that removes noisy browser events,
chooses semantic targets/fallback locators, and compiles the canonical steps
used by the existing Playwright executor.
"""

from __future__ import annotations

import json
import re
from typing import Any


SENSITIVE = re.compile(r"password|passwd|pwd|token|secret|authorization|密码|密钥", re.I)
SUPPORTED_ACTIONS = {"navigate", "click", "input", "select", "check", "upload"}


def _text(value: Any, limit: int = 512) -> str:
    return " ".join(str(value or "").split())[:limit]


def _prefer_own_control_name(event: dict[str, Any], element: dict[str, Any]) -> bool:
    """Clicks on actionable controls should use their own caption, not a nearby field label."""
    if str(event.get("action") or "").lower() != "click":
        return False
    tag = _text(element.get("tag"), 32).lower()
    role = _text(element.get("role"), 32).lower()
    input_type = _text(element.get("type"), 32).lower()
    return (
        tag in {"button", "a"}
        or role in {"button", "link", "menuitem", "option", "tab"}
        or input_type in {"button", "submit", "reset", "image"}
    )


def _generic_select_control(element: dict[str, Any]) -> bool:
    """自定义下拉按钮例外：它的自身文字是当前值，字段标签才是回放目标。"""
    role = _text(element.get("role"), 32).lower()
    aria_label = _text(element.get("ariaLabel"), 64).lower()
    return role == "combobox" or aria_label in {
        "select option", "choose option", "select", "choose",
        "选择选项", "请选择", "选择", "下拉选择",
    }


def _semantic_keys(event: dict[str, Any], element: dict[str, Any]) -> tuple[str, ...]:
    if _prefer_own_control_name(event, element):
        if _generic_select_control(element):
            return "text", "value", "ariaLabel", "label", "title", "name", "id"
        return "text", "value", "ariaLabel", "title", "name", "id"
    return "label", "ariaLabel", "placeholder", "text", "value", "name", "id"


def _target(event: dict[str, Any]) -> str:
    element = event.get("element") if isinstance(event.get("element"), dict) else {}
    for key in _semantic_keys(event, element):
        value = _text(element.get(key))
        if value:
            return value
    # 可操作按钮不能回退使用附近输入框标签。例如“登录”按钮靠近
    # 密码框时，把按钮错记成“密码”会导致回放点击错误元素。
    if _prefer_own_control_name(event, element):
        return _text(event.get("target")) or "页面元素"
    nearby_labels = element.get("nearbyLabels")
    include_nearby = not _prefer_own_control_name(event, element) or _generic_select_control(element)
    if include_nearby and isinstance(nearby_labels, list):
        ranked = sorted(
            (item for item in nearby_labels if isinstance(item, dict) and _text(item.get("text"))),
            key=lambda item: float(item.get("distance") or 999999),
        )
        if ranked:
            return _text(ranked[0].get("text"))
    return _text(event.get("target")) or "页面元素"


def _fallback(event: dict[str, Any]) -> tuple[str, str]:
    element = event.get("element") if isinstance(event.get("element"), dict) else {}
    test_id = _text(element.get("testId"))
    if test_id:
        escaped = test_id.replace('"', '\\"')
        return "css_selector", f'[data-testid="{escaped}"]'
    element_id = _text(element.get("id"))
    if element_id:
        return "id", element_id
    name = _text(element.get("name"))
    if name:
        return "name", name
    css = _text(element.get("css"))
    if css:
        return "css_selector", css
    xpath = _text(element.get("xpath"))
    if xpath:
        return "xpath", xpath
    return "", ""


def _smart_locator(event: dict[str, Any]) -> dict[str, Any]:
    element = event.get("element") if isinstance(event.get("element"), dict) else {}
    role = _text(element.get("role"))
    aliases = []
    for key in _semantic_keys(event, element):
        value = _text(element.get(key))
        if value and value not in aliases:
            aliases.append(value)
    nearby_labels = element.get("nearbyLabels")
    include_nearby = not _prefer_own_control_name(event, element) or _generic_select_control(element)
    if include_nearby and isinstance(nearby_labels, list):
        for item in nearby_labels:
            value = _text(item.get("text")) if isinstance(item, dict) else ""
            if value and value not in aliases:
                aliases.append(value)
    result: dict[str, Any] = {"aliases": aliases[:6], "recorded": True}
    if role:
        result["role"] = role
    input_type = _text(element.get("type"), 32).lower()
    if input_type and input_type not in {"button", "submit", "reset", "textarea"}:
        result["input_types"] = [input_type]
    return result


def _looks_like_select_trigger(step: dict[str, Any]) -> bool:
    """识别自定义下拉触发器，用于将“打开下拉 + 点击选项”合并。"""
    smart = (step.get("options") or {}).get("smart_locator") or {}
    role = str(smart.get("role") or "").lower()
    aliases = [str(item or "").strip().lower() for item in smart.get("aliases", [])]
    trigger_hints = {
        "select option", "choose option", "select", "choose",
        "选择选项", "请选择", "选择", "下拉选择",
    }
    return role == "combobox" or bool(trigger_hints.intersection(aliases))


def _select_trigger_target(step: dict[str, Any], option_value: str) -> str:
    """通用 aria-label 无法区分多个下拉框时，使用录制时的字段名或显示值。"""
    generic = {
        "select option", "choose option", "select", "choose",
        "选择选项", "请选择", "选择", "下拉选择", "页面元素",
    }
    smart = (step.get("options") or {}).get("smart_locator") or {}
    current = _text(step.get("target"))
    aliases = [_text(alias) for alias in smart.get("aliases") or []]
    has_generic_alias = any(alias.lower() in generic for alias in aliases if alias)
    if current.lower() not in generic and not has_generic_alias:
        return current
    for candidate in aliases:
        if (
            candidate
            and candidate.lower() not in generic
            and candidate not in {current, option_value}
        ):
            return candidate
    return current


def _sensitive(event: dict[str, Any], target: str) -> bool:
    element = event.get("element") if isinstance(event.get("element"), dict) else {}
    return element.get("type") == "password" or bool(SENSITIVE.search(" ".join([
        target, _text(element.get("name")), _text(element.get("id")),
    ])))


def _same_recorded_element(step: dict[str, Any], target: str, fallback_type: str, fallback_value: str) -> bool:
    """Whether two noisy browser events point at the same control."""
    if fallback_type and fallback_value:
        return step.get("fallback_type") == fallback_type and step.get("fallback_value") == fallback_value
    return bool(target) and step.get("target") == target


def normalize_ui_recording(payload: dict[str, Any]) -> dict[str, Any]:
    """Return canonical tabs, steps and a readable Playwright code preview."""
    raw_events = payload.get("events", [])
    if not isinstance(raw_events, list):
        raise ValueError("录制事件必须是数组。")

    events = []
    seen_event_ids: set[str] = set()
    for item in raw_events:
        if not isinstance(item, dict) or item.get("action") not in SUPPORTED_ACTIONS:
            continue
        event_id = _text(item.get("eventId"), 128)
        if event_id and event_id in seen_event_ids:
            continue
        if event_id:
            seen_event_ids.add(event_id)
        events.append(item)
    events.sort(key=lambda item: float(item.get("timestamp") or 0))
    steps: list[dict[str, Any]] = []
    tab_keys: list[str] = []
    last_signature = None

    for event in events:
        source_action = str(event.get("action"))
        tab_key = _text(event.get("tabKey"), 64) or "tab-1"
        if tab_key not in tab_keys:
            tab_keys.append(tab_key)
        target = _target(event)
        fallback_type, fallback_value = _fallback(event)
        options = {
            "recorded": True,
            "recorded_url": _text(event.get("url"), 2000),
            "smart_locator": _smart_locator(event),
        }

        if source_action == "navigate":
            url = _text(event.get("url") or event.get("value"), 2000)
            if not url:
                continue
            action, target, value = "goto", url, url
            fallback_type = fallback_value = ""
        elif source_action == "input":
            action = "input"
            value = _text(event.get("value"), 4000)
            if _sensitive(event, target):
                variable_name = _text(event.get("variableName"), 64) or "password"
                value = "${" + variable_name + "}"
                options["recorded_sensitive"] = True
            options["clear_before_input"] = True
        elif source_action == "select":
            action, value = "select", _text(event.get("value"), 1000)
        elif source_action == "check":
            action, value = "check", ""
            options["recorded_checked"] = bool(event.get("checked"))
        elif source_action == "upload":
            # File paths cannot be captured safely by browsers. Keep an explicit
            # placeholder so the editor can ask the user to select platform files.
            action, value = "upload_file", ""
            options["recorded_upload_requires_file"] = True
        else:
            action, value = "click", ""

        # 自定义下拉通常会先产生触发器 click，再产生选项 click。
        # 合并为一个 select 步骤，回放时由执行器打开下拉并选择目标项。
        if source_action == "click" and steps:
            previous = steps[-1]
            element = event.get("element") if isinstance(event.get("element"), dict) else {}
            option_role = _text(element.get("role"), 32).lower()
            option_tag = _text(element.get("tag"), 32).lower()
            if (
                previous.get("action") == "click"
                and previous.get("tab_key") == tab_key
                and _looks_like_select_trigger(previous)
                and target != "页面元素"
                and (option_role in {"option", "menuitem"} or option_tag in {"span", "div", "li"})
            ):
                previous["action"] = "select"
                previous["value"] = target
                previous["options"]["recorded_select_option"] = True
                previous["target"] = _select_trigger_target(previous, target)
                last_signature = (
                    "select", tab_key, previous.get("target"),
                    previous.get("fallback_type"), previous.get("fallback_value"),
                )
                continue

        # Browsers emit click before input/change for the same form control.
        # The click is implementation noise, not a business step.
        if source_action in {"input", "select", "check", "upload"} and steps:
            previous = steps[-1]
            if (
                previous.get("action") == "click"
                and previous.get("tab_key") == tab_key
                and _same_recorded_element(previous, target, fallback_type, fallback_value)
            ):
                steps.pop()
                for index, existing in enumerate(steps, start=1):
                    existing["order"] = index

        signature = (action, tab_key, target, fallback_type, fallback_value)
        if action == "input" and steps and signature == last_signature:
            steps[-1]["value"] = value
            steps[-1]["options"].update(options)
            continue
        if source_action == "navigate" and steps and steps[-1]["action"] == "goto" and steps[-1]["value"] == value:
            continue

        steps.append({
            "order": len(steps) + 1,
            "tab_key": tab_key,
            "action": action,
            "target": target,
            "value": value,
            "locator_mode": "auto",
            "fallback_type": fallback_type,
            "fallback_value": fallback_value,
            "options": options,
            "continue_on_failure": False,
        })
        last_signature = signature

    tabs = [
        {"key": key, "name": "Tab " + str(index), "order": index}
        for index, key in enumerate(tab_keys or ["tab-1"], start=1)
    ]
    return {"tabs": tabs, "steps": steps, "code": compile_playwright_code(steps)}


def compile_playwright_code(steps: list[dict[str, Any]]) -> str:
    """Generate an export/preview; canonical execution still uses the DSL."""
    lines = ["from playwright.sync_api import Page", "", "", "def run(page: Page):"]
    for step in steps:
        action = step["action"]
        target = json.dumps(step.get("target", ""), ensure_ascii=False)
        value = json.dumps(step.get("value", ""), ensure_ascii=False)
        if action == "goto":
            line = f"page.goto({value})"
        else:
            locator = f"page.get_by_text({target}, exact=True)"
            smart = (step.get("options") or {}).get("smart_locator") or {}
            role = smart.get("role")
            if role:
                locator = f"page.get_by_role({json.dumps(role)}, name={target}, exact=True)"
            if action == "input":
                line = f"{locator}.fill({value})"
            elif action == "select":
                line = f"{locator}.select_option(label={value})"
            elif action == "check":
                line = f"{locator}.set_checked(not {locator}.is_checked())"
            elif action == "upload_file":
                line = f"{locator}.set_input_files(\"<请在平台中选择上传文件>\")"
            else:
                line = f"{locator}.click()"
        lines.append("    " + line)
    if not steps:
        lines.append("    pass")
    return "\n".join(lines) + "\n"
