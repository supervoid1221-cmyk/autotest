import os
import socket
import threading
import time
import shutil
from pathlib import Path
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone
from account.tenant_runtime import is_managed_storage_path, legacy_tenant_path, tenant_path
from django.db.utils import OperationalError

from .models import ExecutionTask, ExecutionWorker


def worker_is_fresh(kind):
    cutoff = timezone.now() - timedelta(seconds=settings.EXECUTION_WORKER_OFFLINE_SECONDS)
    return ExecutionWorker.objects.filter(
        kind=kind, status=ExecutionWorker.Status.ONLINE, last_heartbeat_at__gte=cutoff
    ).exists()


def refresh_worker_states():
    cutoff = timezone.now() - timedelta(seconds=settings.EXECUTION_WORKER_OFFLINE_SECONDS)
    return ExecutionWorker.objects.filter(
        status__in=[ExecutionWorker.Status.ONLINE, ExecutionWorker.Status.DEGRADED],
        last_heartbeat_at__lt=cutoff,
    ).update(status=ExecutionWorker.Status.OFFLINE, message="心跳超时，执行器可能未启动或已退出。")


def required_worker_kind(task):
    if task.source_type == ExecutionTask.SourceType.PERFORMANCE:
        return ExecutionWorker.Kind.PERFORMANCE
    return ExecutionWorker.Kind.SCHEDULER


def diagnose_tasks(queryset=None):
    refresh_worker_states()
    if queryset is None:
        queryset = ExecutionTask.objects.all()
    now = timezone.now()
    queue_cutoff = now - timedelta(seconds=settings.EXECUTION_QUEUE_DIAGNOSIS_SECONDS)
    results = {"worker_offline": 0, "stale": 0, "healthy": 0}
    fresh = {
        kind: worker_is_fresh(kind)
        for kind in (ExecutionWorker.Kind.SCHEDULER, ExecutionWorker.Kind.PERFORMANCE)
    }
    for task in queryset.filter(status__in=[
        ExecutionTask.Status.QUEUED, ExecutionTask.Status.PREPARING,
        ExecutionTask.Status.RUNNING, ExecutionTask.Status.REPORTING,
    ]).iterator():
        code = message = ""
        kind = required_worker_kind(task)
        if task.status == ExecutionTask.Status.QUEUED and task.queued_at <= queue_cutoff and not fresh[kind]:
            code = "WORKER_OFFLINE"
            worker_name = dict(ExecutionWorker.Kind.choices)[kind]
            message = f"{worker_name}未上报有效心跳，任务无法被调度。"
            results["worker_offline"] += 1
        elif task.status != ExecutionTask.Status.QUEUED:
            stale_after = max(60, int(task.timeout_seconds or 1800))
            if task.last_activity_at < now - timedelta(seconds=stale_after):
                code = "TASK_STALE"
                message = f"任务超过 {stale_after} 秒没有更新，请检查执行进程或手动终止。"
                results["stale"] += 1
        if not code:
            results["healthy"] += 1
        if task.diagnostic_code != code or task.diagnostic_message != message:
            ExecutionTask.objects.filter(pk=task.pk).update(
                diagnostic_code=code, diagnostic_message=message
            )
    return results


def recover_task(task):
    """只恢复可安全重新入队的任务，不重试已执行的测试步骤。"""
    now = timezone.now()
    if task.last_recovered_at and task.last_recovered_at > now - timedelta(seconds=60):
        raise ValueError("任务刚完成恢复操作，请稍后再试。")
    kind = required_worker_kind(task)
    if not worker_is_fresh(kind):
        raise ValueError(f"{dict(ExecutionWorker.Kind.choices)[kind]}当前离线，请先启动执行器。")

    with transaction.atomic():
        task = ExecutionTask.objects.select_for_update().get(pk=task.pk)
        if task.source_type == ExecutionTask.SourceType.SUITE:
            from suite.models import RunResult
            run = RunResult.objects.select_related("suite").get(
                pk=task.source_id, tenant_id=task.tenant_id,
            )
            if run.status != RunResult.RunStatus.Ready:
                raise ValueError("仅“准备开始”的套件任务可重新入队。")
            ExecutionTask.objects.filter(pk=task.pk).update(
                dispatched_at=None, waiting_reason="等待重新调度"
            )
        elif task.source_type == ExecutionTask.SourceType.APP:
            from case_app.models import AppRun
            run = AppRun.objects.get(pk=task.source_id, tenant_id=task.tenant_id)
            if run.status != AppRun.Status.QUEUED:
                raise ValueError("仅等待设备的 App 任务可重新入队。")
            ExecutionTask.objects.filter(pk=task.pk).update(
                dispatched_at=None, waiting_reason="等待重新调度"
            )
        else:
            from performance.models import PerformanceRun
            run = PerformanceRun.objects.get(pk=task.source_id, tenant_id=task.tenant_id)
            if run.status == PerformanceRun.Status.PREPARING and run.process_id is None:
                run.status = PerformanceRun.Status.QUEUED
                run.started_at = None
                run.save(update_fields=["status", "started_at", "updated_at"])
            elif run.status != PerformanceRun.Status.QUEUED:
                raise ValueError("仅等待或未启动进程的性能任务可恢复。")
        ExecutionTask.objects.filter(pk=task.pk).update(
            recovery_count=task.recovery_count + 1, last_recovered_at=now,
            diagnostic_code="", diagnostic_message="", last_activity_at=now,
        )
    if task.source_type in {ExecutionTask.SourceType.SUITE, ExecutionTask.SourceType.APP}:
        from .dispatcher import dispatch_waiting_tasks
        dispatch_waiting_tasks()
    return task


def stop_task(task):
    now = timezone.now()
    if task.source_type == ExecutionTask.SourceType.SUITE:
        from suite.models import RunResult
        run = RunResult.objects.get(pk=task.source_id, tenant_id=task.tenant_id)
        if run.status in {RunResult.RunStatus.Done, RunResult.RunStatus.Error, RunResult.RunStatus.Canceled}:
            raise ValueError("任务已结束。")
        run.cancel_requested = True
        fields = ["cancel_requested", "update_datetime"]
        if run.status == RunResult.RunStatus.Ready:
            run.status, run.finished_at = RunResult.RunStatus.Canceled, now
            fields.extend(["status", "finished_at"])
        run.save(update_fields=fields)
    elif task.source_type == ExecutionTask.SourceType.APP:
        from case_app.models import AppRun
        run = AppRun.objects.get(pk=task.source_id, tenant_id=task.tenant_id)
        if run.status in {AppRun.Status.PASSED, AppRun.Status.FAILED, AppRun.Status.ERROR, AppRun.Status.STOPPED}:
            raise ValueError("任务已结束。")
        run.stop_requested = True
        fields = ["stop_requested", "updated_at"]
        if run.status == AppRun.Status.QUEUED:
            run.status, run.finished_at = AppRun.Status.STOPPED, now
            fields.extend(["status", "finished_at"])
        run.save(update_fields=fields)
    else:
        from performance.models import PerformanceRun
        run = PerformanceRun.objects.get(pk=task.source_id, tenant_id=task.tenant_id)
        if run.status in {PerformanceRun.Status.PASSED, PerformanceRun.Status.FAILED, PerformanceRun.Status.ERROR, PerformanceRun.Status.STOPPED}:
            raise ValueError("任务已结束。")
        run.stop_requested = True
        fields = ["stop_requested", "updated_at"]
        if run.status == PerformanceRun.Status.QUEUED:
            run.status, run.finished_at = PerformanceRun.Status.STOPPED, now
            fields.extend(["status", "finished_at"])
        run.save(update_fields=fields)
        if run.process_id:
            try:
                os.kill(run.process_id, 15)
            except OSError:
                pass


def delete_task(task):
    """从统一入口删除终态任务、原始报告与运行产物。"""
    if task.status not in {
        ExecutionTask.Status.SUCCEEDED, ExecutionTask.Status.FAILED, ExecutionTask.Status.ERROR,
        ExecutionTask.Status.CANCELED, ExecutionTask.Status.STOPPED,
    }:
        raise ValueError("执行中的任务不能删除，请先停止任务。")

    if task.source_type == ExecutionTask.SourceType.SUITE:
        from suite.models import RunResult
        run = RunResult.objects.filter(pk=task.source_id, tenant_id=task.tenant_id).first()
        if not run:
            task.delete(); return
        path = Path(str(run.path)).resolve() if run.path else None
        run.delete()
        if path and is_managed_storage_path(path, "upload_yaml", tenant=task.tenant_id):
            shutil.rmtree(path, ignore_errors=True)
    elif task.source_type == ExecutionTask.SourceType.APP:
        from case_app.models import AppRun
        run = AppRun.objects.filter(pk=task.source_id, tenant_id=task.tenant_id).first()
        if not run:
            task.delete(); return
        path = tenant_path(
            Path(settings.BASE_DIR) / "app_runs", task.tenant_id, run.execution_no
        ).resolve()
        if not path.exists():
            path = legacy_tenant_path(
                Path(settings.BASE_DIR) / "app_runs", task.tenant_id, run.execution_no
            ).resolve()
        run.delete()
        if is_managed_storage_path(path, "app_runs", tenant=task.tenant_id):
            shutil.rmtree(path, ignore_errors=True)
    else:
        from performance.models import PerformanceRun
        run = PerformanceRun.objects.filter(pk=task.source_id, tenant_id=task.tenant_id).first()
        if not run:
            task.delete(); return
        path = Path(run.work_dir).resolve() if run.work_dir else None
        run.delete()
        if path and is_managed_storage_path(
            path, "performance_runs", tenant=task.tenant_id
        ):
            shutil.rmtree(path, ignore_errors=True)


class WorkerHeartbeat:
    def __init__(self, kind, name, capabilities, capacity=1):
        self.kind = kind
        self.hostname = socket.gethostname()
        self.process_id = os.getpid()
        self.instance_id = f"{kind}:{self.hostname}:{self.process_id}"
        self.defaults = {
            "name": name, "kind": kind, "hostname": self.hostname, "process_id": self.process_id,
            "capacity": max(1, int(capacity)), "capabilities": capabilities,
        }
        self.started_at = timezone.now()

    def touch(self, active_tasks=0, message=""):
        now = timezone.now()
        for attempt in range(4):
            try:
                worker, _ = ExecutionWorker.objects.update_or_create(
                    instance_id=self.instance_id,
                    defaults={**self.defaults, "status": ExecutionWorker.Status.ONLINE,
                              "active_tasks": max(0, int(active_tasks)), "message": message,
                              "started_at": self.started_at, "last_heartbeat_at": now},
                )
                return worker
            except OperationalError as exc:
                if "locked" not in str(exc).lower() or attempt == 3:
                    raise
                time.sleep(0.1 * (attempt + 1))

    def close(self, message="执行器已正常退出。"):
        ExecutionWorker.objects.filter(instance_id=self.instance_id).update(
            status=ExecutionWorker.Status.OFFLINE, active_tasks=0,
            message=message, last_heartbeat_at=timezone.now(),
        )

    def start_background(self, active_tasks_getter=None, interval=10):
        stop_event = threading.Event()

        def run():
            from django.db import close_old_connections
            while not stop_event.is_set():
                try:
                    close_old_connections()
                    active = active_tasks_getter() if active_tasks_getter else 0
                    self.touch(active_tasks=active)
                except Exception:
                    # 心跳失败不应导致执行器退出；控制中心会按超时判定离线。
                    pass
                finally:
                    close_old_connections()
                stop_event.wait(max(2, interval))

        thread = threading.Thread(target=run, name=f"heartbeat-{self.kind}", daemon=True)
        thread.start()
        return stop_event, thread


def dependency_overview(tenant=None, user=None):
    refresh_worker_states()
    checked_at = timezone.now()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        database = {
            "key": "database", "name": "数据库", "status": "online",
            "message": "连接正常", "last_heartbeat_at": checked_at,
        }
    except Exception as exc:
        database = {
            "key": "database", "name": "数据库", "status": "offline",
            "message": str(exc), "last_heartbeat_at": checked_at,
        }
    services = [database]
    for kind, name in ExecutionWorker.Kind.choices:
        online = worker_is_fresh(kind)
        latest = ExecutionWorker.objects.filter(kind=kind).order_by("-last_heartbeat_at").first()
        services.append({
            "key": kind, "name": name, "status": "online" if online else "offline",
            "message": "心跳正常" if online else "未检测到有效心跳",
            "last_heartbeat_at": latest.last_heartbeat_at if latest else None,
        })
    try:
        from case_app.models import AppExecutionNode
        from case_app.health import refresh_stale_appium_nodes
        from project.access import project_access_q

        refresh_stale_appium_nodes()
        appium_nodes = AppExecutionNode.objects.filter(enabled=True)
        if tenant is not None:
            appium_nodes = appium_nodes.filter(project__tenant=tenant)
        if user is not None:
            appium_nodes = appium_nodes.filter(project_access_q(user, "project__"))
        appium_nodes = appium_nodes.distinct()
        online_count = appium_nodes.filter(status="online").count()
        enabled_count = appium_nodes.count()
        latest_heartbeat = appium_nodes.order_by("-last_seen_at").values_list(
            "last_seen_at", flat=True,
        ).first()
        if enabled_count == 0:
            appium_status = "not_configured"
            appium_message = "当前租户未配置启用的 Appium 节点"
        elif online_count == enabled_count:
            appium_status = "online"
            appium_message = f"{online_count}/{enabled_count} 个启用节点在线"
        elif online_count:
            appium_status = "degraded"
            appium_message = f"{online_count}/{enabled_count} 个启用节点在线"
        else:
            appium_status = "offline"
            appium_message = f"0/{enabled_count} 个启用节点在线"
        services.append({
            "key": "appium", "name": "Appium 服务", "status": appium_status,
            "message": appium_message, "last_heartbeat_at": latest_heartbeat,
        })
    except Exception as exc:
        services.append({
            "key": "appium", "name": "Appium 服务", "status": "offline",
            "message": str(exc), "last_heartbeat_at": None,
        })
    return services
