"""Playwright 智能 UI 执行器。

该执行器只处理 PlaywrightCase/PlaywrightStep，既有 Selenium 执行器完全不变。
"""
import re
import base64
import time
import os
import json
import copy
import shutil
import subprocess
from datetime import datetime
from urllib.parse import urljoin
from types import SimpleNamespace
from pathlib import Path

import yaml

from project.models import Environment, ProjectVariable
from case_ui.browser_token import (
    playwright_cookie,
    should_inject_environment_auth,
    storage_init_script,
)
from case_ui.models import playwright_step_display_name
from case_ui.scenario_text import MASKED_SECRET
from case_ui.smart_locator import SmartLocatorError, resolve as resolve_smart
from case_ui.smart_locator.engine import start_ui_transition_watch, wait_for_dialog_state, wait_for_ui_transition
from case_ui.smart_locator.fingerprints import load_for_step, remember_for_step
from case_ui.smart_locator.normalizer import normalize, semantic_terms
from suite.reporting import load_variable_resolution, record_variable_resolution, recalculate_native_report
from suite.execution_log import write_execution_log

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None
    PlaywrightTimeoutError = TimeoutError


_VARIABLE = re.compile(r"\$\{([^}]+)\}")
SENSITIVE = re.compile(r"password|passwd|pwd|token|secret|authorization|密码|密钥", re.I)
OCR_TIMEOUT_SECONDS = 10
OCR_LANGUAGES = {
    "auto": "chi_sim+eng",
    "zh": "chi_sim",
    "en": "eng",
}
COMMIT_CLICK_TARGETS = {
    "创建", "确定", "确认", "提交", "保存", "完成", "登录", "注册",
    "create", "ok", "confirm", "submit", "save", "finish", "login", "register",
}


def _persist_native_result(report):
    """把子进程步骤结果落盘，由套件主进程在收口时统一合并，避免 JSON 字段并发覆盖。"""
    case_id = report.get("case_id")
    if case_id is None:
        return
    path = Path.cwd() / f"playwright_native_result_{case_id}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def _update_native_step(case_id, step_id, **changes):
    result_id = os.environ.get("PLATFORM_RUN_RESULT_ID")
    if not result_id:
        return
    try:
        from suite.models import RunResult
        result = RunResult.objects.get(id=int(result_id))
        report = result.native_report or {}
        group = next((item for item in report.get("scenarios", []) if str(item.get("id")) == f"playwright-ui-{case_id}"), None)
        if not group:
            return
        target = next((item for item in group.get("steps", []) if str(item.get("source_step_id")) == str(step_id)), None)
        if target:
            target.update(changes)
            # UI 提取变量在子进程中产生，实时报告也要立即同步解析轨迹。
            report["variable_resolution"] = load_variable_resolution(Path.cwd())
            recalculate_native_report(report)
            result.native_report = report
            result.save(update_fields=["native_report", "update_datetime"])
    except Exception:
        # 报告写入失败不能改变 Playwright 本身的测试结论。
        return


def _replace(value, variables):
    text = str(value or "")
    return _VARIABLE.sub(lambda m: str(variables.get(m.group(1), m.group(0))), text)


def _replace_runtime(value, variables):
    """递归解析步骤扩展配置中的变量。

    行定位条件保存在 options.smart_locator.row 中，必须和 target/value
    使用同一份运行时变量，否则 ${created_email} 会被当成普通文本。
    """
    if isinstance(value, dict):
        return {key: _replace_runtime(item, variables) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_runtime(item, variables) for item in value]
    if isinstance(value, tuple):
        return tuple(_replace_runtime(item, variables) for item in value)
    return _replace(value, variables) if isinstance(value, str) else value


def _input_text(locator, value, timeout, clear_before_input=True):
    """按步骤配置输入文本；关闭清空时保留控件原值并追加。"""
    if clear_before_input:
        locator.fill("", timeout=timeout)
        locator.fill(value, timeout=timeout)
    else:
        locator.click(timeout=timeout)
        locator.press_sequentially(value, timeout=timeout)


def _toggle_checked(locator, timeout):
    """统一切换原生复选框及 ``role=switch`` 自定义开关。"""
    get_attribute = getattr(locator, "get_attribute", None)
    aria_checked = get_attribute("aria-checked", timeout=timeout) if get_attribute else None
    data_state = get_attribute("data-state", timeout=timeout) if get_attribute else None
    custom_state = None
    if aria_checked in {"true", "false"}:
        custom_state = aria_checked == "true"
    elif data_state in {"checked", "unchecked", "on", "off"}:
        custom_state = data_state in {"checked", "on"}

    if custom_state is not None:
        locator.click(timeout=timeout)
        aria_after = locator.get_attribute("aria-checked", timeout=timeout)
        state_after = locator.get_attribute("data-state", timeout=timeout)
        checked_after = (
            aria_after == "true"
            if aria_after in {"true", "false"}
            else state_after in {"checked", "on"}
        )
        return {"checked_before": custom_state, "checked_after": checked_after}

    checked_before = bool(locator.is_checked(timeout=timeout))
    if checked_before:
        locator.uncheck(timeout=timeout)
    else:
        locator.check(timeout=timeout)
    return {"checked_before": checked_before, "checked_after": not checked_before}


def _ensure_unchecked(locator, timeout):
    """兼容原生复选框和自定义开关的显式取消勾选。"""
    get_attribute = getattr(locator, "get_attribute", None)
    aria_checked = get_attribute("aria-checked", timeout=timeout) if get_attribute else None
    data_state = get_attribute("data-state", timeout=timeout) if get_attribute else None
    if aria_checked in {"true", "false"} or data_state in {"checked", "unchecked", "on", "off"}:
        checked_before = aria_checked == "true" if aria_checked in {"true", "false"} else data_state in {"checked", "on"}
        if checked_before:
            locator.click(timeout=timeout)
        return {"checked_before": checked_before, "checked_after": False}
    checked_before = bool(locator.is_checked(timeout=timeout))
    if checked_before:
        locator.uncheck(timeout=timeout)
    return {"checked_before": checked_before, "checked_after": False}


def _is_commit_click(target, resolution):
    """识别会触发表单提交或异步保存的点击操作。"""
    element = (resolution or {}).get("element") or {}
    return (
        normalize(target) in {normalize(item) for item in COMMIT_CLICK_TARGETS}
        or str(element.get("type") or "").lower() == "submit"
    )


def _wait_for_commit_click(page, target, resolution, was_in_dialog, timeout):
    """等待提交型点击真正完成，避免末步骤尚在请求时就关闭浏览器。"""
    if not _is_commit_click(target, resolution):
        return {"commit_click": False}

    wait_timeout = min(max(int(timeout), 1000), 5000)
    network_idle = False
    try:
        page.wait_for_load_state("networkidle", timeout=wait_timeout)
        network_idle = True
    except PlaywrightTimeoutError:
        # 长连接或轮询页面可能一直达不到 networkidle，继续以弹窗状态判断结果。
        network_idle = False

    dialog_closed = None
    if was_in_dialog:
        dialog_closed = wait_for_dialog_state(page, visible=False, timeout=min(wait_timeout, 3000))
        if not dialog_closed:
            raise RuntimeError(
                f"点击“{target}”后弹窗未关闭，提交可能被表单校验或接口错误阻止。"
            )
    return {
        "commit_click": True,
        "network_idle": network_idle,
        **({"dialog_closed": dialog_closed} if dialog_closed is not None else {}),
    }


def _load_runtime_variables():
    path = Path.cwd() / "extract.yaml"
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as file:
            values = yaml.safe_load(file) or {}
        return values if isinstance(values, dict) else {}
    except Exception:
        return {}


def _save_runtime_variables(values):
    try:
        with (Path.cwd() / "extract.yaml").open("w", encoding="utf-8") as file:
            yaml.safe_dump(values, file, allow_unicode=True, sort_keys=False)
    except Exception:
        pass


def _capture_step_screenshot(page, case_id, step_id, status):
    """保存步骤当前视区，路径相对本次执行目录，便于原生报告展示。"""
    if page is None:
        return ""
    try:
        if case_id is None:
            image = page.screenshot(
                full_page=False, animations="disabled", caret="hide", scale="css",
            )
            return "data:image/png;base64," + base64.b64encode(image).decode("ascii")
        normalized_status = "passed" if status == "passed" else "failed"
        relative_path = Path("screenshots") / (
            f"playwright_{normalized_status}_{case_id}_{step_id}_{int(time.time() * 1000)}.png"
        )
        target = Path.cwd() / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(
            path=str(target),
            full_page=False,
            animations="disabled",
            caret="hide",
            scale="css",
        )
        return relative_path.as_posix()
    except Exception:
        # 截图失败不能覆盖步骤本身的执行结果。
        return ""


def _capture_ocr_screenshot(locator, case_id, step_id):
    """仅截取提取目标元素，供 OCR 识别和报告回溯使用。"""
    try:
        relative_path = Path("screenshots") / (
            f"playwright_ocr_{case_id}_{step_id}_{int(time.time() * 1000)}.png"
        )
        target = Path.cwd() / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        locator.screenshot(path=str(target), animations="disabled", caret="hide", scale="css")
        return relative_path.as_posix()
    except Exception:
        return ""


def _normalize_ocr_text(value):
    return "\n".join(line.strip() for line in str(value or "").splitlines() if line.strip()).strip()


def _ocr_image(relative_path, language="auto"):
    """通过系统 Tesseract 识别元素截图；失败只返回原因，不影响 DOM 提取。"""
    executable = shutil.which("tesseract")
    if not executable:
        return "", "OCR 引擎不可用：未找到 tesseract 命令。"
    language_key = str(language or "auto").lower()
    tesseract_language = OCR_LANGUAGES.get(language_key, OCR_LANGUAGES["auto"])
    image_path = Path.cwd() / relative_path
    last_error = ""
    # 先按单行文本优化（按钮、验证码、数值），为空时再按文本块识别。
    for page_segmentation_mode in ("7", "6"):
        try:
            result = subprocess.run(
                [
                    executable,
                    str(image_path),
                    "stdout",
                    "-l",
                    tesseract_language,
                    "--psm",
                    page_segmentation_mode,
                ],
                capture_output=True,
                text=True,
                timeout=OCR_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return "", f"OCR 识别超时（{OCR_TIMEOUT_SECONDS} 秒）。"
        except OSError as exc:
            return "", f"OCR 引擎启动失败：{exc}"
        if result.returncode != 0:
            last_error = (result.stderr or result.stdout or "未知错误").strip()[-300:]
            continue
        recognized = _normalize_ocr_text(result.stdout)
        if recognized:
            return recognized, ""
    return "", f"OCR 识别失败：{last_error}" if last_error else ""


def _safe(step, value):
    return "***" if SENSITIVE.search(str(getattr(step, "target", ""))) else value


def _extract_text(locator, timeout):
    """读取元素实际可用的文本；表单控件优先读取 value 属性。"""
    tag = str(locator.evaluate("element => element.tagName.toLowerCase()") or "").lower()
    if tag in {"input", "textarea", "select"}:
        return locator.input_value(timeout=timeout)
    return locator.inner_text(timeout=timeout)


def _extract_text_with_ocr(locator, step, case_id, step_id, timeout):
    """DOM 提取为空时按配置使用 OCR 作为兜底，返回值及可回溯的提取元数据。"""
    extracted = _extract_text(locator, timeout)
    tag = str(locator.evaluate("element => element.tagName.toLowerCase()") or "").lower()
    source = "dom_value" if tag in {"input", "textarea", "select"} else "dom_text"
    if str(extracted or "").strip():
        return extracted, {"extraction_source": source}

    options = getattr(step, "options", None) or {}
    if not bool(options.get("ocr_fallback")):
        return extracted, {"extraction_source": source, "ocr_status": "disabled"}
    if SENSITIVE.search(str(getattr(step, "target", ""))):
        return extracted, {
            "extraction_source": source,
            "ocr_status": "skipped_sensitive",
            "ocr_error": "敏感字段禁止 OCR 识别。",
        }

    language = str(options.get("ocr_language") or "auto").lower()
    screenshot_path = _capture_ocr_screenshot(locator, case_id, step_id)
    if not screenshot_path:
        return extracted, {
            "extraction_source": source,
            "ocr_status": "screenshot_failed",
            "ocr_error": "OCR 截图保存失败。",
        }
    ocr_text, error = _ocr_image(screenshot_path, language)
    metadata = {
        "extraction_source": "ocr" if ocr_text else source,
        "ocr_status": "recognized" if ocr_text else "empty",
        "ocr_language": language,
        "ocr_screenshot": {"path": screenshot_path, "label": "OCR 提取截图"},
    }
    if error:
        metadata["ocr_error"] = error
    return ocr_text or extracted, metadata


def _step_name(step):
    return playwright_step_display_name(
        getattr(step, "action", ""), getattr(step, "target", ""), getattr(step, "value", "")
    )


def _step_timeout(options, default_timeout):
    """步骤配置默认使用秒；兼容历史前端保存的毫秒值。"""
    configured = (options or {}).get("timeout")
    if configured in (None, ""):
        return int(default_timeout)
    seconds = float(configured)
    if seconds <= 0:
        raise ValueError("步骤超时必须大于 0 秒。")
    # 历史编辑器把步骤 timeout 以毫秒（如 10000）写入 options，继续按原语义执行。
    if seconds > 300:
        return round(seconds)
    return max(1, round(seconds * 1000))


def _click_targets(target):
    """点击步骤可用 -- 分隔多个按顺序执行的语义元素。"""
    targets = [part.strip() for part in str(target or "").split("--")]
    if not all(targets):
        raise ValueError("连续点击的每个页面元素都不能为空，请用 -- 分隔元素名称。")
    return targets


def _resolve_open_dropdown_option(page, trigger_box, target):
    """定位刚展开的无 ARIA 自定义下拉项，不把页面上同名普通文本当作按钮。"""
    if not isinstance(trigger_box, dict) or not all(
        isinstance(trigger_box.get(key), (int, float)) for key in ("x", "y", "width", "height")
    ):
        return None
    token = f"pw-click-option-{int(time.time() * 1000000)}"
    try:
        result = page.evaluate("""({triggerBox, target, token}) => {
            triggerBox = {
                left: triggerBox.x, right: triggerBox.x + triggerBox.width,
                bottom: triggerBox.y + triggerBox.height,
                width: triggerBox.width, height: triggerBox.height
            };
            if (!triggerBox.width || !triggerBox.height) return {count: 0};
            const visible = element => {
                const style = getComputedStyle(element), box = element.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden'
                    && Number(style.opacity || 1) !== 0 && box.width > 0 && box.height > 0;
            };
            const exact = element => (element.innerText || '').trim() === target;
            const candidates = [...document.querySelectorAll('div, span, li, p, button, [role="option"]')]
                .filter(element => visible(element) && exact(element))
                .filter(element => ![...element.children].some(child => visible(child) && exact(child)))
                .map(element => {
                    let option = element;
                    for (let parent = element.parentElement; parent && parent !== document.body;
                         parent = parent.parentElement) {
                        if (!exact(parent)) break;
                        const style = getComputedStyle(parent);
                        if (parent.matches('button, li, [role="option"], [role="menuitem"]')
                            || style.cursor === 'pointer') { option = parent; break; }
                    }
                    const box = option.getBoundingClientRect();
                    const x = box.left + box.width / 2, y = box.top + box.height / 2;
                    const hit = document.elementFromPoint(x, y);
                    return {option, box, hit};
                })
                .filter(({option, box, hit}) =>
                    box.top >= triggerBox.bottom - 12 && box.top <= triggerBox.bottom + 500
                    && box.left <= triggerBox.right + 40 && box.right >= triggerBox.left - 40
                    && hit && hit !== document.body && hit !== document.documentElement
                    && (option.contains(hit) || hit === option.parentElement)
                );
            const unique = [...new Set(candidates.map(item => item.option))];
            if (unique.length === 1) unique[0].setAttribute('data-pw-click-option', token);
            return {count: unique.length};
        }""", {"triggerBox": trigger_box, "target": target, "token": token})
    except Exception:
        return None
    if (result or {}).get("count") != 1:
        return None
    locator = page.locator(f'[data-pw-click-option="{token}"]')
    return locator, {"strategy": "opened_dropdown_exact_text", "confidence": 100,
                     "matched_phrase": target, "element": {"text": target, "inDialog": True}}


def _execute_click_targets(page, step, timeout):
    targets = _click_targets(step.target)
    if len(targets) > 1 and (step.locator_mode == "manual" or step.fallback_value):
        raise ValueError("连续点击不支持共用手动定位表达式，请分别创建点击步骤。")

    clicks = []
    previous_box = None
    for index, target in enumerate(targets, start=1):
        current_step = copy.copy(step)
        current_step.target = target
        if len(targets) > 1:
            # 一个步骤只有一份持久化指纹，不能把最后一次点击的指纹用于定位第一项。
            current_step.id = None
            current_step.options = copy.deepcopy(step.options or {})
            smart = current_step.options.get("smart_locator")
            if isinstance(smart, dict):
                smart.pop("aliases", None)
                smart.pop("role", None)
        try:
            try:
                locator, resolution = _resolve(page, current_step, timeout)
            except SmartLocatorError:
                option = _resolve_open_dropdown_option(page, previous_box, target)
                if option is None:
                    raise
                locator, resolution = option
            _remember_runtime_anchor(locator)
            was_in_dialog = bool((resolution or {}).get("element", {}).get("inDialog"))
            try:
                clicked_box = locator.bounding_box() if len(targets) > 1 else None
            except Exception:
                clicked_box = None
            transition_token = start_ui_transition_watch(page)
            locator.click(timeout=timeout)
            transition = wait_for_ui_transition(page, transition_token, timeout=min(timeout, 1500))
            commit = _wait_for_commit_click(page, target, resolution, was_in_dialog, timeout)
            if normalize(target) in {"删除", "移除", "delete", "remove"}:
                wait_for_dialog_state(page, visible=not was_in_dialog, timeout=min(timeout, 1500))
        except Exception as exc:
            raise RuntimeError(f"第 {index}/{len(targets)} 个点击元素“{target}”失败：{exc}") from exc
        if len(targets) == 1 and resolution and not resolution.get("strategy", "").startswith("manual:"):
            remember_for_step(step.id, step.environment_name, resolution)
        clicks.append({"target": target, "resolution": resolution, "ui_transition": transition, **commit})
        previous_box = clicked_box

    if len(clicks) == 1:
        return {key: value for key, value in clicks[0].items() if key != "target"}
    return {"clicks": clicks, "click_count": len(clicks), "resolution": clicks[-1]["resolution"]}


def _steps_from_payload(data):
    """构造运行步骤时保留报告分组所需的稳定 Tab 标识。"""
    return [SimpleNamespace(**{
        "id": item.get("id"), "action": item.get("action", ""),
        "tab_key": item.get("tab_key", "tab-1"),
        "target": item.get("target", ""), "value": item.get("value", ""),
        "locator_mode": item.get("locator_mode", "auto"), "fallback_type": item.get("fallback_type", ""),
        "fallback_value": item.get("fallback_value", ""), "options": item.get("options") or {},
        "continue_on_failure": item.get("continue_on_failure", False),
    }) for item in data.get("steps") or []]


def _steps_for_tab(steps, tab_key=None):
    """返回指定 Tab 的步骤；未指定时保持完整用例执行行为。"""
    selected_tab_key = str(tab_key or "").strip()
    if not selected_tab_key:
        return list(steps), ""
    selected = [step for step in steps if str(getattr(step, "tab_key", "")) == selected_tab_key]
    if not selected:
        raise ValueError(f"当前 Tab（{selected_tab_key}）没有可执行步骤。")
    return selected, selected_tab_key


def _css_attribute_value(value):
    """转义 CSS 属性选择器中的双引号和反斜杠。"""
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _xpath_literal(value):
    """生成可安全放入 XPath 的字符串字面量。"""
    text = str(value)
    if "'" not in text:
        return f"'{text}'"
    if '"' not in text:
        return f'"{text}"'
    return "concat(" + ", \"'\", ".join(f"'{part}'" for part in text.split("'")) + ")"


def _valid_xpath_expression(value):
    """识别可直接交给 Playwright 的 XPath，排除 email 这类语义名称。"""
    expression = str(value or "").strip()
    return expression.startswith(("/", "./", "(", "id(", "ancestor::", "descendant::"))


def _resolve_manual(page, step, timeout):
    if step.locator_mode == "manual" or step.fallback_value:
        locator_type = (step.fallback_type or "css_selector").lower()
        locator_value = step.fallback_value
        if locator_type in {"testid", "test_id"}:
            locator = page.get_by_test_id(locator_value)
        elif locator_type == "role":
            locator = page.get_by_role("button", name=locator_value, exact=True)
        elif locator_type == "id":
            locator = page.locator(f'[id="{_css_attribute_value(locator_value)}"]')
        elif locator_type == "name":
            locator = page.locator(f'[name="{_css_attribute_value(locator_value)}"]')
        elif locator_type == "class_name":
            if any(character.isspace() for character in locator_value):
                raise ValueError("Class Name 只能填写一个类名，不能包含空格。")
            class_literal = _xpath_literal(locator_value)
            locator = page.locator(
                f"xpath=//*[contains(concat(' ', normalize-space(@class), ' '), "
                f"concat(' ', {class_literal}, ' '))]"
            )
        elif locator_type == "link_text":
            locator = page.get_by_role("link", name=locator_value, exact=True)
        elif locator_type == "xpath":
            locator = page.locator(f"xpath={locator_value}")
        else:
            locator = page.locator(locator_value)
        locator.wait_for(state="visible", timeout=timeout)
        if locator.count() != 1:
            raise ValueError(f"手动定位表达式匹配到 {locator.count()} 个元素，必须唯一。")
        return locator, {"strategy": f"manual:{locator_type}", "confidence": 100, "candidates": []}


def _resolve_recorded_select_trigger(page, step, timeout):
    """用录制时显示值锁定自定义下拉触发器，避免通用 Select option 冲突。"""
    options = getattr(step, "options", None) or {}
    if str(getattr(step, "action", "")) != "select" or not options.get("recorded_select_option"):
        return None
    smart = options.get("smart_locator") or {}
    generic = {
        "select option", "choose option", "select", "choose",
        "选择选项", "请选择", "选择", "下拉选择", "页面元素",
    }
    normalized_generic = {normalize(item) for item in generic}
    option_value = normalize(getattr(step, "value", ""))
    phrases = []
    for raw in [getattr(step, "target", ""), *(smart.get("aliases") or [])]:
        phrase = str(raw or "").strip()
        if not phrase or normalize(phrase) in normalized_generic or normalize(phrase) == option_value:
            continue
        if phrase not in phrases:
            phrases.append(phrase)
    for phrase in phrases:
        candidates = []
        for role in ("combobox", "button"):
            candidates = _visible_matches(page.get_by_role(role, name=phrase, exact=True))
            if candidates:
                break
        if not candidates:
            candidates = _visible_matches(
                page.get_by_text(phrase, exact=True).locator(
                    "xpath=ancestor-or-self::*[self::button or @role='combobox'][1]"
                )
            )
        if len(candidates) == 1:
            locator = candidates[0]
            locator.wait_for(state="visible", timeout=timeout)
            locator.scroll_into_view_if_needed(timeout=timeout)
            return locator, {
                "strategy": "recorded_select_trigger",
                "confidence": 100,
                "matched_phrase": phrase,
                "candidates": [],
            }
    return None


def _resolve_recorded_generic_element(page, step, timeout):
    """恢复旧版录制中缺失语义名称的控件。

    仅处理明确标记为录制生成的步骤，并以刚执行过的控件为锚点，在同一弹窗内
    选择紧随其后的同类型表单控件，避免对人工创建步骤进行猜测。
    """
    options = getattr(step, "options", None) or {}
    if not options.get("recorded") or normalize(getattr(step, "target", "")) not in {
        normalize("页面元素"), normalize("输入框"), normalize("数字输入框")
    }:
        return None
    smart = options.get("smart_locator") or {}
    input_types = [str(item or "").lower() for item in smart.get("input_types") or [] if item]
    if not input_types:
        return None
    token = f"pw-recorded-generic-{int(time.time() * 1000000)}"
    try:
        result = page.evaluate("""({token, inputTypes}) => {
            const visible = element => {
                const style = getComputedStyle(element), box = element.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden'
                    && Number(style.opacity || 1) !== 0 && box.width > 0 && box.height > 0;
            };
            const anchor = window.__autotestPreviousElementRect;
            if (!anchor) return {count: 0};
            const activeDialog = [...document.querySelectorAll('[role="dialog"],dialog,[aria-modal="true"]')]
                .filter(visible).at(-1) || null;
            const controls = [...document.querySelectorAll('input,textarea,select')].filter(element => {
                if (!visible(element) || element.disabled) return false;
                if (activeDialog && !activeDialog.contains(element)) return false;
                const type = String(element.getAttribute('type') || element.tagName).toLowerCase();
                return inputTypes.includes(type);
            });
            const ranked = controls.map(element => {
                const box = element.getBoundingClientRect();
                const vertical = box.top - anchor.bottom;
                const horizontal = Math.abs(box.left - anchor.left);
                const score = (vertical < -8 ? 10000 + Math.abs(vertical) : vertical) + horizontal * .25;
                return {element, score, vertical};
            }).filter(item => item.vertical >= -8).sort((a, b) => a.score - b.score);
            if (!ranked.length) return {count: 0};
            ranked[0].element.setAttribute('data-pw-recorded-generic', token);
            return {count: 1};
        }""", {"token": token, "inputTypes": input_types})
    except Exception:
        return None
    if int((result or {}).get("count") or 0) != 1:
        return None
    locator = page.locator(f'[data-pw-recorded-generic="{token}"]')
    locator.wait_for(state="visible", timeout=timeout)
    locator.scroll_into_view_if_needed(timeout=timeout)
    return locator, {
        "strategy": "recorded_relative_control",
        "confidence": 96,
        "candidates": [],
    }


def _remember_runtime_anchor(locator):
    """记录已定位控件位置，供下一条旧版录制步骤恢复语义。"""
    try:
        locator.evaluate("""element => {
            const box = element.getBoundingClientRect();
            window.__autotestPreviousElementRect = {
                left: box.left, right: box.right, top: box.top, bottom: box.bottom,
                width: box.width, height: box.height
            };
        }""")
    except Exception:
        pass


def _resolve(page, step, timeout):
    """自动定位优先；仅在自动定位失败且已配置兜底时使用手动表达式。"""
    if step.action == "upload_file" and step.locator_mode != "manual":
        return _resolve_upload_input(page, step, timeout)
    if step.locator_mode == "manual":
        if str(step.fallback_type or "").lower() == "xpath" and not _valid_xpath_expression(step.fallback_value):
            # 早期页面会把录制得到的语义名称（例如 email）误存为 XPath。
            # 该值仍可作为智能定位描述使用，但不能拼成 xpath=email。
            runtime_step = copy.copy(step)
            runtime_step.target = str(step.target or step.fallback_value or "").strip()
            runtime_step.locator_mode = "auto"
            runtime_step.fallback_value = ""
            fingerprint = load_for_step(runtime_step.id, getattr(runtime_step, "environment_name", ""))
            return resolve_smart(page, runtime_step, timeout, fingerprint=fingerprint)
        return _resolve_manual(page, step, timeout)
    recorded_generic = _resolve_recorded_generic_element(page, step, timeout)
    if recorded_generic:
        return recorded_generic
    recorded_select = _resolve_recorded_select_trigger(page, step, timeout)
    if recorded_select:
        return recorded_select
    try:
        fingerprint = load_for_step(step.id, getattr(step, "environment_name", ""))
        return resolve_smart(page, step, timeout, fingerprint=fingerprint)
    except SmartLocatorError as smart_error:
        if not step.fallback_value:
            raise
        locator, resolution = _resolve_manual(page, step, timeout)
        resolution["smart_locator_error"] = str(smart_error)
        resolution["fallback_used"] = True
        return locator, resolution


def _resolve_upload_input(page, step, timeout):
    """文件控件通常是隐藏的 input；按标签或属性精确匹配，唯一控件时兜底。"""
    target = str(step.target or "").strip()
    file_inputs = page.locator("input[type='file']")
    file_inputs.first.wait_for(state="attached", timeout=timeout)
    labeled = page.get_by_label(target, exact=True)
    matches = []
    for index in range(labeled.count()):
        candidate = labeled.nth(index)
        if candidate.evaluate("el => el.tagName === 'INPUT' && el.type === 'file'"):
            matches.append(candidate)
    if len(matches) == 1:
        return matches[0], {"strategy": "file_input_label", "confidence": 100, "candidates": []}
    if len(matches) > 1:
        raise ValueError(f"上传文件元素「{target}」匹配多个文件控件，请提供更明确的名称。")

    for index in range(file_inputs.count()):
        candidate = file_inputs.nth(index)
        if candidate.evaluate("(el, name) => [el.id, el.name, el.getAttribute('aria-label')].includes(name)", target):
            matches.append(candidate)
    if len(matches) == 1:
        return matches[0], {"strategy": "file_input_attribute", "confidence": 95, "candidates": []}
    if len(matches) > 1:
        raise ValueError(f"上传文件元素「{target}」匹配多个文件控件，请提供更明确的名称。")
    if file_inputs.count() == 1:
        return file_inputs.first, {"strategy": "unique_file_input", "confidence": 75, "candidates": []}
    raise ValueError(f"无法唯一定位上传文件元素「{target}」，请使用关联标签、ID、name 或 aria-label。")


def _ensure_checked(locator, timeout):
    """YAML 的「勾选」是幂等操作，已勾选时不再切换。"""
    get_attribute = getattr(locator, "get_attribute", None)
    aria_checked = get_attribute("aria-checked", timeout=timeout) if get_attribute else None
    data_state = get_attribute("data-state", timeout=timeout) if get_attribute else None
    if aria_checked == "true" or data_state in {"checked", "on"}:
        return {"checked_before": True, "checked_after": True}
    if aria_checked == "false" or data_state in {"unchecked", "off"}:
        return _toggle_checked(locator, timeout)
    if locator.is_checked(timeout=timeout):
        return {"checked_before": True, "checked_after": True}
    return _toggle_checked(locator, timeout)

def _visible_matches(locator):
    matches = []
    try:
        for index in range(locator.count()):
            candidate = locator.nth(index)
            if candidate.is_visible():
                matches.append(candidate)
    except Exception:
        return []
    return matches


def _exact_visible_option(page, scope, phrases):
    """在已打开菜单中按标准化后的可见文本查找唯一操作项。

    Playwright 的锚定正则在部分 portal 菜单文本上不会命中（例如 DOM 中可见的
    ``Delete``）；这里通过一次 DOM 遍历做大小写无关的精确比较，仍然坚持唯一
    命中，不使用固定业务类名，也不会模糊点击相似菜单项。
    """
    token = f"pw-exact-option-{int(time.time() * 1000000)}"
    root = page.locator("body") if scope is page else scope
    try:
        result = root.evaluate("""(root, {phrases, token}) => {
            const compact = value => String(value || '').normalize('NFKC').trim().toLowerCase()
                .replace(/[\\s_\\-:/：()（）,.，。]+/g, '');
            const wanted = new Set(phrases.map(compact).filter(Boolean));
            const visible = element => {
                const style = getComputedStyle(element), box = element.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden'
                    && Number(style.opacity || 1) !== 0 && box.width > 0 && box.height > 0;
            };
            const candidates = [...root.querySelectorAll(
                'button, a, li, [role="option"], [role="menuitem"]'
            )].filter(element => {
                if (!visible(element) || element.disabled) return false;
                const name = element.getAttribute('aria-label') || element.innerText || element.textContent || '';
                return wanted.has(compact(name));
            });
            if (candidates.length === 1) candidates[0].setAttribute('data-pw-exact-option', token);
            return {count: candidates.length};
        }""", {"phrases": list(phrases), "token": token})
    except Exception:
        return None, 0
    count = int((result or {}).get("count") or 0)
    return (page.locator(f'[data-pw-exact-option="{token}"]') if count == 1 else None), count


def _opened_option_scope(page, trigger):
    """只返回当前触发器打开的菜单。

    优先使用 aria-controls/aria-owns 建立确定关系；无关联属性时，选择当前
    最上层且可见的 listbox/menu，不扫描和试点其他表格行。
    """
    try:
        controlled = trigger.get_attribute("aria-controls") or trigger.get_attribute("aria-owns")
        if controlled:
            linked = page.locator(f"#{controlled}")
            if linked.count() == 1 and linked.is_visible():
                return linked
    except Exception:
        pass
    token = f"pw-option-{int(time.time() * 1000000)}"
    try:
        local_popup = trigger.evaluate("""(trigger, token) => {
            const visible = element => {
                const style = getComputedStyle(element), box = element.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden'
                    && Number(style.opacity || 1) !== 0 && box.width > 0 && box.height > 0;
            };
            let current = trigger.parentElement;
            for (let depth = 0; current && depth < 4; depth += 1, current = current.parentElement) {
                if (current.matches('td, th, tr, table, [role="row"], [role="cell"], [role="gridcell"]')) break;
                const candidates = [...current.children].filter(element =>
                    element !== trigger && !element.contains(trigger) && visible(element)
                    && element.querySelector('button, [role="menuitem"], [role="option"]')
                    && (['absolute', 'fixed'].includes(getComputedStyle(element).position)
                        || element.matches('[role="menu"], [role="listbox"]'))
                );
                if (candidates.length === 1) {
                    candidates[0].setAttribute('data-pw-option-scope', token);
                    return true;
                }
            }
            return false;
        }""", token)
        if local_popup:
            return page.locator(f'[data-pw-option-scope="{token}"]')
    except Exception:
        pass
    try:
        selected = page.evaluate("""({token}) => {
            const visible = element => {
                const style = getComputedStyle(element), box = element.getBoundingClientRect();
                return style.display !== 'none' && style.visibility !== 'hidden'
                    && Number(style.opacity || 1) !== 0 && box.width > 0 && box.height > 0;
            };
            const selector = [
                '[role="listbox"]', '[role="menu"]', '.n-base-select-menu',
                '.ant-select-dropdown', '.el-select-dropdown', '.el-dropdown-menu',
                '[data-radix-menu-content]', '[data-radix-select-content]'
            ].join(',');
            const candidates = [...document.querySelectorAll(selector)].filter(visible);
            if (!candidates.length) return false;
            const ranked = candidates.map((element, order) => {
                let zIndex = 0, current = element;
                while (current && current !== document.documentElement) {
                    const value = Number.parseInt(getComputedStyle(current).zIndex, 10);
                    if (Number.isFinite(value)) zIndex = Math.max(zIndex, value);
                    current = current.parentElement;
                }
                return {element, zIndex, order};
            }).sort((left, right) => left.zIndex - right.zIndex || left.order - right.order);
            ranked.at(-1).element.setAttribute('data-pw-option-scope', token);
            return true;
        }""", {"token": token})
        if selected:
            return page.locator(f'[data-pw-option-scope="{token}"]')
    except Exception:
        pass
    return page


def _select_value(page, locator, value, timeout):
    """兼容原生 select 与常见的自定义 combobox/listbox。"""
    tag = locator.evaluate("element => element.tagName.toLowerCase()")
    if tag == "select":
        try:
            locator.select_option(label=value, timeout=timeout)
        except Exception:
            locator.select_option(value=value, timeout=timeout)
        return

    locator.click(timeout=timeout)
    page.wait_for_timeout(80)
    option_scope = _opened_option_scope(page, locator)
    option = None
    scopes = [option_scope]
    # 某些组件把菜单 teleport 到 body 且不设 role/aria-controls。此时只在
    # 已打开菜单之后查找全局唯一可见项，不会去开启其他行的触发器。
    if option_scope is not page:
        scopes.append(page)
    for scope in scopes:
        phrases = semantic_terms(value, {})[0]
        for phrase in phrases:
            exact_phrase = re.compile(rf"^{re.escape(phrase)}$", re.I)
            matches = _visible_matches(scope.get_by_role("option", name=exact_phrase))
            if not matches:
                matches = _visible_matches(scope.get_by_role("menuitem", name=exact_phrase))
            if not matches:
                matches = _visible_matches(scope.get_by_text(exact_phrase).locator(
                    "xpath=ancestor-or-self::*[self::li or self::div or self::button or @role='option' or @role='menuitem'][1]"
                ))
            if len(matches) > 1:
                raise ValueError(f"已打开下拉框，但找到 {len(matches)} 个可见的“{value}”，无法唯一选择。")
            if matches:
                option = matches[0]
                break
        if option is None:
            option, count = _exact_visible_option(page, scope, phrases)
            if count > 1:
                raise ValueError(f"已打开下拉框，但找到 {count} 个可见的“{value}”，无法唯一选择。")
        if option is not None:
            break
    if option is None:
        raise ValueError(f"已打开下拉框，但未找到下拉项“{value}”。")
    option.scroll_into_view_if_needed(timeout=timeout)
    option.click(timeout=timeout)


def execute_playwright_case(case, tab_key=None, *, raise_on_failure=True):
    if sync_playwright is None:
        raise RuntimeError("未安装 Playwright，请执行 pip install playwright，并安装浏览器依赖。")
    variables = _load_runtime_variables()
    if isinstance(case, dict):
        data = case
        steps = _steps_from_payload(data)
        case_id = data.get("id")
        project_id = data.get("project_id")
        case_name = data.get("name", "Playwright 用例")
        browser_name = data.get("browser", "chromium")
        run_mode = data.get("run_mode", "headless")
        default_timeout = int(data.get("default_timeout", 10000))
        base_url = str(data.get("base_url") or "")
        viewport = data.get("viewport") or {"width": 1440, "height": 900}
        environment_name = str(data.get("environment_name") or "")
        environment = Environment.objects.filter(project_id=project_id, name=environment_name).first()
        if not base_url and environment:
            base_url = environment.base_url
    else:
        case_id = case.id
        project_id = case.project_id
        steps = list(case.steps.select_related("case").all())
        case_name = case.name
        browser_name = case.browser
        run_mode = case.run_mode
        default_timeout = case.default_timeout
        viewport = case.viewport or {"width": 1440, "height": 900}
        environment = None
        if case.environment_name:
            environment = Environment.objects.filter(project=case.project, name=case.environment_name).first()
        base_url = environment.base_url if environment else ""
        environment_name = str(case.environment_name or "")
    for key, variable_value in ProjectVariable.values_for_projects([project_id]).items():
        variables.setdefault(key, variable_value)
    steps, selected_tab_key = _steps_for_tab(steps, tab_key)
    navigation_targets = [
        _replace(step.value, variables) or _replace(step.target, variables)
        for step in steps
        if step.action == "goto"
    ]
    token_variables = variables if os.environ.get("PLATFORM_RUN_RESULT_ID") else {}
    browser_token = (
        environment.browser_token_payload(token_variables, Path.cwd())
        if environment and should_inject_environment_auth(base_url, navigation_targets)
        else {}
    )
    for step in steps:
        # 套件执行环境优先于用例默认环境，用于选择环境级定位覆盖和历史指纹。
        step.environment_name = str(
            (data.get("environment_name") if isinstance(case, dict) else case.environment_name) or ""
        )
    report = {
        "case_id": case_id, "name": case_name, "engine": "playwright",
        "tab_key": selected_tab_key, "passed": True, "steps": [],
    }
    write_execution_log(
        f"智能 UI 用例开始：{case_name} · 浏览器 {browser_name} · "
        f"模式 {'有界面' if run_mode == 'headed' else '无界面'} · 共 {len(steps)} 步"
    )
    with sync_playwright() as playwright:
        browser_type = getattr(playwright, browser_name, None)
        if browser_type is None:
            raise ValueError(f"不支持的浏览器：{browser_name}")
        browser_started_at = datetime.now().astimezone().isoformat()
        try:
            browser = browser_type.launch(headless=run_mode != "headed")
        except Exception as exc:
            error = f"浏览器启动失败：{exc}"
            write_execution_log(f"智能 UI {error}", "ERROR")
            report["passed"] = False
            if steps:
                report["steps"].append({
                    "id": steps[0].id, "name": _step_name(steps[0]),
                    "action": steps[0].action, "target": steps[0].target,
                    "tab_key": getattr(steps[0], "tab_key", ""), "status": "failed",
                    "passed": False, "duration_ms": 0, "error": error,
                })
                _update_native_step(
                    case_id, steps[0].id, status="failed", passed=False,
                    started_at=browser_started_at,
                    finished_at=datetime.now().astimezone().isoformat(),
                    duration_ms=0, errors=[error], exception=str(exc),
                )
                for pending_step in steps[1:]:
                    _update_native_step(
                        case_id, pending_step.id, status="skipped", passed=None,
                        duration_ms=0, skip_reason="浏览器启动失败，后续步骤未执行。",
                    )
            _persist_native_result(report)
            raise RuntimeError(error) from exc
        try:
            context = browser.new_context(viewport=viewport)
            init_script = storage_init_script(browser_token)
            if init_script:
                context.add_init_script(script=init_script)
            cookie = playwright_cookie(browser_token, base_url)
            if cookie:
                context.add_cookies([cookie])
            page = context.new_page()
            write_execution_log("智能 UI 浏览器已启动，会话准备完成")
            for step in steps:
                started = time.perf_counter()
                started_at = datetime.now().astimezone().isoformat()
                item = {
                    "id": step.id, "name": _step_name(step), "action": step.action,
                    "target": step.target, "tab_key": getattr(step, "tab_key", ""),
                    "status": "running", "started_at": started_at,
                }
                report["steps"].append(item)
                _persist_native_result(report)
                _update_native_step(case_id, step.id, status="running", started_at=started_at)
                write_execution_log(
                    f"智能 UI 步骤 {len(report['steps'])}/{len(steps)} 开始：{_step_name(step)}"
                )
                timeout = _step_timeout(step.options, default_timeout)
                try:
                    value = _replace(step.value, variables)
                    target = _replace(step.target, variables)
                    if (step.action == "input" and (step.options or {}).get("source_format") == "scenario_text"
                            and MASKED_SECRET.fullmatch(value)):
                        raise ValueError("输入步骤仍是 *** 占位符，请填写真实值或项目变量后再执行。")
                    if (step.options or {}).get("source_format") == "scenario_text" and (
                        _VARIABLE.search(value) or _VARIABLE.search(target)
                    ):
                        raise ValueError("场景变量未解析，请在项目变量中配置所引用的变量。")
                    runtime_step = copy.copy(step)
                    runtime_step.value = value
                    runtime_step.target = target
                    runtime_step.options = _replace_runtime(step.options, variables)
                    resolution = None
                    if step.action == "goto":
                        url = value or target
                        if not url.startswith(("http://", "https://")):
                            url = urljoin(base_url.rstrip("/") + "/", url.lstrip("/"))
                        page.goto(url, timeout=timeout, wait_until="domcontentloaded")
                        detail = {"url": page.url}
                    elif step.action == "sleep":
                        page.wait_for_timeout(int(float(value) * 1000))
                        detail = {"seconds": float(value)}
                    elif step.action == "click":
                        detail = _execute_click_targets(page, runtime_step, timeout)
                    else:
                        locator, resolution = _resolve(page, runtime_step, timeout)
                        _remember_runtime_anchor(locator)
                        if step.action == "upload_file":
                            from case_ui.file_utils import resolve_uploaded_file
                            file_ids = (runtime_step.options or {}).get("file_ids", [])
                            if not isinstance(file_ids, list) or not file_ids:
                                raise ValueError("上传文件步骤未选择文件。")
                            paths = [str(resolve_uploaded_file(file_id, project_id)[0]) for file_id in file_ids]
                            locator.set_input_files(paths, timeout=timeout)
                            detail = {"files": [Path(path).name for path in paths], "count": len(paths), "resolution": resolution}
                        elif step.action == "input":
                            clear_before_input = bool(runtime_step.options.get("clear_before_input", True))
                            _input_text(locator, value, timeout, clear_before_input)
                            detail = {
                                "value": _safe(step, value), "resolution": resolution,
                                "clear_before_input": clear_before_input,
                            }
                        elif step.action == "clear":
                            locator.fill("", timeout=timeout); detail = {"resolution": resolution}
                        elif step.action == "select":
                            _select_value(page, locator, value, timeout); detail = {"value": value, "resolution": resolution}
                        elif step.action == "check":
                            check_action = (_ensure_checked if runtime_step.options.get("source_format") == "scenario_text"
                                            else _toggle_checked)
                            detail = {"resolution": resolution, **check_action(locator, timeout)}
                        elif step.action == "uncheck":
                            # 兼容历史步骤；新建和编辑页面不再提供“取消勾选”。
                            detail = {"resolution": resolution, **_ensure_unchecked(locator, timeout)}
                        elif step.action == "assert_visible":
                            locator.is_visible(timeout=timeout); detail = {"resolution": resolution, "passed": True}
                        elif step.action == "assert_text":
                            actual = locator.inner_text(timeout=timeout)
                            if value not in actual: raise AssertionError(f"期望包含 {value!r}，实际为 {actual!r}")
                            detail = {"expected": value, "actual": actual, "resolution": resolution}
                        elif step.action == "save_text":
                            variable_name = value.strip()
                            if not variable_name:
                                raise ValueError("提取文本步骤必须填写保存变量名。")
                            extracted, extraction_detail = _extract_text_with_ocr(
                                locator, runtime_step, case_id, step.id, timeout
                            )
                            variables[variable_name] = extracted
                            _save_runtime_variables(variables)
                            record_variable_resolution(
                                Path.cwd(), "ui_extract", {variable_name: extracted},
                                step_id=step.id, step_name=_step_name(step), action="save_text",
                                expression=(runtime_step.fallback_value or target or ""),
                                extraction_source=extraction_detail.get("extraction_source"),
                                ocr_status=extraction_detail.get("ocr_status"),
                                ocr_language=extraction_detail.get("ocr_language"),
                            )
                            detail = {
                                "variable": variable_name, "value": _safe(step, extracted),
                                "resolution": resolution, **extraction_detail,
                            }
                        else:
                            raise ValueError(f"不支持的 Playwright 操作：{step.action}")
                    if resolution and not resolution.get("strategy", "").startswith("manual:"):
                        remember_for_step(step.id, step.environment_name, resolution)
                    detail.setdefault("page_url", page.url)
                    if bool((runtime_step.options or {}).get("screenshot")):
                        # 操作完成后等待一帧左右，让动画/提示完成绘制再截图。
                        page.wait_for_timeout(100)
                        screenshot_path = _capture_step_screenshot(page, case_id, step.id, "passed")
                        if screenshot_path:
                            detail["screenshot"] = {
                                "path": screenshot_path,
                                "label": "步骤截图",
                            }
                    item.update({"status": "passed", "passed": True, "detail": detail})
                except Exception as exc:
                    failure_detail = {"page_url": page.url}
                    screenshot_path = _capture_step_screenshot(page, case_id, step.id, "failed")
                    if screenshot_path:
                        screenshot = {
                            "path": screenshot_path,
                            "label": "失败时页面截图",
                        }
                        # 失败步骤不受“执行后截图”开关影响，必须写入报告标准字段。
                        failure_detail["screenshot"] = screenshot
                        # 保留历史字段供旧版报告使用。
                        failure_detail["failure_screenshot"] = screenshot
                    item.update({
                        "status": "failed", "passed": False, "error": str(exc),
                        "detail": failure_detail,
                    })
                    report["passed"] = False
                finished_at = datetime.now().astimezone().isoformat()
                item["finished_at"] = finished_at
                item["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
                step_number = len(report["steps"])
                if item["status"] == "passed":
                    detail = item.get("detail") or {}
                    value_summary = (
                        f" · 输入内容：{detail.get('value')}"
                        if step.action == "input" else ""
                    )
                    resolution = detail.get("resolution") or {}
                    strategy = resolution.get("strategy") or ""
                    locator_summary = f" · 定位：{strategy}" if strategy else ""
                    write_execution_log(
                        f"智能 UI 步骤 {step_number}/{len(steps)} 通过：{_step_name(step)}"
                        f"{value_summary}{locator_summary} · {item['duration_ms']} ms",
                        "SUCCESS",
                    )
                else:
                    write_execution_log(
                        f"智能 UI 步骤 {step_number}/{len(steps)} 失败：{_step_name(step)} · "
                        f"{item['duration_ms']} ms · {item.get('error') or '未知错误'}",
                        "ERROR",
                    )
                _update_native_step(
                    case_id, step.id, status=item["status"], passed=item.get("passed"),
                    started_at=started_at, finished_at=finished_at, duration_ms=item["duration_ms"],
                    action_key=step.action, detail=item.get("detail", {}),
                    errors=[item["error"]] if item.get("error") else [], exception=item.get("error", ""),
                )
                _persist_native_result(report)
                if item["status"] == "failed" and not step.continue_on_failure:
                    break
        finally:
            browser.close()
    report["variables"] = {key: _safe(type("S", (), {"name": key, "target": key})(), value) for key, value in variables.items()}
    _persist_native_result(report)
    if not report["passed"] and raise_on_failure:
        failures = [item for item in report["steps"] if item.get("status") == "failed"]
        summary = "；".join(f"{item.get('name')}: {item.get('error')}" for item in failures)
        raise AssertionError(f"Playwright 用例执行失败：{summary}")
    if report["passed"]:
        write_execution_log(f"智能 UI 用例执行结束：{case_name} · 通过", "SUCCESS")
    return report


def execute_playwright_scenario_group(cases, *, raise_on_failure=True, persist_split=False):
    """按场景顺序执行一个 YAML 文件，共用同一个浏览器和页面。

    仍按原场景拆分报告；任一场景失败时，后续场景标记为未执行，
    避免在登录/前置操作失败后继续操作错误页面。
    """
    if not cases:
        raise ValueError("YAML 文件没有可执行场景。")
    if len(cases) == 1:
        report = execute_playwright_case(cases[0], raise_on_failure=raise_on_failure)
        return [report]

    combined = {key: value for key, value in cases[0].items() if key != "steps"}
    combined["name"] = " / ".join(str(case.get("name") or "未命名场景") for case in cases)
    # 套件仍写磁盘截图；临时批次 ID 不对应任何原生报告场景。
    combined["id"] = f"yaml-batch-{cases[0].get('id')}" if persist_split else None
    combined["steps"] = [step for case in cases for step in case.get("steps", [])]
    execution_report = execute_playwright_case(combined, raise_on_failure=False)
    executed_steps = execution_report.get("steps") or []
    reports = []
    offset = 0
    for case in cases:
        expected = len(case.get("steps", []))
        steps = executed_steps[offset:offset + expected]
        offset += expected
        passed = len(steps) == expected and all(step.get("passed") is True for step in steps)
        report = {
            "case_id": case.get("id"), "name": case.get("name"), "engine": "playwright",
            "passed": passed, "steps": steps, "variables": execution_report.get("variables", {}),
        }
        if not steps:
            report["error"] = "前一个场景失败，未继续执行。"
        elif not passed and not any(step.get("passed") is False for step in steps):
            report["error"] = "前一个场景失败，剩余步骤未执行。"
        if persist_split:
            _persist_native_result(report)
        reports.append(report)
    if raise_on_failure and not all(report["passed"] for report in reports):
        failed = next(report for report in reports if not report["passed"])
        failed_step = next((step for step in failed["steps"] if step.get("passed") is False), None)
        raise AssertionError(
            f"YAML 场景「{failed['name']}」执行失败："
            f"{failed_step.get('error') if failed_step else failed.get('error', '未完成')}"
        )
    return reports
