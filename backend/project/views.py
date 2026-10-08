from time import perf_counter

import requests
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from account.permissions import IsPlatformAdmin
from account.models import Tenant, TenantMembership
from account.tenancy import get_request_tenant, validate_tenant_relations

from .models import DatabaseConnection, DynamicFunction, DynamicFunctionRevision, Environment, Module, Project, ProjectVariable
from .serializers import DatabaseConnectionSerializer, DynamicFunctionSerializer, EnvironmentSerializer, ModuleSerializer, ProjectSerializer, ProjectVariableSerializer
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
        tenant = get_request_tenant(self.request)
        queryset = self.queryset.filter(tenant=tenant)
        if is_admin(self.request.user):
            return queryset
        return queryset.filter(project_access_q(self.request.user)).distinct()

    def create(self, request, *args, **kwargs):
        if not is_admin(request.user):
            raise PermissionDenied("仅管理员可以创建项目和设置项目负责人。")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(tenant=get_request_tenant(self.request))

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
        if not TenantMembership.objects.filter(
            tenant=project.tenant,
            user=user,
            status=TenantMembership.Status.ACTIVE,
        ).exists():
            return Response({"detail": "该用户不属于当前租户。"}, status=status.HTTP_400_BAD_REQUEST)
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
class ModuleViewSet(viewsets.ModelViewSet):
    """项目下的共享目录。

    接口管理、UI 元素管理、App 元素管理读写的是同一套目录数据，所以这里不按
    调用方区分，只按项目过滤：在任意一个页面新建/重命名，另外两个页面立即生效。
    """

    queryset = Module.objects.select_related("project", "created_by").all()
    serializer_class = ModuleSerializer

    def get_queryset(self):
        queryset = self.queryset.filter(
            project__tenant=get_request_tenant(self.request),
        ).filter(project_access_q(self.request.user, "project__")).distinct()
        project_id = self.request.query_params.get("project")
        return queryset.filter(project_id=project_id) if project_id else queryset

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        require_project_access(self.request.user, project)
        validate_tenant_relations(self.request, project=project)
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        module = self.get_object()
        project = serializer.validated_data.get("project", module.project)
        require_project_access(self.request.user, project)
        validate_tenant_relations(self.request, project=project)
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        """删除目录。

        目录被三个模块共用，删除会同时影响三处，所以调用方必须明确说明关联资产
        怎么处理：默认只删目录，接口/UI 元素/App 元素一律移到「未分组」；显式传
        ``cascade=true`` 才连同目录下的资产一起删除。
        """
        module = self.get_object()
        require_project_access(request.user, module.project)
        cascade = str(request.query_params.get("cascade", "false")).lower() in {"1", "true", "yes"}
        counts = {
            "endpoint_count": module.endpoints.count(),
            "ui_element_count": module.ui_elements.count(),
            "app_element_count": module.app_elements.count(),
        }
        with transaction.atomic():
            if cascade:
                module.endpoints.all().delete()
                module.ui_elements.all().delete()
                module.app_elements.all().delete()
            # 非级联时无需手工置空：三个外键都是 SET_NULL，Django 的删除收集器
            # 会把三处关联资产的 module 一并置为 NULL。
            module.delete()
        return Response(
            {
                "detail": "目录及其下资产已删除。" if cascade else "目录已删除，关联资产已移至未分组。",
                "cascade": cascade,
                "counts": counts,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["Project"])
class EnvironmentViewSet(viewsets.ModelViewSet):
    queryset = Environment.objects.select_related("project").all()
    serializer_class = EnvironmentSerializer

    def get_queryset(self):
        return self.queryset.filter(
            project__tenant=get_request_tenant(self.request),
        ).filter(project_access_q(self.request.user, "project__")).distinct()

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        validate_tenant_relations(self.request, project=project)
        require_project_access(self.request.user, project)
        serializer.save()

    def perform_update(self, serializer):
        environment = self.get_object()
        require_project_access(self.request.user, environment.project)
        target_project = serializer.validated_data.get("project", environment.project)
        validate_tenant_relations(self.request, project=target_project)
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
        tenant = get_request_tenant(self.request)
        queryset = self.queryset.filter(
            projects__tenant=tenant,
        ).exclude(
            projects__tenant__in=Tenant.objects.exclude(pk=tenant.pk),
        ).filter(
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
        projects = list(serializer.validated_data["projects"])
        validate_tenant_relations(self.request, projects=projects)
        require_projects_access(self.request.user, projects)
        serializer.save(created_by=self.request.user, approval_status=DynamicFunction.ApprovalStatus.DRAFT)

    def perform_update(self, serializer):
        instance = self.get_object()
        require_projects_access(self.request.user, instance.projects.all())
        projects = list(serializer.validated_data.get("projects", instance.projects.all()))
        validate_tenant_relations(self.request, projects=projects)
        require_projects_access(self.request.user, projects)
        serializer.save()

    def perform_destroy(self, instance):
        require_projects_access(self.request.user, instance.projects.all())
        instance.delete()

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsPlatformAdmin])
    def approve(self, request, pk=None):
        instance = self.get_object()
        with transaction.atomic():
            instance.approval_status = DynamicFunction.ApprovalStatus.APPROVED
            instance.approved_by = request.user
            instance.approved_at = timezone.now()
            instance.save(update_fields=["approval_status", "approved_by", "approved_at", "code_hash", "updated_at"])
            # 已审批版本是审计证据，重复点击审批不得覆盖原快照。
            DynamicFunctionRevision.objects.get_or_create(
                dynamic_function=instance, version=instance.version,
                defaults={"code": instance.code, "code_hash": instance.code_hash, "project_ids": list(instance.projects.values_list("id", flat=True)), "timeout_seconds": instance.timeout_seconds, "memory_mb": instance.memory_mb, "approved_by": request.user},
            )
        return Response(self.get_serializer(instance).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsPlatformAdmin])
    def reject(self, request, pk=None):
        instance = self.get_object()
        instance.approval_status = DynamicFunction.ApprovalStatus.REJECTED
        instance.approved_by = None
        instance.approved_at = None
        instance.save(update_fields=["approval_status", "approved_by", "approved_at", "code_hash", "updated_at"])
        return Response(self.get_serializer(instance).data)

    @action(detail=False, methods=["post"], url_path="check-conflicts")
    def check_conflicts(self, request):
        try:
            project_ids = [int(item) for item in request.data.get("projects", [])]
        except (TypeError, ValueError):
            project_ids = []
        projects = list(Project.objects.filter(
            pk__in=project_ids,
            tenant=get_request_tenant(request),
        ))
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
            result = execute_dynamic_function(
                [code], function_name, args=args, kwargs=kwargs,
                timeout_seconds=request.data.get("timeout_seconds"), memory_mb=request.data.get("memory_mb"),
            )
            return Response({"function_name": function_name, "functions": names, "result": result, "display": str(result)})
        except Exception as exc:
            return Response({"detail": f"函数调试失败：{exc}", "functions": function_names(code)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=["Project"])
class DatabaseConnectionViewSet(viewsets.ModelViewSet):
    queryset = DatabaseConnection.objects.prefetch_related("projects").all()
    serializer_class = DatabaseConnectionSerializer

    def get_queryset(self):
        tenant = get_request_tenant(self.request)
        return self.queryset.filter(
            projects__tenant=tenant,
        ).exclude(
            projects__tenant__in=Tenant.objects.exclude(pk=tenant.pk),
        ).filter(project_access_q(self.request.user, "projects__")).distinct()

    def perform_create(self, serializer):
        projects = list(serializer.validated_data["projects"])
        validate_tenant_relations(self.request, projects=projects)
        require_projects_access(self.request.user, projects)
        serializer.save()

    def perform_update(self, serializer):
        instance = self.get_object()
        require_projects_access(self.request.user, instance.projects.all())
        projects = list(serializer.validated_data.get("projects", instance.projects.all()))
        validate_tenant_relations(self.request, projects=projects)
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
        if record_id and existing and not serializer.validated_data.get("ssh_private_key_passphrase"):
            serializer.validated_data["ssh_private_key_passphrase"] = existing.ssh_private_key_passphrase
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
        if record_id and existing and not serializer.validated_data.get("ssh_private_key_passphrase"):
            serializer.validated_data["ssh_private_key_passphrase"] = existing.ssh_private_key_passphrase
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
