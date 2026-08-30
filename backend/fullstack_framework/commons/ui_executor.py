"""平台 UI 用例的 Selenium 执行器。"""
import logging
import os
import time
import json
import platform
import re
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import yaml
from selenium import webdriver
from selenium.common import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.selenium_manager import SeleniumManager
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from fullstack_framework.commons.api_executor import substitute_data
from suite.reporting import load_variable_resolution, recalculate_native_report, record_variable_resolution
from case_ui.models import ui_step_display_name

logger = logging.getLogger(__name__)
SENSITIVE_HINTS = ("password", "passwd", "pwd", "secret", "token", "authorization", "密码", "密钥")
SELENIUM_MANAGER_TIMEOUT_SECONDS = 20


class UiAssertionError(AssertionError):
    def __init__(self, message, expected, actual):
        super().__init__(message)
        self.expected = expected
        self.actual = actual

def load_ui_cases(base_path=None):
    base_path = Path(base_path or Path.cwd())
    cases = []
    names = []
    for path in sorted(base_path.glob("ui_case_*.yaml")):
        with open(path, encoding="utf-8") as file:
            data = yaml.safe_load(file) or {}
        if not isinstance(data, dict) or not data.get("steps"):
            raise ValueError(f"UI 用例文件格式不正确：{path.name}")
        cases.append(data)
        names.append(str(data.get("name") or path.stem))
    return cases, names


def _variables_path():
    return Path.cwd() / "extract.yaml"


def _load_variables():
    path = _variables_path()
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _save_variables(variables):
    with open(_variables_path(), "w", encoding="utf-8") as file:
        yaml.safe_dump(variables, file, allow_unicode=True)


def _persist_native_step(case_id, step, changes):
    """原子写入 Selenium UI 步骤快照，供进度接口实时读取。"""
    if case_id is None:
        return
    path = Path.cwd() / f"ui_native_result_{case_id}.json"
    report = {"case_id": case_id, "engine": "selenium", "steps": []}
    try:
        if path.exists():
            report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        pass
    step_id = step.get("id")
    target = next((item for item in report.get("steps", []) if str(item.get("id")) == str(step_id)), None)
    if target is None:
        target = {
            "id": step_id,
            "name": _step_name(step),
            "action": step.get("action", ""),
            "tab_key": step.get("tab_key", ""),
        }
        report.setdefault("steps", []).append(target)
    target.update(changes)
    temporary = path.with_suffix(".json.tmp")
    try:
        temporary.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
    except OSError:
        logger.exception("写入 UI 实时步骤快照失败")


def _update_native_step(case_id, step, **changes):
    # 先落运行目录：即使 SQLite 此刻被其他进程占用，前端仍可实时看到状态。
    _persist_native_step(case_id, step, changes)
    result_id = os.environ.get("PLATFORM_RUN_RESULT_ID")
    if not result_id:
        return
    try:
        from django.db import transaction
        from suite.models import RunResult

        with transaction.atomic():
            result = RunResult.objects.select_for_update().get(id=int(result_id))
            report = result.native_report or {}
            group = next(
                (item for item in report.get("scenarios", []) if str(item.get("id")) == f"ui-{case_id}"),
                None,
            )
            if group is None:
                return
            target = next(
                (item for item in group.get("steps", []) if str(item.get("source_step_id")) == str(step.get("id"))),
                None,
            )
            if target is None:
                return
            target.update(changes)
            report["variable_resolution"] = load_variable_resolution(Path.cwd())
            recalculate_native_report(report)
            result.native_report = report
            result.save(update_fields=["native_report", "update_datetime"])
    except Exception:
        # 报告写入失败不应改变 UI 操作本身的测试结论。
        logger.exception("写入 UI 原生执行报告失败")


def _skip_steps(case_id, steps, reason):
    finished_at = datetime.now().astimezone().isoformat()
    for step in steps:
        _update_native_step(
            case_id, step, status="skipped", passed=None,
            finished_at=finished_at, duration_ms=0, skip_reason=reason,
        )


def _configured_chromedriver_path():
    """读取显式配置的 ChromeDriver 路径，优先级高于本地缓存。"""
    path = os.environ.get("CHROMEDRIVER_PATH", "").strip()
    if not path:
        try:
            from django.conf import settings

            path = str(getattr(settings, "CHROMEDRIVER_PATH", "") or "").strip()
        except Exception:
            path = ""
    if not path:
        return None
    candidate = Path(path).expanduser()
    if not candidate.is_file():
        raise RuntimeError(f"配置的 ChromeDriver 路径不存在或不是文件：{candidate}")
    if not os.access(candidate, os.X_OK):
        raise RuntimeError(f"配置的 ChromeDriver 没有执行权限：{candidate}")
    return candidate


def _chrome_version(binary_path=None):
    """获取本机 Chrome 主版本；读取失败时返回空字符串，后续由 Manager 处理。"""
    if binary_path:
        candidates = [str(binary_path)]
    elif platform.system() == "Darwin":
        candidates = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    elif platform.system() == "Windows":
        candidates = [
            os.path.expandvars(r"%PROGRAMFILES%\\Google\\Chrome\\Application\\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\\Google\\Chrome\\Application\\chrome.exe"),
        ]
    else:
        candidates = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"]

    for candidate in candidates:
        if not candidate or (os.path.sep in candidate and not Path(candidate).is_file()):
            continue
        try:
            result = subprocess.run(
                [candidate, "--version"], capture_output=True, text=True, timeout=5, check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        match = re.search(r"(\d+)\.(\d+)\.(\d+)\.(\d+)", result.stdout + result.stderr)
        if match:
            return match.group(1)
    return ""


def _driver_version_from_cache_path(path):
    """从 Selenium 缓存路径中读取 Driver 的版本目录。"""
    for parent in path.parents:
        if re.fullmatch(r"\d+(?:\.\d+){1,3}", parent.name):
            return tuple(int(part) for part in parent.name.split("."))
    return ()


def _cached_chromedriver(chrome_major, cache_root=None):
    """寻找与当前 Chrome 主版本一致的、本机 Selenium 缓存 Driver。"""
    if not chrome_major:
        return None
    root = Path(cache_root or os.environ.get("SE_CACHE_PATH") or Path.home() / ".cache" / "selenium")
    drivers_root = root / "chromedriver"
    if not drivers_root.is_dir():
        return None
    executable_names = {"chromedriver", "chromedriver.exe"}
    matches = []
    for candidate in drivers_root.rglob("*"):
        if candidate.name not in executable_names or not candidate.is_file() or not os.access(candidate, os.X_OK):
            continue
        version = _driver_version_from_cache_path(candidate)
        if version and str(version[0]) == str(chrome_major):
            matches.append((version, candidate))
    return max(matches, key=lambda item: item[0])[1] if matches else None


def _manager_chromedriver(options, timeout=SELENIUM_MANAGER_TIMEOUT_SECONDS):
    """受控调用 Selenium Manager，避免网络异常时长时间阻塞整个任务。"""
    args = [str(SeleniumManager.get_binary()), "--browser", "chrome", "--output", "json"]
    if getattr(options, "binary_location", None):
        args.extend(["--browser-path", str(options.binary_location)])
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"Selenium Manager 在 {timeout} 秒内未能完成 ChromeDriver 下载。"
            "请检查网络或代理，或配置 CHROMEDRIVER_PATH 指向可用的本地驱动。"
        ) from exc
    output_text = (completed.stdout or "").strip()
    error_text = (completed.stderr or "").strip()
    try:
        result = json.loads(output_text).get("result") or {}
        driver_path = Path(str(result.get("driver_path") or "")).expanduser()
    except (ValueError, TypeError):
        driver_path = Path("")
    if completed.returncode or not driver_path.is_file():
        detail = (error_text or output_text or "未返回可用 ChromeDriver")[-500:]
        raise RuntimeError(
            "Selenium Manager 下载或解析 ChromeDriver 失败，请检查网络、代理或 Chrome 版本。"
            f"详情：{detail}"
        )
    return driver_path


def _resolve_chromedriver(options):
    """按显式配置、本地缓存、Selenium Manager 的顺序解析 ChromeDriver。"""
    configured = _configured_chromedriver_path()
    if configured:
        return configured, "配置路径"

    chrome_major = _chrome_version(getattr(options, "binary_location", None))
    cached = _cached_chromedriver(chrome_major)
    if cached:
        return cached, f"本地 Selenium 缓存（Chrome {chrome_major}）"

    return _manager_chromedriver(options), "Selenium Manager"


def _create_driver(browser, run_mode="headless"):
    if browser != "chrome":
        raise ValueError(f"暂不支持浏览器：{browser}")
    if run_mode not in {"headless", "headed"}:
        raise ValueError(f"不支持的浏览器运行模式：{run_mode}")
    options = webdriver.ChromeOptions()
    if run_mode == "headless":
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=zh-CN")
    options.add_argument("--window-size=1920,1080")
    chrome_binary = os.environ.get("CHROME_BINARY", "").strip()
    if chrome_binary:
        options.binary_location = chrome_binary

    driver_path, source = _resolve_chromedriver(options)
    try:
        return webdriver.Chrome(service=Service(executable_path=str(driver_path)), options=options)
    except WebDriverException as exc:
        raise RuntimeError(
            f"ChromeDriver 启动失败（来源：{source}，路径：{driver_path}）。"
            "请确认驱动主版本与 Chrome 一致且具备执行权限。"
            f"详情：{exc}"
        ) from exc


def _find(driver, step, timeout):
    by_name = str(step.get("by") or "").upper()
    locator = step.get("locator")
    if not by_name or not locator or not hasattr(By, by_name):
        raise ValueError(f"步骤「{_step_name(step)}」的元素定位配置无效。")
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((getattr(By, by_name), locator))
    )


def _is_sensitive(step):
    text = str(step.get("element_name", "")).lower()
    return any(hint in text for hint in SENSITIVE_HINTS)


def _safe_value(step, value):
    return "***" if _is_sensitive(step) else str(value)


def _step_name(step):
    return ui_step_display_name(step.get("action"), step.get("element_name", ""), step.get("value", ""))


def _page_context(driver):
    try:
        return {"page_url": driver.current_url, "page_title": driver.title}
    except Exception:
        return {}


def _capture_step_screenshot(driver, case_id, step_id, status):
    """保存 Selenium 步骤当前视区，返回相对本次执行目录的报告路径。"""
    if driver is None:
        return ""
    try:
        relative_path = Path("screenshots") / (
            f"selenium_{status}_{case_id}_{step_id}_{int(time.time() * 1000)}.png"
        )
        target = Path.cwd() / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if not driver.save_screenshot(str(target)):
            return ""
        return relative_path.as_posix()
    except Exception:
        # 截图是报告增强能力，失败不能覆盖步骤本身的执行结论。
        logger.warning("保存 Selenium 步骤截图失败", exc_info=True)
        return ""


def _perform(driver, case, step, variables):
    action = step.get("action")
    options = step.get("options") or {}
    timeout = float(options.get("timeout", 10))
    project_id = case.get("project_id")
    environment_name = case.get("environment_name")
    raw_value = step.get("value", "")
    value = substitute_data(raw_value, variables, project_id, environment_name)

    if action == "goto":
        target = str(value)
        if not target.startswith(("http://", "https://")):
            target = urljoin(str(case.get("base_url") or "").rstrip("/") + "/", target.lstrip("/"))
        driver.get(target)
        return {"url": target}
    if action == "sleep":
        time.sleep(float(value))
        return {"seconds": float(value)}
    if action == "iframe_exit":
        driver.switch_to.default_content()
        return {}
    if action == "js_code":
        element = _find(driver, step, timeout) if step.get("locator") else None
        result = driver.execute_script(str(value), element) if element else driver.execute_script(str(value))
        return {"result": str(result)[:1000]}

    element = _find(driver, step, timeout)
    if action == "click":
        element.click()
        return {}
    if action == "input":
        if options.get("clear_before_input", True):
            element.clear()
        element.send_keys(str(value))
        return {"value": _safe_value(step, value)}
    if action == "upload_file":
        from case_ui.file_utils import resolve_uploaded_file
        file_ids = options.get("file_ids", [])
        if not isinstance(file_ids, list) or not file_ids:
            raise ValueError("上传文件步骤未选择文件。")
        paths = [str(resolve_uploaded_file(file_id, project_id)[0]) for file_id in file_ids]
        # Selenium 对 <input type=file> 的标准上传方式是写入执行机上的绝对路径。
        element.send_keys("\n".join(paths))
        return {"files": [Path(path).name for path in paths], "count": len(paths)}
    if action == "clear":
        element.clear()
        return {}
    if action == "save_text":
        variable_name = str(raw_value).strip()
        variables[variable_name] = element.text
        _save_variables(variables)
        record_variable_resolution(
            Path.cwd(), "ui_extract", {variable_name: element.text},
            step_id=step.get("id"), step_name=_step_name(step), action="save_text",
            expression=f"{step.get('by') or ''}={step.get('locator') or ''}".strip("="),
        )
        return {"variable": variable_name, "value": _safe_value(step, element.text)}
    if action == "assert_text":
        actual = element.text
        if actual != str(value):
            raise UiAssertionError(f"文本断言失败：期望 {value!r}，实际 {actual!r}", str(value), actual)
        return {"expected": str(value), "actual": actual, "passed": True}
    if action == "assert_value":
        actual = element.get_attribute("value")
        if actual != str(value):
            raise UiAssertionError(f"值断言失败：期望 {value!r}，实际 {actual!r}", str(value), actual)
        return {"expected": str(value), "actual": actual, "passed": True}
    if action == "iframe_enter":
        driver.switch_to.frame(element)
        return {}
    if action == "select":
        Select(element).select_by_visible_text(str(value))
        return {"value": str(value)}
    raise ValueError(f"不支持的 UI 操作：{action}")


def execute_ui_case(case):
    variables = _load_variables()
    driver = None
    failures = []
    steps = case.get("steps") or []
    try:
        try:
            driver = _create_driver(
                case.get("browser", "chrome"),
                case.get("run_mode", "headless"),
            )
        except Exception as exc:
            if steps:
                now = datetime.now().astimezone().isoformat()
                _update_native_step(
                    case.get("id"), steps[0], status="failed", passed=False,
                    started_at=now, finished_at=now, duration_ms=0,
                    errors=[f"浏览器启动失败：{exc}"], exception=str(exc),
                )
                _skip_steps(case.get("id"), steps[1:], "浏览器启动失败，后续步骤未执行。")
            raise

        for index, step in enumerate(steps):
            started = time.perf_counter()
            started_at = datetime.now().astimezone().isoformat()
            _update_native_step(case.get("id"), step, status="running", passed=None, started_at=started_at)
            try:
                detail = _perform(driver, case, step, variables)
                detail.update(_page_context(driver))
                if bool((step.get("options") or {}).get("screenshot")):
                    time.sleep(0.1)
                    screenshot_path = _capture_step_screenshot(
                        driver, case.get("id"), step.get("id"), "passed"
                    )
                    if screenshot_path:
                        detail["screenshot"] = {
                            "path": screenshot_path,
                            "label": "步骤截图",
                        }
                assertions = []
                if step.get("action") in {"assert_text", "assert_value"}:
                    assertions.append({
                        "type": step.get("action"),
                        "actual": detail.get("actual"),
                        "expected": detail.get("expected"),
                        "passed": True,
                    })
                _update_native_step(
                    case.get("id"), step, status="passed", passed=True,
                    finished_at=datetime.now().astimezone().isoformat(),
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                    element_name=step.get("element_name", ""), by=step.get("by"),
                    locator=step.get("locator"), action_key=step.get("action"),
                    detail=detail, assertions=assertions, errors=[], exception="",
                )
            except Exception as exc:
                message = f"步骤「{_step_name(step)}」失败：{exc}"
                failures.append(message)
                failure_detail = _page_context(driver)
                # 失败步骤始终截图，不受“执行后截图”开关影响。
                screenshot_path = _capture_step_screenshot(
                    driver, case.get("id"), step.get("id"), "failed"
                )
                if screenshot_path:
                    screenshot = {
                        "path": screenshot_path,
                        "label": "失败时页面截图",
                    }
                    failure_detail["screenshot"] = screenshot
                    failure_detail["failure_screenshot"] = screenshot
                assertions = []
                if isinstance(exc, UiAssertionError):
                    assertions.append({
                        "type": step.get("action"), "actual": exc.actual,
                        "expected": exc.expected, "passed": False,
                    })
                _update_native_step(
                    case.get("id"), step, status="failed", passed=False,
                    finished_at=datetime.now().astimezone().isoformat(),
                    duration_ms=round((time.perf_counter() - started) * 1000, 2),
                    element_name=step.get("element_name", ""), by=step.get("by"),
                    locator=step.get("locator"), action_key=step.get("action"),
                    detail=failure_detail, assertions=assertions,
                    errors=[message], exception=str(exc),
                )
                if not step.get("continue_on_failure"):
                    _skip_steps(
                        case.get("id"), steps[index + 1:],
                        f"前序步骤「{_step_name(step)}」失败，后续步骤未执行。",
                    )
                    raise
        if failures:
            raise AssertionError("；".join(failures))
    finally:
        if driver:
            driver.quit()
