import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import close_old_connections, transaction
from django.utils import timezone

from performance.models import PerformanceRun
from performance import runner as performance_runner
from execution_control.models import ExecutionTask, ExecutionWorker
from execution_control.services import WorkerHeartbeat, diagnose_tasks
from account.models import Tenant
from account.tenant_runtime import (
    ensure_tenant_storage_capacity,
    tenant_has_performance_execution_capacity,
)
from system.runtime import configured_max_performance_worker_count


def _execute_run(run_id, tenant_id):
    """每个并发槽使用独立数据库连接执行一个 k6 任务。"""
    close_old_connections()
    try:
        performance_runner.execute_run(run_id, str(tenant_id))
    finally:
        close_old_connections()


def _claim_next_run():
    """原子领取一条符合租户配额和存储限额的性能任务。"""
    with transaction.atomic():
        runs = PerformanceRun.objects.select_for_update(skip_locked=True).filter(
            status=PerformanceRun.Status.QUEUED, stop_requested=False,
        ).select_related("tenant").order_by("created_at")
        for candidate in runs:
            tenant = Tenant.objects.select_for_update().get(pk=candidate.tenant_id)
            if not tenant_has_performance_execution_capacity(tenant):
                ExecutionTask.objects.filter(
                    tenant=tenant,
                    source_type=ExecutionTask.SourceType.PERFORMANCE,
                    source_id=candidate.pk,
                ).update(waiting_reason="等待当前租户性能任务并发额度释放")
                continue
            try:
                ensure_tenant_storage_capacity(tenant)
            except ValueError as exc:
                candidate.status = PerformanceRun.Status.ERROR
                candidate.error_message = str(exc)
                candidate.finished_at = timezone.now()
                candidate.save(update_fields=["status", "error_message", "finished_at", "updated_at"])
                continue
            candidate.status = PerformanceRun.Status.PREPARING
            candidate.save(update_fields=["status", "updated_at"])
            return candidate.id, candidate.tenant_id
    return None


class Command(BaseCommand):
    help = "运行独立性能测试 Worker，按系统配置并发执行等待中的 k6 任务。"

    def add_arguments(self, parser):
        parser.add_argument("--poll-interval", type=float, default=1.0)

    def handle(self, *args, **options):
        interval = max(0.2, float(options["poll_interval"]))
        capacity = configured_max_performance_worker_count()
        heartbeat = WorkerHeartbeat(
            ExecutionWorker.Kind.PERFORMANCE, "性能执行器", ["k6"], capacity=capacity,
        )
        heartbeat.touch(message=f"性能执行器已启动，并发数 {capacity}。")
        self.stdout.write(self.style.SUCCESS(f"Performance worker started (capacity={capacity})"))
        futures = {}
        last_heartbeat = 0.0
        executor = ThreadPoolExecutor(max_workers=32, thread_name_prefix="performance-run")
        try:
            while True:
                for future in [item for item in futures if item.done()]:
                    run_id = futures.pop(future)
                    try:
                        future.result()
                    except Exception as exc:
                        self.stderr.write(f"性能任务 {run_id} 执行线程异常：{exc}")

                capacity = configured_max_performance_worker_count()
                heartbeat.defaults["capacity"] = capacity
                # Worker 领取后异常退出时，未创建进程的任务可安全重新排队。
                PerformanceRun.objects.filter(
                    status=PerformanceRun.Status.PREPARING,
                    process_id__isnull=True,
                    updated_at__lt=timezone.now() - timedelta(minutes=2),
                ).update(status=PerformanceRun.Status.QUEUED, started_at=None)

                for _ in range(max(0, capacity - len(futures))):
                    claimed = _claim_next_run()
                    if claimed is None:
                        break
                    run_id, tenant_id = claimed
                    futures[executor.submit(_execute_run, run_id, tenant_id)] = run_id

                now = time.monotonic()
                if now - last_heartbeat >= 5:
                    diagnose_tasks()
                    heartbeat.touch(
                        active_tasks=len(futures),
                        message=f"性能执行器运行正常，并发数 {capacity}。",
                    )
                    last_heartbeat = now
                time.sleep(interval)
        finally:
            executor.shutdown(wait=True)
            heartbeat.close()
