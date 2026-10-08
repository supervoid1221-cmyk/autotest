import json
import logging
import os
import time
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from project.models import ProjectVariable
from account.tenant_runtime import ensure_tenant_storage_capacity, tenant_path
from suite.execution_log import write_execution_log

from .appium_client import AppiumClient
from .models import AppArtifact, AppDevice, AppRun, AppStepResult


logger = logging.getLogger(__name__)


def _append_log(run, message, level="INFO"):
    line = f"[{timezone.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}"
    run.log_content = f"{run.log_content}\n{line}".strip()[-200000:]
    run.save(update_fields=["log_content", "updated_at"])
    options = run.options if isinstance(run.options, dict) else {}
    if str(options.get("suite_result_id") or "").strip():
        from suite.models import RunResult
        suite_result_path = RunResult.objects.filter(
            pk=options["suite_result_id"], tenant_id=run.tenant_id,
        ).values_list("path", flat=True).first()
        write_execution_log(message, level, base_path=suite_result_path, tenant_id=run.tenant_id)
    else:
        write_execution_log(message, level, tenant_id=run.tenant_id)


def _artifact(run, step_result, artifact_type, name, content, binary=False):
    size = len(content) if isinstance(content, (bytes, bytearray)) else len(str(content).encode("utf-8"))
    ensure_tenant_storage_capacity(run.tenant, size)
    root = tenant_path(
        Path(settings.BASE_DIR) / "app_runs", run.tenant_id, run.execution_no
    )
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    if binary:
        path.write_bytes(content)
    else:
        path.write_text(str(content), encoding="utf-8")
    return AppArtifact.objects.create(
        run=run, step_result=step_result, artifact_type=artifact_type,
        name=name, file_path=str(path.relative_to(settings.BASE_DIR)),
    )


def _locator(step):
    if step.element_id:
        return step.element.locator_type, step.element.locator_value
    target = step.target or {}
    return str(target.get("type") or "id"), str(target.get("value") or "")


def _resolved_step_value(step, variables):
    value = str(step.value or "")
    for key, variable in variables.items():
        value = value.replace(f"${{{key}}}", str(variable))
    return value


def _step_value_is_sensitive(step):
    if bool((step.options or {}).get("sensitive")):
        return True
    element = step.element
    hints = " ".join([
        str(getattr(element, "name", "") or ""),
        str(getattr(element, "page_name", "") or ""),
        str(getattr(element, "locator_value", "") or ""),
        str(getattr(element, "element_class", "") or ""),
    ]).lower()
    return any(keyword in hints for keyword in ("password", "passwd", "pwd", "secret", "token", "密码", "密钥"))


def _step_execution_detail(step, variables):
    locator_type, locator_value = _locator(step)
    resolved_value = _resolved_step_value(step, variables)
    masked = step.action == "input" and _step_value_is_sensitive(step)
    element = step.element
    return {
        "value": "******" if masked and resolved_value else resolved_value,
        "value_masked": masked,
        "element_name": str(getattr(element, "name", "") or ""),
        "page_name": str(getattr(element, "page_name", "") or ""),
        "locator_type": locator_type,
        "locator_value": locator_value,
    }


def _step_start_log(index, total, result, step):
    input_summary = ""
    if step.action == "input":
        input_summary = f"，输入内容：{(result.detail or {}).get('value') or '（空）'}"
    return f"步骤 {index}/{total}：{result.name}{input_summary}"


def _execute_step(client, run, step, variables):
    action = step.action
    value = _resolved_step_value(step, variables)
    timeout = int((step.options or {}).get("timeout", run.case.default_timeout))
    package = run.application.package_name
    if action == "launch":
        client.command("POST", "/appium/device/activate_app", {"appId": package})
    elif action == "terminate":
        client.command("POST", "/appium/device/terminate_app", {"appId": package})
    elif action == "restart":
        client.command("POST", "/appium/device/terminate_app", {"appId": package})
        client.command("POST", "/appium/device/activate_app", {"appId": package})
    elif action in {"click", "input", "clear", "wait_element", "get_text", "assert_exists", "assert_text", "assert_attribute"}:
        using, locator_value = _locator(step)
        if using == "coordinate":
            coordinates = [part.strip() for part in locator_value.split(",")]
            if len(coordinates) != 2 or action not in {"click", "input"}:
                raise ValueError("坐标定位仅支持点击和输入，表达式格式应为 x,y。")
            client.tap(int(coordinates[0]), int(coordinates[1]))
            if action == "input":
                client.command("POST", "/keys", {"text": value, "value": list(value)})
            return
        if using in {"ocr_text", "image_text"}:
            match = client.locate_visual_text(using, locator_value)
            if action == "click":
                client.tap(match["x"], match["y"])
            elif action == "input":
                client.tap(match["x"], match["y"])
                client.command("POST", "/keys", {"text": value, "value": list(value)})
            elif action == "get_text":
                variables[value or f"step_{step.order}"] = match["text"]
            elif action == "assert_text" and value and value not in str(match["text"]):
                raise AssertionError(f"OCR 文本断言失败，期望「{value}」，识别结果「{match['text']}」。")
            elif action in {"clear", "assert_attribute"}:
                raise ValueError("OCR/图像文字定位不支持清空或属性断言。")
            return
        element_id = client.element(using, locator_value, timeout)
        element_path = f"/element/{element_id}"
        if action == "click":
            client.command("POST", f"{element_path}/click", {})
        elif action == "clear":
            client.command("POST", f"{element_path}/clear", {})
        elif action == "input":
            client.command("POST", f"{element_path}/clear", {})
            client.command("POST", f"{element_path}/value", {"text": value, "value": list(value)})
        elif action == "get_text":
            variables[value or f"step_{step.order}"] = client.command("GET", f"{element_path}/text")
        elif action == "assert_text":
            actual = str(client.command("GET", f"{element_path}/text") or "")
            if actual != value:
                raise AssertionError(f"文本断言失败，期望「{value}」，实际「{actual}」。")
        elif action == "assert_attribute":
            configured_attribute = str((step.options or {}).get("attribute") or "")
            attribute, expected = (value.split("=", 1) + [""])[:2] if not configured_attribute else (configured_attribute, value)
            if not attribute:
                raise ValueError("属性断言请按 属性名=期望值 填写操作值。")
            actual = str(client.command("GET", f"{element_path}/attribute/{attribute}") or "")
            if actual != expected:
                raise AssertionError(f"属性 {attribute} 断言失败，期望「{expected}」，实际「{actual}」。")
    elif action == "back":
        client.command("POST", "/back", {})
    elif action == "home":
        client.command("POST", "/appium/device/press_keycode", {"keycode": 3})
    elif action == "wait":
        time.sleep(max(0, min(float(value or 1), 300)))
    elif action == "swipe":
        target = step.target or {}
        duration = int(target.get("duration", 600))
        actions = [{"type": "pointer", "id": "finger1", "parameters": {"pointerType": "touch"}, "actions": [
            {"type": "pointerMove", "duration": 0, "x": int(target.get("start_x", 0)), "y": int(target.get("start_y", 0))},
            {"type": "pointerDown", "button": 0},
            {"type": "pause", "duration": 100},
            {"type": "pointerMove", "duration": duration, "x": int(target.get("end_x", 0)), "y": int(target.get("end_y", 0))},
            {"type": "pointerUp", "button": 0},
        ]}]
        client.command("POST", "/actions", {"actions": actions})
    elif action == "screenshot":
        return "screenshot"
    elif action == "set_variable":
        configured_name = str((step.options or {}).get("name") or "")
        if configured_name:
            variables[configured_name] = value
        elif "=" in value:
            name, variable_value = value.split("=", 1)
            variables[name.strip()] = variable_value
        else:
            raise ValueError("设置变量请按 变量名=变量值 填写操作值。")
    else:
        raise ValueError(f"暂不支持操作：{action}")


def execute_app_run(run_id, tenant_id=None):
    run = AppRun.objects.select_related("case", "application", "version", "device__node").get(pk=run_id)
    if tenant_id is not None and str(run.tenant_id) != str(tenant_id):
        raise ValueError("执行任务租户与 App 执行记录不一致。")
    if run.stop_requested or run.status == AppRun.Status.STOPPED:
        return
    client = None
    acquired = False
    session_started = False
    try:
        with transaction.atomic():
            device = AppDevice.objects.select_for_update().get(pk=run.device_id)
            if not device.enabled or device.state == AppDevice.State.OFFLINE:
                raise RuntimeError("设备未启用或当前离线。")
            if device.state in {AppDevice.State.BUSY, AppDevice.State.INSPECTING}:
                raise RuntimeError("设备正在被其他任务或元素检查占用。")
            device.state = AppDevice.State.BUSY
            device.save(update_fields=["state", "updated_at"])
            acquired = True
        run.status = AppRun.Status.PREPARING
        run.started_at = timezone.now()
        run.save(update_fields=["status", "started_at", "updated_at"])
        _append_log(run, f"App 用例「{run.case.name}」开始执行")
        _append_log(run, f"已锁定设备 {run.device.name}（{run.device.udid}）")
        capabilities = {
            "platformName": "Android", "appium:automationName": "UiAutomator2",
            "appium:udid": run.device.udid, "appium:deviceName": run.device.name,
            "appium:noReset": not bool(run.options.get("clear_data", run.application.clear_data)),
            "appium:appPackage": run.application.package_name,
            "appium:appActivity": run.application.main_activity or None,
            "appium:newCommandTimeout": 300,
        }
        capabilities.update(run.application.startup_options or {})
        if run.version and run.options.get("auto_install", run.application.auto_install) and run.version.file_path:
            run.status = AppRun.Status.INSTALLING
            run.save(update_fields=["status", "updated_at"])
            capabilities["appium:app"] = str((Path(settings.BASE_DIR) / run.version.file_path).resolve())
            capabilities["appium:enforceAppInstall"] = bool(run.application.replace_install)
            _append_log(run, f"正在安装应用版本：{run.version.name}")
        capabilities = {key: value for key, value in capabilities.items() if value not in (None, "")}
        client = AppiumClient(run.device.node.server_url, timeout=60)
        client.start_session(capabilities)
        session_started = True
        _append_log(run, f"Appium 会话已建立，应用：{run.application.name}")
        run.status = AppRun.Status.RUNNING
        run.save(update_fields=["status", "updated_at"])
        steps = list(run.case.steps.select_related("element").order_by("order", "id"))
        variables = ProjectVariable.values_for_projects([run.project_id])
        passed_count = failed_count = executed_count = 0
        for index, step in enumerate(steps, start=1):
            run.refresh_from_db(fields=["stop_requested"])
            if run.stop_requested:
                run.status = AppRun.Status.STOPPED
                break
            started = timezone.now()
            result = AppStepResult.objects.create(
                run=run, step=step, order=index, action=step.action,
                name=f"{step.get_action_display()} · {step.element.name if step.element_id else step.value or ''}"[:160],
                status="running", started_at=started,
                detail=_step_execution_detail(step, variables),
            )
            executed_count = index
            _append_log(run, _step_start_log(index, len(steps), result, step))
            try:
                retry_count = int((step.options or {}).get("retry_count", run.case.retry_count) or 0)
                output = None
                for attempt in range(retry_count + 1):
                    try:
                        output = _execute_step(client, run, step, variables)
                        break
                    except Exception:
                        if attempt >= retry_count:
                            raise
                        _append_log(run, f"步骤 {index} 执行失败，正在进行第 {attempt + 1} 次重试")
                if output == "screenshot" or bool((step.options or {}).get("screenshot")):
                    _artifact(run, result, "screenshot", f"step-{index}-screenshot.png", client.screenshot(), binary=True)
                result.status = "passed"
                result.message = "执行成功"
                passed_count += 1
            except Exception as exc:
                result.status = "failed"
                result.message = str(exc)
                failed_count += 1
                try:
                    _artifact(run, result, "screenshot", f"step-{index}-failed.png", client.screenshot(), binary=True)
                    _artifact(run, result, "page_source", f"step-{index}-source.xml", client.page_source())
                except Exception as artifact_error:
                    _append_log(run, f"失败附件采集失败：{artifact_error}")
            result.finished_at = timezone.now()
            result.duration_ms = max(0, int((result.finished_at - started).total_seconds() * 1000))
            result.save(update_fields=["status", "message", "finished_at", "duration_ms"])
            if result.status == "passed":
                _append_log(run, f"步骤 {index}/{len(steps)} 通过，耗时 {result.duration_ms} ms")
            else:
                _append_log(run, f"步骤 {index}/{len(steps)} 失败，耗时 {result.duration_ms} ms：{result.message}", "ERROR")
            run.progress = int(index / max(len(steps), 1) * 100)
            run.save(update_fields=["progress", "updated_at"])
            if result.status == "failed" and run.case.stop_on_failure and not step.continue_on_failure:
                break
        skipped = max(0, len(steps) - executed_count)
        if skipped:
            for step in steps[executed_count:]:
                AppStepResult.objects.create(
                    run=run, step=step, order=step.order, action=step.action,
                    name=f"{step.get_action_display()} · {step.element.name if step.element_id else step.value or ''}"[:160],
                    status="skipped", message="任务已停止" if run.status == AppRun.Status.STOPPED else "前序步骤失败，未执行",
                )
        run.summary = {"total": len(steps), "passed": passed_count, "failed": failed_count, "skipped": skipped}
        if run.status != AppRun.Status.STOPPED:
            run.status = AppRun.Status.REPORTING
            run.save(update_fields=["status", "updated_at"])
            run.status = AppRun.Status.PASSED if failed_count == 0 else AppRun.Status.FAILED
            run.progress = 100
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "progress", "summary", "finished_at", "updated_at"])
        _append_log(
            run,
            f"App 用例执行结束：{run.get_status_display()}，"
            f"成功 {passed_count}，失败 {failed_count}，跳过 {skipped}",
        )
    except Exception as exc:
        run.status = AppRun.Status.ERROR
        run.error_message = str(exc)
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "error_message", "finished_at", "updated_at"])
        _append_log(run, f"执行异常：{exc}", "ERROR")
    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass
        if acquired:
            AppDevice.objects.filter(pk=run.device_id).update(
                state=AppDevice.State.ONLINE if session_started else AppDevice.State.OFFLINE,
                updated_at=timezone.now(),
            )
        try:
            from execution_control.dispatcher import dispatch_waiting_tasks
            dispatch_waiting_tasks()
        except Exception:
            logger.exception("继续派发等待任务失败，app_run_id=%s", run_id)


def execute_suite_app_case(case_data):
    """在套件 pytest 进程内同步执行 App 用例，并将步骤结果回写到套件报告。"""
    from .models import AppCase

    case_id = int((case_data or {}).get("id") or 0)
    case = AppCase.objects.select_related("project", "application", "default_device").get(pk=case_id)
    device_id = int((case_data or {}).get("device_id") or case.default_device_id or 0)
    device = AppDevice.objects.filter(pk=device_id, project=case.project, enabled=True).first()
    if not device:
        raise RuntimeError(f"App 用例「{case.name}」的默认设备不可用。")
    version = case.application.versions.filter(enabled=True).order_by("-created_at", "-id").first()
    run = AppRun.objects.create(
        tenant=case.tenant, case=case, project=case.project, application=case.application,
        version=version, device=device,
        options={
            "auto_install": bool(case.application.auto_install),
            "clear_data": bool(case.application.clear_data),
            "suite_result_id": str(os.environ.get("PLATFORM_RUN_RESULT_ID") or ""),
        },
    )
    execute_app_run(run.id)
    run.refresh_from_db()
    _merge_suite_run_result(run)
    if run.status != AppRun.Status.PASSED:
        message = run.error_message or f"App 用例执行结果：{run.get_status_display()}"
        raise AssertionError(message)
    return run


def _merge_suite_run_result(app_run):
    result_id = str(os.environ.get("PLATFORM_RUN_RESULT_ID") or "").strip()
    if not result_id:
        return
    from suite.models import RunResult
    from suite.reporting import recalculate_native_report

    result = RunResult.objects.filter(pk=int(result_id)).first()
    if not result:
        return
    report = result.native_report or {}
    scenario = next(
        (item for item in report.get("scenarios", []) if str(item.get("id")) == f"app-{app_run.case_id}"),
        None,
    )
    if not scenario:
        return
    runtime_results = {
        item.step_id: item
        for item in app_run.step_results.prefetch_related("artifacts").order_by("order", "id")
        if item.step_id
    }
    for step in scenario.get("steps", []):
        runtime = runtime_results.get(step.get("source_step_id"))
        if not runtime:
            continue
        runtime_detail = runtime.detail or _step_execution_detail(runtime.step, {})
        step.update({
            "status": runtime.status,
            "passed": True if runtime.status == "passed" else False if runtime.status == "failed" else None,
            "duration_ms": runtime.duration_ms,
            "started_at": runtime.started_at.isoformat() if runtime.started_at else None,
            "finished_at": runtime.finished_at.isoformat() if runtime.finished_at else None,
            "message": runtime.message,
            "element_name": runtime_detail.get("element_name") or "",
            "target": runtime_detail.get("element_name") or "",
            "by": runtime_detail.get("locator_type") or "",
            "locator": runtime_detail.get("locator_value") or "",
            "detail": {
                "value": runtime_detail.get("value") or "",
                "value_masked": bool(runtime_detail.get("value_masked")),
                "page_name": runtime_detail.get("page_name") or "",
                "resolution": {
                    "strategy": runtime_detail.get("locator_type") or "",
                    "element": {
                        "name": runtime_detail.get("element_name") or "",
                        "page": runtime_detail.get("page_name") or "",
                        "locator": runtime_detail.get("locator_value") or "",
                    },
                    "fallback_used": False,
                    "candidates": [],
                },
            },
            "errors": [runtime.message] if runtime.status == "failed" and runtime.message else [],
            "artifacts": [
                {
                    "id": artifact.id, "type": artifact.artifact_type, "name": artifact.name,
                    "download_url": f"/api/case_app/run/{app_run.id}/artifact/{artifact.id}/",
                }
                for artifact in runtime.artifacts.all()
            ],
        })
    scenario.update({
        "app_run_id": app_run.id, "execution_no": app_run.execution_no,
        "device": app_run.device.name, "summary": app_run.summary,
        "error_message": app_run.error_message,
    })
    recalculate_native_report(report)
    result.native_report = report
    result.save(update_fields=["native_report", "update_datetime"])
