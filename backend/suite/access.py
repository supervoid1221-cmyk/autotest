"""测试套件及其跨项目执行内容的权限工具。"""
from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from project.access import accessible_projects, is_admin, require_project_access, require_projects_access
from project.models import Project

from .models import Suite


def filter_suite_access(queryset, user, prefix=""):
    """仅保留用户有权访问全部执行内容的套件关联数据。"""
    if is_admin(user):
        return queryset
    visible_projects = accessible_projects(user)
    invisible_projects = Project.objects.exclude(pk__in=visible_projects.values("pk"))
    return queryset.filter(
        **{f"{prefix}environment__project__in": visible_projects}
    ).exclude(
        **{f"{prefix}scenarios__project__in": invisible_projects}
    ).exclude(
        **{f"{prefix}scenarios__projects__in": invisible_projects}
    ).exclude(
        **{f"{prefix}scenarios__steps__endpoint__project__in": invisible_projects}
    ).exclude(
        **{f"{prefix}ui_cases__project__in": invisible_projects}
    ).exclude(
        **{f"{prefix}playwright_cases__project__in": invisible_projects}
    ).exclude(
        **{f"{prefix}app_cases__project__in": invisible_projects}
    ).exclude(
        **{f"{prefix}execution_items__scenario__project__in": invisible_projects}
    ).exclude(
        **{f"{prefix}execution_items__scenario__projects__in": invisible_projects}
    ).exclude(
        **{
            f"{prefix}execution_items__scenario__steps__endpoint__project__in":
                invisible_projects
        }
    ).exclude(
        **{f"{prefix}execution_items__ui_case__project__in": invisible_projects}
    ).exclude(
        **{f"{prefix}execution_items__playwright_case__project__in": invisible_projects}
    ).exclude(
        **{f"{prefix}execution_items__yaml_case__project__in": invisible_projects}
    ).exclude(
        **{f"{prefix}execution_items__app_case__project__in": invisible_projects}
    ).distinct()


def accessible_suites(user):
    return filter_suite_access(Suite.objects.all(), user)


def filter_suite_project(queryset, project_id, prefix=""):
    """按套件实际关联的任一项目过滤，并与列表中的“所属项目”口径保持一致。"""
    try:
        project_id = int(project_id)
    except (TypeError, ValueError):
        return queryset.none()
    if project_id <= 0:
        return queryset.none()

    return queryset.filter(
        Q(**{f"{prefix}environment__project_id": project_id})
        | Q(**{f"{prefix}scenarios__project_id": project_id})
        | Q(**{f"{prefix}scenarios__projects__id": project_id})
        | Q(**{f"{prefix}scenarios__steps__endpoint__project_id": project_id})
        | Q(**{f"{prefix}ui_cases__project_id": project_id})
        | Q(**{f"{prefix}playwright_cases__project_id": project_id})
        | Q(**{f"{prefix}app_cases__project_id": project_id})
        | Q(**{f"{prefix}execution_items__scenario__project_id": project_id})
        | Q(**{f"{prefix}execution_items__scenario__projects__id": project_id})
        | Q(**{f"{prefix}execution_items__scenario__steps__endpoint__project_id": project_id})
        | Q(**{f"{prefix}execution_items__ui_case__project_id": project_id})
        | Q(**{f"{prefix}execution_items__playwright_case__project_id": project_id})
        | Q(**{f"{prefix}execution_items__yaml_case__project_id": project_id})
        | Q(**{f"{prefix}execution_items__app_case__project_id": project_id})
    ).distinct()


def require_suite_access(user, suite):
    """要求用户拥有套件主项目及当前全部执行内容的项目权限。"""
    if not suite.environment_id:
        raise PermissionDenied("套件未配置执行环境，无法确定项目权限。")
    require_project_access(user, suite.environment.project)
    for scenario in suite.scenarios.select_related("project").prefetch_related("projects"):
        require_project_access(user, scenario.project)
        require_projects_access(user, scenario.projects.all())
    require_projects_access(user, (case.project for case in suite.ui_cases.select_related("project")))
    require_projects_access(
        user, (case.project for case in suite.playwright_cases.select_related("project")),
    )
    require_projects_access(
        user, (item.yaml_case.project for item in suite.execution_items.filter(
            item_type="yaml_ui",
        ).select_related("yaml_case__project") if item.yaml_case),
    )
    require_projects_access(user, (case.project for case in suite.app_cases.select_related("project")))
