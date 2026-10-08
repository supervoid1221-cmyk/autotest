from django.utils import timezone

from account.access import display_name

from .models import ExecutionTask


TERMINAL_STATUSES = {
    ExecutionTask.Status.SUCCEEDED,
    ExecutionTask.Status.FAILED,
    ExecutionTask.Status.ERROR,
    ExecutionTask.Status.CANCELED,
    ExecutionTask.Status.STOPPED,
}


def _bounded_progress(value, status):
    if status in TERMINAL_STATUSES:
        return 100
    try:
        return max(0, min(99, int(value or 0)))
    except (TypeError, ValueError):
        return 0


def _created_by_name(run):
    """从源任务的 created_by 外键取执行人显示名称。

    取不到时返回空串而不是「系统」：App / 性能任务允许没有创建人（迁移前的历史
    数据、由调度器直接发起的任务），空串让前端显示为「-」，比谎称「系统执行」
    更准确。
    """
    return display_name(getattr(run, "created_by", None), default="")


def sync_suite_run(run):
    from suite.models import RunResult

    mapping = {
        RunResult.RunStatus.Init: ExecutionTask.Status.QUEUED,
        RunResult.RunStatus.Ready: ExecutionTask.Status.QUEUED,
        RunResult.RunStatus.Running: ExecutionTask.Status.RUNNING,
        RunResult.RunStatus.Reporting: ExecutionTask.Status.REPORTING,
        RunResult.RunStatus.Done: ExecutionTask.Status.SUCCEEDED if run.is_pass else ExecutionTask.Status.FAILED,
        RunResult.RunStatus.Error: ExecutionTask.Status.ERROR,
        RunResult.RunStatus.Canceled: ExecutionTask.Status.CANCELED,
        RunResult.RunStatus.Paused: ExecutionTask.Status.PAUSED,
    }
    status = mapping.get(run.status, ExecutionTask.Status.ERROR)
    report_summary = (run.native_report or {}).get("summary") or {}
    total = sum(int(report_summary.get(key, 0) or 0) for key in ("passed", "failed", "running", "pending", "skipped"))
    completed = sum(int(report_summary.get(key, 0) or 0) for key in ("passed", "failed", "skipped"))
    progress = round(completed / total * 100) if total else (100 if status in TERMINAL_STATUSES else 0)
    error_message = ""
    if status == ExecutionTask.Status.ERROR:
        error_message = "套件执行进程异常结束，请查看实时日志。"
    return _upsert(
        source_type=ExecutionTask.SourceType.SUITE, source=run, execution_no=run.id,
        project=run.project, name=run.suite.name, engine="UI&API",
        status=status, raw_status=str(run.status), progress=progress,
        timeout_seconds=run.timeout_seconds, error_message=error_message,
        created_at=run.create_datetime, updated_at=run.update_datetime,
        resource_keys=_suite_resource_keys(run),
        # RunResult.executor_name 在「重新执行」时会被改写（复用同一条执行记录），
        # 所以这里总是带值传下去，让 _upsert 覆盖旧值，否则重跑后执行人停在上一轮。
        executor_name=run.executor_name,
    )


def sync_app_run(run):
    # 套件内的 App 用例只是主任务的一个执行项，结果会合并到套件报告。
    # 若再将该 AppRun 登记为独立任务，统一执行中心就会出现两份报告。
    if is_suite_child_app_run(run):
        ExecutionTask.objects.filter(
            tenant_id=run.tenant_id,
            source_type=ExecutionTask.SourceType.APP,
            source_id=run.pk,
        ).delete()
        return None
    mapping = {
        "queued": ExecutionTask.Status.QUEUED,
        "preparing": ExecutionTask.Status.PREPARING,
        "installing": ExecutionTask.Status.PREPARING,
        "running": ExecutionTask.Status.RUNNING,
        "reporting": ExecutionTask.Status.REPORTING,
        "passed": ExecutionTask.Status.SUCCEEDED,
        "failed": ExecutionTask.Status.FAILED,
        "error": ExecutionTask.Status.ERROR,
        "stopped": ExecutionTask.Status.STOPPED,
    }
    return _upsert(
        source_type=ExecutionTask.SourceType.APP, source=run, execution_no=run.execution_no,
        project=run.project, name=run.case.name, engine="Appium",
        status=mapping.get(run.status, ExecutionTask.Status.ERROR), raw_status=run.status,
        stage="安装应用" if run.status == "installing" else "", progress=run.progress,
        timeout_seconds=1800, error_message=run.error_message,
        created_at=run.created_at, updated_at=run.updated_at,
        resource_keys=[f"app-device:{run.device_id}"],
        executor_name=_created_by_name(run),
    )


def is_suite_child_app_run(run):
    options = run.options if isinstance(run.options, dict) else {}
    return bool(str(options.get("suite_result_id") or "").strip())


def sync_performance_run(run):
    mapping = {
        "queued": ExecutionTask.Status.QUEUED,
        "preparing": ExecutionTask.Status.PREPARING,
        "running": ExecutionTask.Status.RUNNING,
        "reporting": ExecutionTask.Status.REPORTING,
        "passed": ExecutionTask.Status.SUCCEEDED,
        "failed": ExecutionTask.Status.FAILED,
        "error": ExecutionTask.Status.ERROR,
        "stopped": ExecutionTask.Status.STOPPED,
    }
    return _upsert(
        source_type=ExecutionTask.SourceType.PERFORMANCE, source=run, execution_no=run.execution_no,
        project=run.project, name=run.scenario.name, engine="k6",
        status=mapping.get(run.status, ExecutionTask.Status.ERROR), raw_status=run.status,
        progress=run.progress, timeout_seconds=_performance_timeout(run), error_message=run.error_message,
        created_at=run.created_at, updated_at=run.updated_at,
        resource_keys=[],
        executor_name=_created_by_name(run),
    )


def _suite_resource_keys(run):
    """套件包含 App 用例时，执行期间预留其默认设备。"""
    try:
        device_ids = run.suite.execution_items.filter(
            item_type="app", app_case__default_device_id__isnull=False,
        ).values_list("app_case__default_device_id", flat=True)
        return sorted({f"app-device:{device_id}" for device_id in device_ids})
    except Exception:
        return []


def _performance_timeout(run):
    execution = run.execution_config or {}
    if execution.get("load_mode") == "thread_group":
        return max(60, int(execution.get("ramp_up_seconds") or 0) + int(execution.get("duration_seconds") or 0) + 120)
    total = 0
    for stage in execution.get("stages") or []:
        value = str(stage.get("duration") or "0s").strip().lower()
        try:
            if value.endswith("ms"):
                total += float(value[:-2]) / 1000
            elif value.endswith("s"):
                total += float(value[:-1])
            elif value.endswith("m"):
                total += float(value[:-1]) * 60
            elif value.endswith("h"):
                total += float(value[:-1]) * 3600
        except ValueError:
            continue
    return max(60, int(total) + 120)


def _upsert(*, source_type, source, execution_no, project, name, engine, status, raw_status,
            progress, timeout_seconds, error_message, created_at, updated_at,
            resource_keys=None, stage="", executor_name=""):
    now = timezone.now()
    tenant = getattr(source, "tenant", None) or getattr(project, "tenant", None)
    previous_status = ExecutionTask.objects.filter(
        tenant=tenant, source_type=source_type, source_id=source.pk,
    ).values_list("status", flat=True).first()
    defaults = {
        "execution_no": str(execution_no), "project": project, "name": str(name)[:160], "engine": engine,
        "status": status, "raw_status": str(raw_status), "stage": stage or dict(ExecutionTask.Status.choices).get(status, ""),
        "progress": _bounded_progress(progress, status), "timeout_seconds": max(1, int(timeout_seconds or 1800)),
        "diagnostic_code": "SOURCE_ERROR" if error_message else "",
        "diagnostic_message": str(error_message or ""), "last_activity_at": updated_at or now,
        "resource_keys": list(resource_keys or []),
        "queued_at": created_at or now, "started_at": getattr(source, "started_at", None),
        "finished_at": getattr(source, "finished_at", None), "source_created_at": created_at or now,
        "source_updated_at": updated_at or now,
    }
    # 执行人只在拿到名字时才写。空值来自「源记录没有创建人」（历史数据、
    # 由调度器直接发起的 App / 性能任务），此时保留库里的旧快照而不是抹成空：
    # created_by 是 SET_NULL，用户注销后外键会变 None，若照写空值就会把
    # 「张三执行过」变成「-」，快照的意义就没了。
    # 套件走的是 RunResult.executor_name，恒有值（默认「系统」），不受影响。
    executor_name = str(executor_name or "").strip()
    if executor_name:
        defaults["executor_name"] = executor_name[:150]
    task, created = ExecutionTask.objects.update_or_create(
        tenant=tenant,
        source_type=source_type,
        source_id=source.pk,
        defaults=defaults,
    )
    # 重新执行会复用原执行编号。当源记录从终态重置为 Ready 时，
    # 必须同时清理上一轮的派发痕迹，否则调度器会误认该任务已进队。
    if (
        not created
        and status == ExecutionTask.Status.QUEUED
        and previous_status in TERMINAL_STATUSES
    ):
        task.dispatched_at = None
        task.dispatch_attempts = 0
        task.waiting_reason = ""
        task.recovery_count = 0
        task.last_recovered_at = None
        task.save(update_fields=[
            "dispatched_at", "dispatch_attempts", "waiting_reason",
            "recovery_count", "last_recovered_at", "updated_at",
        ])
    if status != ExecutionTask.Status.QUEUED and task.waiting_reason:
        task.waiting_reason = ""
        task.save(update_fields=["waiting_reason", "updated_at"])
    return task


def sync_all_existing():
    from case_app.models import AppRun
    from performance.models import PerformanceRun
    from suite.models import RunResult

    counts = {"suite": 0, "app": 0, "performance": 0}
    for run in RunResult.objects.select_related("suite", "project").iterator():
        sync_suite_run(run); counts["suite"] += 1
    # 带上 created_by：执行人快照取自该外键，不预取会退化成逐行查库。
    for run in AppRun.objects.select_related("case", "project", "created_by").iterator():
        if sync_app_run(run) is not None:
            counts["app"] += 1
    for run in PerformanceRun.objects.select_related("scenario", "project", "created_by").iterator():
        sync_performance_run(run); counts["performance"] += 1
    return counts
