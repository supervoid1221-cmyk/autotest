"""项目成员的数据权限工具。"""
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from account.access import is_system_admin

from .models import Project


def is_admin(user):
    """兼容既有调用：系统管理员拥有全部项目及关联数据权限。"""
    return is_system_admin(user)


def project_access_q(user, prefix=""):
    """返回可访问项目的 Q 条件，prefix 例如 ``project__``。"""
    # 管理员拥有全项目数据权限；普通用户仅能访问自己负责或加入的项目。
    if is_admin(user):
        return Q()
    if not user or not user.is_authenticated:
        return Q(**{f"{prefix}pk__in": []})
    return Q(**{f"{prefix}pm": user}) | Q(**{f"{prefix}user_list": user})


def accessible_projects(user):
    """返回当前用户可访问的项目 QuerySet。"""
    queryset = Project.objects.all()
    if is_admin(user):
        return queryset
    if not user or not user.is_authenticated:
        return queryset.none()
    return queryset.filter(project_access_q(user)).distinct()


def filter_all_project_access(
    queryset,
    user,
    primary_field,
    projects_field,
    dependent_project_fields=(),
):
    """过滤必须同时拥有主项目和全部关联项目权限的数据。

    跨项目场景会携带多个项目的接口、参数和执行配置。仅拥有其中一个项目
    权限时不能返回整条场景，否则会间接泄露其他项目的数据。
    """
    if is_admin(user):
        return queryset
    visible_projects = accessible_projects(user)
    invisible_projects = Project.objects.exclude(pk__in=visible_projects.values("pk"))
    queryset = queryset.filter(
        **{f"{primary_field}__in": visible_projects}
    ).exclude(
        **{f"{projects_field}__in": invisible_projects}
    )
    for field in dependent_project_fields:
        queryset = queryset.exclude(**{f"{field}__in": invisible_projects})
    return queryset.distinct()


def can_access_project(user, project):
    return bool(project and user and user.is_authenticated and (is_admin(user) or (
        project.pm_id == user.id or project.user_list.filter(pk=user.id).exists()
    )))


def require_project_access(user, project):
    if not can_access_project(user, project):
        raise PermissionDenied("您不是该项目成员，无权访问项目数据。")


def require_projects_access(user, projects):
    """要求用户拥有集合中每一个项目的访问权限。"""
    for project in projects:
        require_project_access(user, project)


def require_project_manager(user, project):
    if not (is_admin(user) or project.pm_id == user.id):
        raise PermissionDenied("仅项目负责人可以维护项目成员。")
