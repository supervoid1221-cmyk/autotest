"""Playwright 智能 UI 执行器。

该执行器只处理 PlaywrightCase/PlaywrightStep，既有 Selenium 执行器完全不变。
"""
import re
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

from project.models import Environment
from case_ui.models import playwright_step_display_name
from case_ui.smart_locator import SmartLocatorError, resolve as resolve_smart
from case_ui.smart_locator.engine import start_ui_transition_watch, wait_for_dialog_state, wait_for_ui_transition
from case_ui.smart_locator.fingerprints import load_for_step, remember_for_step
from case_ui.smart_locator.normalizer import normalize, semantic_terms
from suite.reporting import load_variable_resolution, record_variable_resolution, recalculate_native_report

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
    """统一勾选操作：未选中则选中，已选中则取消。"""
    checked_before = bool(locator.is_checked(timeout=timeout))
    if checked_before:
        locator.uncheck(timeout=timeout)
    else:
        locator.check(timeout=timeout)
    return {"checked_before": checked_before, "checked_after": not checked_before}


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
    try:
        normalized_status = "passed" if status == "passed" else "failed"
        relative_path = Path("screenshots") / (
            f"playwright_{normalized_status}_{case_id}_{step_id}_{int(time.time() * 1000)}.png"
        )
        target = Path.cwd() / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(target), full_page=False, animations="disabled", caret="hide", scale="css")
        return relative_path.as_posix()
    except Exception:
        # 截图失败不能覆盖步骤本身的执行结果。
        return ""


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


def _resolve(page, step, timeout):
    """自动定位优先；仅在自动定位失败且已配置兜底时使用手动表达式。"""
    if step.locator_mode == "manual":
        return _resolve_manual(page, step, timeout)
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


def execute_playwright_case(case, tab_key=None):
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
    steps, selected_tab_key = _steps_for_tab(steps, tab_key)
    for step in steps:
        # 套件执行环境优先于用例默认环境，用于选择环境级定位覆盖和历史指纹。
        step.environment_name = str(
            (data.get("environment_name") if isinstance(case, dict) else case.environment_name) or ""
        )
    report = {
        "case_id": case_id, "name": case_name, "engine": "playwright",
        "tab_key": selected_tab_key, "passed": True, "steps": [],
    }
    with sync_playwright() as playwright:
        browser_type = getattr(playwright, browser_name, None)
        if browser_type is None:
            raise ValueError(f"不支持的浏览器：{browser_name}")
        browser_started_at = datetime.now().astimezone().isoformat()
        try:
            browser = browser_type.launch(headless=run_mode != "headed")
        except Exception as exc:
            error = f"浏览器启动失败：{exc}"
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
            page = browser.new_page(viewport=viewport)
            for step in steps:
                started = time.perf_counter()
                item = {
                    "id": step.id, "name": _step_name(step), "action": step.action,
                    "target": step.target, "tab_key": getattr(step, "tab_key", ""), "status": "running",
                }
                report["steps"].append(item)
                _persist_native_result(report)
                _update_native_step(case_id, step.id, status="running", started_at=datetime.now().astimezone().isoformat())
                timeout = _step_timeout(step.options, default_timeout)
                try:
                    value = _replace(step.value, variables)
                    target = _replace(step.target, variables)
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
                    else:
                        locator, resolution = _resolve(page, runtime_step, timeout)
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
                        elif step.action == "click":
                            was_in_dialog = bool((resolution or {}).get("element", {}).get("inDialog"))
                            transition_token = start_ui_transition_watch(page)
                            locator.click(timeout=timeout)
                            transition = wait_for_ui_transition(page, transition_token, timeout=min(timeout, 1500))
                            detail = {"resolution": resolution, "ui_transition": transition}
                            # 删除通常是“列表删除 → 弹窗确认删除”两步。第一步等待弹窗
                            # 完成挂载，第二步等待弹窗关闭，确保两次点击都产生实际效果。
                            if normalize(target) in {"删除", "移除", "delete", "remove"}:
                                wait_for_dialog_state(page, visible=not was_in_dialog, timeout=min(timeout, 1500))
                        elif step.action == "clear":
                            locator.fill("", timeout=timeout); detail = {"resolution": resolution}
                        elif step.action == "select":
                            _select_value(page, locator, value, timeout); detail = {"value": value, "resolution": resolution}
                        elif step.action == "check":
                            detail = {"resolution": resolution, **_toggle_checked(locator, timeout)}
                        elif step.action == "uncheck":
                            # 兼容历史步骤；新建和编辑页面不再提供“取消勾选”。
                            locator.uncheck(timeout=timeout); detail = {"resolution": resolution, "checked_after": False}
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
                        # 保留历史字段供旧版报告使用；开启步骤截图时同时写入统一字段。
                        failure_detail["failure_screenshot"] = screenshot
                        if bool((getattr(step, "options", None) or {}).get("screenshot")):
                            failure_detail["screenshot"] = screenshot
                    item.update({
                        "status": "failed", "passed": False, "error": str(exc),
                        "detail": failure_detail,
                    })
                    report["passed"] = False
                item["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
                _update_native_step(
                    case_id, step.id, status=item["status"], passed=item.get("passed"),
                    finished_at=datetime.now().astimezone().isoformat(), duration_ms=item["duration_ms"],
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
    if not report["passed"]:
        failures = [item for item in report["steps"] if item.get("status") == "failed"]
        summary = "；".join(f"{item.get('name')}: {item.get('error')}" for item in failures)
        raise AssertionError(f"Playwright 用例执行失败：{summary}")
    return report
