"""统一执行任务的先进先出资源调度器。"""
import time

from django.conf import settings
from django.db import OperationalError, transaction
from django.db.models import Count, F, Q
from django.utils import timezone
from django_q.tasks import async_task

from .models import ExecutionTask
from account.models import Tenant
from account.tenant_runtime import tenant_has_regular_execution_capacity
from system.runtime import configured_max_worker_count


SCHEDULER_TYPES = (ExecutionTask.SourceType.SUITE, ExecutionTask.SourceType.APP)
ACTIVE_STATUSES = (
    ExecutionTask.Status.PREPARING,
    ExecutionTask.Status.RUNNING,
    ExecutionTask.Status.PAUSED,
    ExecutionTask.Status.REPORTING,
)
def _normalized_resources(task):
    return {str(item) for item in (task.resource_keys or []) if str(item).strip()}


def _resource_conflicts(resources, occupied_resources):
    conflicts = set(resources & occupied_resources)
    device_ids = []
    for resource in resources:
        if resource.startswith("app-device:"):
            try:
                device_ids.append(int(resource.split(":", 1)[1]))
            except (TypeError, ValueError):
                conflicts.add(resource)
    if device_ids:
        from case_app.models import AppDevice

        available_ids = set(AppDevice.objects.filter(
            id__in=device_ids, enabled=True, state=AppDevice.State.ONLINE,
        ).values_list("id", flat=True))
        conflicts.update(
            f"app-device:{device_id}" for device_id in device_ids if device_id not in available_ids
        )
    return sorted(conflicts)


def _enqueue_task(task):
    """将已经获得执行槽位的源任务放入 Django-Q。"""
    if task.source_type == ExecutionTask.SourceType.SUITE:
        from suite.models import RunResult

        run = RunResult.objects.select_related("suite").get(
            pk=task.source_id, tenant_id=task.tenant_id,
        )
        return async_task(
            "suite.tasks.run_pytest",
            str(run.path), run.id, run.suite.case_api_count(),
            run.suite.case_ui_count() + run.suite.case_playwright_count() + run.suite.case_app_count(),
            str(task.tenant_id),
            task_name=f"suite-run-{run.id}",
            group=f"tenant-{task.tenant_id}",
            q_options={
                # Django-Q 的外层时限必须晚于计划自身的时限，给准备、归档和状态收口留余量。
                "timeout": max(1, int(run.timeout_seconds or 1800))
                + settings.EXECUTION_TASK_FINISHING_GRACE_SECONDS,
            },
        )
    if task.source_type == ExecutionTask.SourceType.APP:
        return async_task(
            "case_app.executor.execute_app_run", task.source_id, str(task.tenant_id),
            task_name=f"app-run-{task.source_id}",
            group=f"tenant-{task.tenant_id}",
        )
    raise ValueError(f"不支持派发的任务类型：{task.source_type}")


def _reserve_dispatches():
    """在同一事务中按入队时间预留槽位和独占资源。"""
    now = timezone.now()
    capacity = configured_max_worker_count()

    # dispatched_at 表示消息已成功交给 Django-Q。执行器离线时，消息仍会
    # 持久化保留在队列中；不能仅因等待时间较长就清空该标记，否则 worker
    # 恢复时原消息和新消息会同时执行。确需重入队时由“恢复任务”显式处理。

    reserved = list(ExecutionTask.objects.filter(
        source_type__in=SCHEDULER_TYPES,
    ).filter(
        Q(status__in=ACTIVE_STATUSES)
        | Q(status=ExecutionTask.Status.QUEUED, dispatched_at__isnull=False)
    ).order_by("queued_at", "id"))
    available = max(0, capacity - len(reserved))
    occupied_resources = set()
    active_by_tenant = dict(
        ExecutionTask.objects.filter(
            source_type__in=SCHEDULER_TYPES,
            status__in=ACTIVE_STATUSES,
        )
        .values("tenant_id")
        .annotate(total=Count("id"))
        .values_list("tenant_id", "total")
    )
    for task in reserved:
        occupied_resources.update(_normalized_resources(task))
        if task.status == ExecutionTask.Status.QUEUED:
            active_by_tenant[task.tenant_id] = active_by_tenant.get(task.tenant_id, 0) + 1

    tenants = {
        tenant.pk: tenant for tenant in Tenant.objects.filter(
            pk__in={task.tenant_id for task in reserved}
        )
    }

    candidates = list(ExecutionTask.objects.select_for_update().filter(
        source_type__in=SCHEDULER_TYPES,
        status=ExecutionTask.Status.QUEUED,
        dispatched_at__isnull=True,
    ).order_by("queued_at", "id"))
    selected = []
    for task in candidates:
        if available <= 0:
            break
        resources = _normalized_resources(task)
        tenant = tenants.get(task.tenant_id)
        if tenant is None:
            tenant = Tenant.objects.get(pk=task.tenant_id)
            tenants[tenant.pk] = tenant
        if not tenant_has_regular_execution_capacity(
            tenant, active_by_tenant.get(task.tenant_id, 0)
        ):
            task.waiting_reason = "等待当前租户普通任务并发额度释放"
            task.save(update_fields=["waiting_reason", "updated_at"])
            # 租户配额只限制本租户，不能阻塞队列中其他租户的任务。
            continue
        conflicts = _resource_conflicts(resources, occupied_resources)
        if conflicts:
            # 严格 FIFO：队首资源不足时不允许后来的任务越过它抢占空闲槽位。
            task.waiting_reason = f"等待资源释放：{', '.join(conflicts)}"
            task.save(update_fields=["waiting_reason", "updated_at"])
            break
        task.dispatched_at = now
        task.dispatch_attempts = F("dispatch_attempts") + 1
        task.waiting_reason = ""
        task.save(update_fields=["dispatched_at", "dispatch_attempts", "waiting_reason", "updated_at"])
        selected.append(task.id)
        occupied_resources.update(resources)
        active_by_tenant[task.tenant_id] = active_by_tenant.get(task.tenant_id, 0) + 1
        available -= 1

    if candidates and available <= 0:
        ExecutionTask.objects.filter(
            source_type__in=SCHEDULER_TYPES,
            status=ExecutionTask.Status.QUEUED,
            dispatched_at__isnull=True,
            waiting_reason="",
        ).update(waiting_reason="等待执行器空闲")
    return selected


def dispatch_waiting_tasks():
    """派发最早进入队列且资源满足的任务；并发调用时自动短暂重试。"""
    selected = []
    for attempt in range(4):
        try:
            with transaction.atomic():
                selected = _reserve_dispatches()
            break
        except OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == 3:
                raise
            time.sleep(0.1 * (attempt + 1))

    dispatched = 0
    for task_id in selected:
        try:
            task = ExecutionTask.objects.get(pk=task_id)
            _enqueue_task(task)
            dispatched += 1
        except Exception as exc:
            ExecutionTask.objects.filter(pk=task_id, status=ExecutionTask.Status.QUEUED).update(
                dispatched_at=None,
                waiting_reason=f"派发失败，等待重试：{str(exc)[:160]}",
            )
    return dispatched
