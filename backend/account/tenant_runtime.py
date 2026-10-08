"""租户执行配额和本地文件命名空间。"""
import re
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.db.models import Q


MANAGED_STORAGE_ROOTS = (
    "upload_yaml",
    "performance_runs",
    "app_runs",
    "uploaded_api_files",
    "uploaded_ui_files",
    "app_uploads",
    "runtime_auth_locks",
    "logs",
)
MANAGED_STORAGE_LAYOUT = {
    "upload_yaml": ("runs", "suite"),
    "performance_runs": ("runs", "performance"),
    "app_runs": ("runs", "app"),
    "uploaded_api_files": ("uploads", "api"),
    "uploaded_ui_files": ("uploads", "ui"),
    "app_uploads": ("uploads", "app"),
    "runtime_auth_locks": ("locks",),
    "logs": ("logs",),
}
TENANT_STORAGE_ROOT = "tenant_storage"


class TenantQuotaExceeded(ValueError):
    pass


@lru_cache(maxsize=2048)
def _tenant_slug_for_id(tenant_id):
    try:
        from .models import Tenant
        return Tenant.objects.filter(pk=tenant_id).values_list("slug", flat=True).first() or ""
    except Exception:
        return ""


def _tenant_identity(tenant, tenant_slug=None):
    tenant_id = getattr(tenant, "pk", tenant)
    value = str(tenant_id or "").strip().lower()
    if not value or any(character not in "0123456789abcdefABCDEF-" for character in value):
        raise ValueError("租户标识不正确。")
    slug = tenant_slug or getattr(tenant, "slug", "")
    if not slug:
        # 数据库尚未初始化或纯路径单测时使用稳定回退值。
        slug = _tenant_slug_for_id(value)
    code = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(slug).strip()).strip("-_") or "unknown"
    return value, code.lower()


def tenant_directory_name(tenant, tenant_slug=None):
    tenant_id, code = _tenant_identity(tenant, tenant_slug)
    return f"tenant_{code}_{tenant_id}"


def tenant_storage_root(tenant, *, base_dir=None, tenant_slug=None):
    """返回租户的独立存储根目录。

    租户编码仅用于可读展示，UUID 才是稳定身份。如果编码后续被修改，
    优先沿用同一 UUID 的已有目录，避免文件被切成两份。
    """
    tenant_id, code = _tenant_identity(tenant, tenant_slug)
    storage_root = Path(base_dir or settings.BASE_DIR) / TENANT_STORAGE_ROOT
    preferred = storage_root / f"tenant_{code}_{tenant_id}"
    if preferred.exists():
        return preferred
    candidates = sorted(storage_root.glob(f"tenant_*_{tenant_id}")) if storage_root.exists() else []
    return candidates[0] if candidates else preferred


def initialize_tenant_storage(tenant, *, base_dir=None):
    """创建完整租户目录；目录权限不对其他系统用户开放。"""
    root = tenant_storage_root(tenant, base_dir=base_dir)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    for namespace in MANAGED_STORAGE_ROOTS:
        path = root / Path(*MANAGED_STORAGE_LAYOUT[namespace])
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.chmod(0o700)
    return root


def tenant_path(root, tenant, *parts):
    """生成 ``tenant_<编码>_<UUID>/<业务空间>`` 下的路径。"""
    namespace_root = Path(root)
    tenant_root = tenant_storage_root(tenant, base_dir=namespace_root.parent)
    layout = MANAGED_STORAGE_LAYOUT.get(namespace_root.name, (namespace_root.name,))
    return tenant_root / Path(*layout) / Path(*map(str, parts))


def legacy_tenant_path(root, tenant, *parts):
    """第三阶段旧目录，仅用于过渡期读取和清理。"""
    tenant_id, _ = _tenant_identity(tenant)
    return Path(root) / f"tenant_{tenant_id}" / Path(*map(str, parts))


def is_managed_storage_path(path, namespace, *, tenant=None, base_dir=None, allow_legacy=True):
    """验证路径确实位于指定租户/业务存储空间内。"""
    try:
        resolved = Path(path).resolve()
        base = Path(base_dir or settings.BASE_DIR).resolve()
        if tenant is not None:
            roots = [tenant_path(base / namespace, tenant).resolve()]
            if allow_legacy:
                roots.append(legacy_tenant_path(base / namespace, tenant).resolve())
            return any(resolved != root and root in resolved.parents for root in roots)

        try:
            relative = resolved.relative_to((base / TENANT_STORAGE_ROOT).resolve())
        except ValueError:
            relative = None
        if (
            relative is not None
            and len(relative.parts) >= 2 + len(MANAGED_STORAGE_LAYOUT.get(namespace, (namespace,)))
            and relative.parts[0].startswith("tenant_")
            and tuple(relative.parts[1:1 + len(MANAGED_STORAGE_LAYOUT.get(namespace, (namespace,)))])
            == MANAGED_STORAGE_LAYOUT.get(namespace, (namespace,))
        ):
            return True
        if allow_legacy:
            legacy_root = (base / namespace).resolve()
            return legacy_root in resolved.parents
        return False
    except (OSError, ValueError):
        return False


def _directory_size(path):
    total = 0
    if not path.exists():
        return total
    for item in path.rglob("*"):
        try:
            if item.is_file() and not item.is_symlink():
                total += item.stat().st_size
        except OSError:
            continue
    return total


def tenant_storage_usage(tenant_id, *, base_dir=None):
    base = Path(base_dir or settings.BASE_DIR)
    total = _directory_size(tenant_storage_root(tenant_id, base_dir=base))
    # 迁移期同时统计旧目录，防止切换新结构后配额被绕过。
    total += sum(_directory_size(legacy_tenant_path(base / root, tenant_id)) for root in MANAGED_STORAGE_ROOTS)
    return total


def ensure_tenant_storage_capacity(tenant, reserve_bytes=0, *, base_dir=None):
    quota = max(0, int(tenant.storage_quota_bytes or 0))
    used = tenant_storage_usage(tenant.pk, base_dir=base_dir)
    requested = max(0, int(reserve_bytes or 0))
    if quota and used + requested > quota:
        raise TenantQuotaExceeded(
            f"当前租户存储配额不足（已使用 {used} 字节，配额 {quota} 字节）。"
        )
    return used


def tenant_active_regular_execution_count(tenant_id):
    from execution_control.models import ExecutionTask

    return ExecutionTask.objects.filter(
        tenant_id=tenant_id,
        source_type__in=(ExecutionTask.SourceType.SUITE, ExecutionTask.SourceType.APP),
    ).filter(
        Q(status__in=(
            ExecutionTask.Status.PREPARING, ExecutionTask.Status.RUNNING,
            ExecutionTask.Status.PAUSED, ExecutionTask.Status.REPORTING,
        )) | Q(status=ExecutionTask.Status.QUEUED, dispatched_at__isnull=False)
    ).count()


def tenant_has_regular_execution_capacity(tenant, active_count=None):
    limit = max(1, int(tenant.max_regular_concurrent_executions or 1))
    count = (
        tenant_active_regular_execution_count(tenant.pk)
        if active_count is None else int(active_count)
    )
    return count < limit


def tenant_active_performance_execution_count(tenant_id):
    from execution_control.models import ExecutionTask

    return ExecutionTask.objects.filter(
        tenant_id=tenant_id,
        source_type=ExecutionTask.SourceType.PERFORMANCE,
    ).filter(
        Q(status__in=(
            ExecutionTask.Status.PREPARING, ExecutionTask.Status.RUNNING,
            ExecutionTask.Status.PAUSED, ExecutionTask.Status.REPORTING,
        )) | Q(status=ExecutionTask.Status.QUEUED, dispatched_at__isnull=False)
    ).count()


def tenant_has_performance_execution_capacity(tenant, active_count=None):
    limit = max(1, min(32, int(tenant.max_performance_concurrent_executions or 1)))
    count = (
        tenant_active_performance_execution_count(tenant.pk)
        if active_count is None else int(active_count)
    )
    return count < limit
