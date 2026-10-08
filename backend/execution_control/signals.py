from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.db.utils import OperationalError, ProgrammingError

from case_app.models import AppDevice, AppRun
from performance.models import PerformanceRun
from suite.models import RunResult

from .models import ExecutionTask
from .sync import sync_app_run, sync_performance_run, sync_suite_run


def backfill_execution_tasks(**kwargs):
    """首次迁移后自动回填历史任务，后续保持幂等对账。"""
    from .sync import sync_all_existing
    try:
        sync_all_existing()
    except (OperationalError, ProgrammingError):
        # SQLite 本地执行器可能正在写心跳；迁移本身已完成时不应因历史对账报失败。
        # 新任务仍由 post_save 实时同步，管理员也可从控制中心手动对账。
        return


@receiver(post_save, sender=RunResult)
def update_suite_task(sender, instance, **kwargs):
    _safe_sync(sync_suite_run, instance)
    if instance.status in {
        RunResult.RunStatus.Done,
        RunResult.RunStatus.Error,
        RunResult.RunStatus.Canceled,
    }:
        from suite.run_metrics import invalidate_overview_cache
        invalidate_overview_cache(instance.tenant_id)


@receiver(post_save, sender=AppRun)
def update_app_task(sender, instance, **kwargs):
    _safe_sync(sync_app_run, instance)


@receiver(post_save, sender=PerformanceRun)
def update_performance_task(sender, instance, **kwargs):
    _safe_sync(sync_performance_run, instance)


def _safe_sync(callback, instance):
    # 全新数据库迁移期间，源表可能先于统一台账表建立。
    try:
        callback(instance)
    except (OperationalError, ProgrammingError):
        return


@receiver(post_delete, sender=RunResult)
def delete_suite_task(sender, instance, **kwargs):
    _safe_delete(instance.tenant_id, ExecutionTask.SourceType.SUITE, instance.pk)


@receiver(post_delete, sender=AppRun)
def delete_app_task(sender, instance, **kwargs):
    _safe_delete(instance.tenant_id, ExecutionTask.SourceType.APP, instance.pk)


@receiver(post_delete, sender=PerformanceRun)
def delete_performance_task(sender, instance, **kwargs):
    _safe_delete(instance.tenant_id, ExecutionTask.SourceType.PERFORMANCE, instance.pk)


def _safe_delete(tenant_id, source_type, source_id):
    try:
        ExecutionTask.objects.filter(
            tenant_id=tenant_id, source_type=source_type, source_id=source_id,
        ).delete()
    except (OperationalError, ProgrammingError):
        return


@receiver(post_save, sender=AppDevice)
def dispatch_after_device_release(sender, instance, **kwargs):
    if instance.enabled and instance.state == AppDevice.State.ONLINE:
        from .dispatcher import dispatch_waiting_tasks
        transaction.on_commit(dispatch_waiting_tasks)
