"""执行产物保留策略。只清理平台明确管理的本地目录。"""
import logging
import shutil
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone

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


def cleanup_expired_files(retention_days=None, *, dry_run=False, base_dir=None, active_paths=None, now=None):
    """清理超过保留期的执行目录、报告和日志，返回清理统计。"""
    days = max(1, int(retention_days or settings.FILE_RETENTION_DAYS))
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
    errors = []

    # 每次执行均生成 result_* 独立目录；整个目录按最后修改时间统一过期。
    if upload_root.exists():
        for path in upload_root.glob("result_*"):
            resolved = path.resolve()
            if resolved in protected or not _is_within(resolved, upload_root):
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

    result = {
        "retention_days": days,
        "cutoff": cutoff.isoformat(),
        "removed_count": len(removed),
        "removed": removed,
        "errors": errors,
        "dry_run": dry_run,
    }
    logger.info("本地执行文件清理完成：%s", result)
    return result
