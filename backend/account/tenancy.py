"""当前租户上下文解析。

第一阶段由前端在 X-Tenant-ID 请求头中传递当前租户；
后端始终以成员关系为准，不信任客户端传入的任意 ID。
"""

from rest_framework.exceptions import PermissionDenied, ValidationError

from .access import is_system_admin
from .models import Tenant, TenantMembership


TENANT_HEADER = "X-Tenant-ID"


def tenants_for_user(user):
    queryset = Tenant.objects.filter(status=Tenant.Status.ACTIVE)
    if is_system_admin(user):
        return queryset
    if not user or not user.is_authenticated:
        return queryset.none()
    return queryset.filter(
        memberships__user=user,
        memberships__status=TenantMembership.Status.ACTIVE,
    ).distinct()


def get_request_tenant(request, *, required=True):
    """解析并校验当前租户。

    未传请求头时回退到用户的第一个可用租户，保证旧客户端在
    过渡期仍可使用；前端完成升级后所有请求都会显式携带租户。
    """

    # drf-spectacular 用匿名 mock request 构建 Schema，并不会执行真实业务请求。
    # 仅对其标记的假视图跳过租户校验，避免文档生成被当成无租户用户访问。
    schema_view = (getattr(request, "parser_context", None) or {}).get("view")
    if getattr(schema_view, "swagger_fake_view", False):
        request.tenant = None
        return None

    tenant_id = str(request.headers.get(TENANT_HEADER) or "").strip()
    queryset = tenants_for_user(request.user)
    if tenant_id:
        try:
            tenant = queryset.filter(pk=tenant_id).first()
        except (TypeError, ValueError):
            raise ValidationError({"tenant": "租户标识格式不正确。"})
        if not tenant:
            raise PermissionDenied("您无权访问该租户。")
    else:
        tenant = queryset.first()

        # 兼容第一阶段之前创建的账号以及旧客户端：只在没有显式
        # X-Tenant-ID 且账号尚无成员关系时，从用户已有项目权限推导。
        # 显式伪造租户头仍会在上方被拒绝。
        if tenant is None and request.user and request.user.is_authenticated:
            from project.access import project_access_q
            from project.models import Project

            tenant = Tenant.objects.filter(
                status=Tenant.Status.ACTIVE,
                projects__in=Project.objects.filter(project_access_q(request.user)),
            ).distinct().order_by("id").first()

    if required and tenant is None:
        raise PermissionDenied("当前账号未加入可用租户。")
    request.tenant = tenant
    return tenant


def is_tenant_admin(user, tenant):
    if is_system_admin(user):
        return True
    return TenantMembership.objects.filter(
        user=user,
        tenant=tenant,
        status=TenantMembership.Status.ACTIVE,
        role__in=[TenantMembership.Role.OWNER, TenantMembership.Role.ADMIN],
    ).exists()


def related_tenant_id(value):
    """从核心对象或其项目/套件关联中解析租户。"""
    if value is None:
        return None
    tenant_id = getattr(value, "tenant_id", None)
    if tenant_id:
        return tenant_id
    project = getattr(value, "project", None)
    if project is not None and getattr(project, "tenant_id", None):
        return project.tenant_id
    environment = getattr(value, "environment", None)
    if environment is not None and getattr(environment, "project_id", None):
        return environment.project.tenant_id
    return None


def validate_tenant_relations(request, **relations):
    """统一拒绝将其他租户的项目、套件、场景或用例关联进当前租户。"""
    tenant = get_request_tenant(request)
    errors = {}
    for field, value in relations.items():
        values = value if isinstance(value, (list, tuple, set)) else [value]
        if any(related_tenant_id(item) not in (None, tenant.id) for item in values):
            errors[field] = "不能关联其他租户的数据。"
    if errors:
        raise ValidationError(errors)
    return tenant


class TenantScopedViewSetMixin:
    """核心业务 ViewSet 的统一租户查询和写入入口。"""

    tenant_lookup = "tenant"

    def current_tenant(self):
        return get_request_tenant(self.request)

    def tenant_scope(self, queryset, lookup=None):
        return queryset.filter(**{lookup or self.tenant_lookup: self.current_tenant()})

    def save_in_tenant(self, serializer, **kwargs):
        return serializer.save(tenant=self.current_tenant(), **kwargs)
