"""执行产物保留策略。只清理平台明确管理的本地目录。"""
import logging
import shutil
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import DatabaseError
from django.utils import timezone
from account.tenant_runtime import is_managed_storage_path, legacy_tenant_path, tenant_path

logger = logging.getLogger(__name__)


def _is_within(path, root):
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _entry_expired(path, cutoff_timestamp):
    """目录以其内部最新文件的时间为准，避免目录本身 mtime 较旧时误删。"""
    try:
        latest_mtime = path.stat().st_mtime
        if path.is_dir() and not path.is_symlink():
            for child in path.rglob("*"):
                try:
                    latest_mtime = max(latest_mtime, child.stat().st_mtime)
                except OSError:
                    continue
        return latest_mtime < cutoff_timestamp
    except OSError:
        return False


def _remove_entry(path, dry_run=False):
    if dry_run:
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def cleanup_expired_files(
    retention_days=None, *, dry_run=False, base_dir=None, active_paths=None, now=None,
    include_database_records=None,
):
    """清理超过保留期的执行目录、报告、日志和性能报告，返回清理统计。"""
    # 显式指定其他根目录时默认只处理该目录下的文件，不应顺带
    # 删除当前平台数据库中的性能/App 执行记录。
    if include_database_records is None:
        include_database_records = base_dir is None
    if retention_days is None:
        configured_days = None
        if include_database_records:
            try:
                from system.models import SystemConfiguration

                configured_days = SystemConfiguration.objects.filter(pk=1).values_list("report_retention_days", flat=True).first()
            except DatabaseError:
                # 数据库尚未迁移或暂时不可用时，仍使用环境配置保证清理任务可执行。
                configured_days = None
        retention_days = configured_days or settings.FILE_RETENTION_DAYS
    days = max(1, int(retention_days))
    base = Path(base_dir or settings.BASE_DIR).resolve()
    current_time = now or timezone.now()
    cutoff = current_time - timedelta(days=days)
    cutoff_timestamp = cutoff.timestamp()

    upload_root = (base / "upload_yaml").resolve()
    if active_paths is None:
        from .models import RunResult
        active_statuses = [
            RunResult.RunStatus.Init,
            RunResult.RunStatus.Ready,
            RunResult.RunStatus.Running,
            RunResult.RunStatus.Reporting,
            RunResult.RunStatus.Paused,
        ]
        active_paths = RunResult.objects.filter(status__in=active_statuses).values_list("path", flat=True)
    protected = set()
    for value in active_paths or []:
        path = Path(str(value))
        if not path.is_absolute():
            path = base / path
        protected.add(path.resolve())

    removed = []
    removed_performance_run_ids = []
    removed_app_run_ids = []
    errors = []

    # 每次执行均生成 result_* 独立目录；整个目录按最后修改时间统一过期。
    tenant_storage_root = (base / "tenant_storage").resolve()
    paths = []
    if tenant_storage_root.exists():
        paths.extend(tenant_storage_root.glob("tenant_*/runs/suite/result_*"))
    if upload_root.exists():
        paths.extend(upload_root.glob("tenant_*/result_*"))
        paths.extend(upload_root.glob("result_*"))
    if paths:
        for path in paths:
            resolved = path.resolve()
            if resolved in protected or not (
                _is_within(resolved, upload_root) or _is_within(resolved, tenant_storage_root)
            ):
                continue
            if _entry_expired(resolved, cutoff_timestamp):
                try:
                    _remove_entry(resolved, dry_run)
                    removed.append(str(resolved))
                except OSError as exc:
                    errors.append({"path": str(resolved), "error": str(exc)})

    # 兼容旧版本曾写入的全局日志、第三方报告和临时结果目录。
    legacy_roots = [
        base / "logs",
        base / "fullstack_framework" / "logs",
        base / "fullstack_framework" / "report",
        base / "fullstack_framework" / "temps",
    ]
    for root in legacy_roots:
        root = root.resolve()
        if not root.exists() or not _is_within(root, base):
            continue
        for path in list(root.iterdir()):
            if not _is_within(path, root) or not _entry_expired(path, cutoff_timestamp):
                continue
            try:
                _remove_entry(path, dry_run)
                removed.append(str(path))
            except OSError as exc:
                errors.append({"path": str(path), "error": str(exc)})

    # 性能报告与接口执行文件共用同一保留期。过期时同步删除
    # 报告主记录、级联的指标明细以及 performance_runs 下的运行产物。
    from performance.models import PerformanceRun

    terminal_statuses = [
        PerformanceRun.Status.PASSED,
        PerformanceRun.Status.FAILED,
        PerformanceRun.Status.ERROR,
        PerformanceRun.Status.STOPPED,
    ]
    expired_runs = list(
        PerformanceRun.objects.filter(status__in=terminal_statuses, finished_at__lt=cutoff)
        .only("id", "work_dir", "tenant_id")
        .order_by("id")
    ) if include_database_records else []
    for run in expired_runs:
        run_id = run.id
        work_dir = Path(run.work_dir) if run.work_dir else None
        if work_dir and not work_dir.is_absolute():
            work_dir = base / work_dir
        resolved_work_dir = work_dir.resolve() if work_dir else None
        if resolved_work_dir and resolved_work_dir.exists():
            if not is_managed_storage_path(
                resolved_work_dir, "performance_runs", tenant=run.tenant_id, base_dir=base
            ):
                errors.append({"path": str(resolved_work_dir), "error": "性能任务目录不在受管的 performance_runs 目录内"})
            else:
                try:
                    _remove_entry(resolved_work_dir, dry_run)
                    removed.append(str(resolved_work_dir))
                except OSError as exc:
                    errors.append({"path": str(resolved_work_dir), "error": str(exc)})
                    continue
        if not dry_run:
            run.delete()
        removed_performance_run_ids.append(run_id)

    # App 自动化报告沿用系统统一保留天数，过期时同步删除步骤明细、附件记录和文件。
    from case_app.models import AppRun

    app_root = (base / "app_runs").resolve()
    expired_app_runs = list(AppRun.objects.filter(
        status__in=[AppRun.Status.PASSED, AppRun.Status.FAILED, AppRun.Status.ERROR, AppRun.Status.STOPPED],
        finished_at__lt=cutoff,
    ).only("id", "execution_no", "tenant_id").order_by("id")) if include_database_records else []
    for run in expired_app_runs:
        run_path = tenant_path(app_root, run.tenant_id, run.execution_no).resolve()
        if not run_path.exists():
            run_path = legacy_tenant_path(app_root, run.tenant_id, run.execution_no).resolve()
        if run_path.exists() and is_managed_storage_path(
            run_path, "app_runs", tenant=run.tenant_id, base_dir=base
        ):
            try:
                _remove_entry(run_path, dry_run)
                removed.append(str(run_path))
            except OSError as exc:
                errors.append({"path": str(run_path), "error": str(exc)})
                continue
        if not dry_run:
            run.delete()
        removed_app_run_ids.append(run.id)

    result = {
        "retention_days": days,
        "cutoff": cutoff.isoformat(),
        "removed_count": len(removed),
        "removed": removed,
        "removed_performance_run_count": len(removed_performance_run_ids),
        "removed_performance_run_ids": removed_performance_run_ids,
        "removed_app_run_count": len(removed_app_run_ids),
        "removed_app_run_ids": removed_app_run_ids,
        "errors": errors,
        "dry_run": dry_run,
    }
    logger.info("本地执行文件清理完成：%s", result)
    return result
