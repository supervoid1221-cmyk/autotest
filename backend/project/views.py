from time import perf_counter

import requests
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import DatabaseConnection, DynamicFunction, Environment, Project, ProjectVariable
from .serializers import DatabaseConnectionSerializer, DynamicFunctionSerializer, EnvironmentSerializer, ProjectSerializer, ProjectVariableSerializer
from .database_functions import test_database_connection, test_database_query
from .dynamic_functions import execute_dynamic_function, function_names, parse_dynamic_arguments, validate_dynamic_code, whitelist
from .access import (
    can_access_project,
    is_admin,
    project_access_q,
    require_project_access,
    require_project_manager,
    require_projects_access,
)


@extend_schema(tags=["Project"])
class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all().order_by("-id")
    serializer_class = ProjectSerializer

    def get_queryset(self):
        if is_admin(self.request.user):
            return self.queryset
        return self.queryset.filter(project_access_q(self.request.user)).distinct()

    def create(self, request, *args, **kwargs):
        if not is_admin(request.user):
            raise PermissionDenied("仅管理员可以创建项目和设置项目负责人。")
        return super().create(request, *args, **kwargs)

    def perform_update(self, serializer):
        project = self.get_object()
        if not (is_admin(self.request.user) or project.pm_id == self.request.user.id):
            raise PermissionDenied("仅项目负责人可以编辑项目。")
        if not is_admin(self.request.user) and "pm" in serializer.validated_data and serializer.validated_data["pm"].id != project.pm_id:
            raise PermissionDenied("仅管理员可以修改项目负责人。")
        serializer.save()

    def perform_destroy(self, instance):
        if not is_admin(self.request.user):
            raise PermissionDenied("仅管理员可以删除项目。")
        instance.delete()

    @action(detail=True, methods=["post", "delete"], url_path="members/(?P<user_id>[^/.]+)")
    def members(self, request, pk=None, user_id=None):
        project = self.get_object()
        require_project_manager(request.user, project)
        from django.contrib.auth.models import User
        user = User.objects.filter(pk=user_id, is_active=True).first()
        if not user:
            return Response({"detail": "用户不存在或已禁用。"}, status=status.HTTP_404_NOT_FOUND)
        if request.method == "POST":
            project.user_list.add(user)
        else:
            project.user_list.remove(user)
        return Response(ProjectSerializer(project, context={"request": request}).data)


@extend_schema(tags=["Project"])
class ProjectVariableViewSet(viewsets.ModelViewSet):
    queryset = ProjectVariable.objects.select_related("project").all()
    serializer_class = ProjectVariableSerializer

    def get_queryset(self):
        queryset = self.queryset.filter(project_access_q(self.request.user, "project__")).distinct()
        project_ids = self.request.query_params.get("project")
        if project_ids:
            try:
                ids = [int(item) for item in str(project_ids).split(",") if item.strip()]
            except ValueError:
                ids = []
            queryset = queryset.filter(project_id__in=ids)
        return queryset

    def perform_create(self, serializer):
        require_project_manager(self.request.user, serializer.validated_data["project"])
        serializer.save()

    def perform_update(self, serializer):
        require_project_manager(self.request.user, self.get_object().project)
        serializer.save()

    def perform_destroy(self, instance):
        require_project_manager(self.request.user, instance.project)
        instance.delete()


@extend_schema(tags=["Project"])
class EnvironmentViewSet(viewsets.ModelViewSet):
    queryset = Environment.objects.select_related("project").all()
    serializer_class = EnvironmentSerializer

    def get_queryset(self):
        return self.queryset.filter(project_access_q(self.request.user, "project__")).distinct()

    def perform_create(self, serializer):
        require_project_access(self.request.user, serializer.validated_data["project"])
        serializer.save()

    def perform_update(self, serializer):
        environment = self.get_object()
        require_project_access(self.request.user, environment.project)
        target_project = serializer.validated_data.get("project", environment.project)
        require_project_access(self.request.user, target_project)
        serializer.save()

    @staticmethod
    def _masked_token(token):
        token = str(token or "")
        if not token:
            return ""
        if len(token) <= 16:
            return "*" * len(token)
        return f"{token[:10]}...{token[-4:]}"

    def _auth_status(self, environment):
        now = timezone.now()
        expires_at = environment.token_expires_at
        valid = environment._cached_token_valid()
        remaining_seconds = max(0, int((expires_at - now).total_seconds())) if valid and expires_at else 0
        return {
            "auth_enabled": environment.auth_enabled,
            "cached": bool(environment.cached_token),
            "valid": valid,
            "masked_token": self._masked_token(environment.cached_token),
            "token_refreshed_at": environment.token_refreshed_at,
            "token_expires_at": expires_at,
            "remaining_seconds": remaining_seconds,
        }

    def _refresh_token(self, environment):
        if not environment.auth_enabled:
            raise ValueError("请先启用自动登录。")
        token = environment._login_and_extract_token()
        refreshed_at = timezone.now()
        expires_at = environment._token_expire_time(refreshed_at)
        Environment.objects.filter(pk=environment.pk).update(
            cached_token=token,
            token_refreshed_at=refreshed_at,
            token_expires_at=expires_at,
        )
        environment.cached_token = token
        environment.token_refreshed_at = refreshed_at
        environment.token_expires_at = expires_at
        return self._auth_status(environment)

    @action(detail=True, methods=["get"], url_path="auth-status")
    def auth_status(self, request, pk=None):
        return Response(self._auth_status(self.get_object()))

    @action(detail=True, methods=["get"], url_path="token-value")
    def token_value(self, request, pk=None):
        environment = self.get_object()
        if not environment.cached_token:
            return Response({"detail": "当前环境没有可复制的 Token 缓存。"}, status=status.HTTP_404_NOT_FOUND)
        response = Response({"token": environment.cached_token})
        response["Cache-Control"] = "no-store"
        return response

    @action(detail=True, methods=["post"], url_path="refresh-token")
    def refresh_token(self, request, pk=None):
        environment = self.get_object()
        try:
            return Response(self._refresh_token(environment))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], url_path="clear-token")
    def clear_token(self, request, pk=None):
        environment = self.get_object()
        Environment.objects.filter(pk=environment.pk).update(
            cached_token="", token_refreshed_at=None, token_expires_at=None,
        )
        environment.cached_token = ""
        environment.token_refreshed_at = None
        environment.token_expires_at = None
        return Response(self._auth_status(environment))

    @action(detail=True, methods=["post"], url_path="validate-auth")
    def validate_auth(self, request, pk=None):
        environment = self.get_object()
        started_at = perf_counter()
        try:
            if environment.auth_enabled:
                auth_status = self._refresh_token(environment)
                detail = "登录接口响应成功，Token 提取成功"
            else:
                # 未启用认证时只验证基础服务是否可访问；任意 HTTP 响应均代表服务已建立连接。
                requests.get(environment.base_url, timeout=10)
                auth_status = self._auth_status(environment)
                detail = "基础服务连接成功，当前未启用自动认证"
            return Response({
                "connected": True,
                "detail": detail,
                "elapsed_ms": max(1, round((perf_counter() - started_at) * 1000)),
                **auth_status,
            })
        except (requests.RequestException, ValueError) as exc:
            return Response({
                "connected": False,
                "detail": str(exc),
                "elapsed_ms": max(1, round((perf_counter() - started_at) * 1000)),
            }, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=["Project"])
class DynamicFunctionViewSet(viewsets.ModelViewSet):
    queryset = DynamicFunction.objects.prefetch_related("projects").all()
    serializer_class = DynamicFunctionSerializer

    def get_queryset(self):
        queryset = self.queryset.filter(
            project_access_q(self.request.user, "projects__")
        ).distinct()
        project_ids = self.request.query_params.get("projects") or self.request.query_params.get("project")
        if project_ids:
            try:
                ids = [int(item) for item in str(project_ids).split(",") if item.strip()]
            except ValueError:
                ids = []
            queryset = queryset.filter(projects__id__in=ids).distinct()
        return queryset

    def perform_create(self, serializer):
        require_projects_access(self.request.user, serializer.validated_data["projects"])
        serializer.save()

    def perform_update(self, serializer):
        instance = self.get_object()
        require_projects_access(self.request.user, instance.projects.all())
        projects = serializer.validated_data.get("projects", instance.projects.all())
        require_projects_access(self.request.user, projects)
        serializer.save()

    def perform_destroy(self, instance):
        require_projects_access(self.request.user, instance.projects.all())
        instance.delete()

    @action(detail=False, methods=["post"], url_path="check-conflicts")
    def check_conflicts(self, request):
        try:
            project_ids = [int(item) for item in request.data.get("projects", [])]
        except (TypeError, ValueError):
            project_ids = []
        projects = list(Project.objects.filter(pk__in=project_ids))
        if len(projects) != len(set(project_ids)):
            return Response({"detail": "存在无效的项目。"}, status=status.HTTP_400_BAD_REQUEST)
        require_projects_access(request.user, projects)
        serializer = self.get_serializer()
        conflicts = serializer.get_conflicts(
            projects,
            str(request.data.get("code") or ""),
            request.data.get("exclude_id"),
        )
        return Response({"conflicts": conflicts})

    @action(detail=False, methods=["get"])
    def whitelist(self, request):
        return Response(whitelist())

    @action(detail=False, methods=["post"])
    def test(self, request):
        code = str(request.data.get("code") or "")
        function_name = str(request.data.get("function_name") or "")
        arguments = str(request.data.get("arguments") or "")
        try:
            validate_dynamic_code(code)
            names = function_names(code)
            if not function_name:
                return Response({"functions": names})
            if function_name not in names:
                return Response({"detail": "请选择当前代码中定义的函数。", "functions": names}, status=status.HTTP_400_BAD_REQUEST)
            args, kwargs = parse_dynamic_arguments(arguments)
            result = execute_dynamic_function([code], function_name, args=args, kwargs=kwargs)
            return Response({"function_name": function_name, "functions": names, "result": result, "display": str(result)})
        except Exception as exc:
            return Response({"detail": f"函数调试失败：{exc}", "functions": function_names(code)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=["Project"])
class DatabaseConnectionViewSet(viewsets.ModelViewSet):
    queryset = DatabaseConnection.objects.prefetch_related("projects").all()
    serializer_class = DatabaseConnectionSerializer

    def get_queryset(self):
        return self.queryset.filter(project_access_q(self.request.user, "projects__")).distinct()

    def perform_create(self, serializer):
        require_projects_access(self.request.user, serializer.validated_data["projects"])
        serializer.save()

    def perform_update(self, serializer):
        instance = self.get_object()
        require_projects_access(self.request.user, instance.projects.all())
        projects = serializer.validated_data.get("projects", instance.projects.all())
        require_projects_access(self.request.user, projects)
        serializer.save()

    def perform_destroy(self, instance):
        require_projects_access(self.request.user, instance.projects.all())
        instance.delete()

    @action(detail=False, methods=["post"], url_path="test-connection")
    def test_connection(self, request):
        record_id = request.data.get("id")
        existing = self.get_queryset().filter(pk=record_id).first() if record_id else None
        serializer = self.get_serializer(instance=existing, data=request.data)
        serializer.is_valid(raise_exception=True)
        require_projects_access(self.request.user, serializer.validated_data["projects"])
        password = serializer.validated_data.get("password") or ""
        if not password and record_id:
            password = existing.password if existing else ""
        try:
            elapsed = test_database_connection(serializer.validated_data, password)
            return Response({"connected": True, "elapsed_ms": elapsed})
        except Exception as exc:
            return Response({"detail": f"连接失败：{exc}"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"], url_path="test-sql")
    def test_sql(self, request):
        record_id = request.data.get("id")
        existing = self.get_queryset().filter(pk=record_id).first() if record_id else None
        serializer = self.get_serializer(instance=existing, data=request.data)
        serializer.is_valid(raise_exception=True)
        require_projects_access(self.request.user, serializer.validated_data["projects"])
        password = serializer.validated_data.get("password") or (existing.password if existing else "")
        sql = str(request.data.get("sql") or "").strip()
        if not sql:
            return Response({"detail": "请输入需要校验的 SQL。"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            return Response(test_database_query(
                serializer.validated_data, password, sql,
                confirm_write=bool(request.data.get("confirm_write")),
            ))
        except Exception as exc:
            return Response({"detail": f"SQL 校验失败：{exc}"}, status=status.HTTP_400_BAD_REQUEST)
