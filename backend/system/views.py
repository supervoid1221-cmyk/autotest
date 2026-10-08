import os
import time
import mimetypes
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.http import FileResponse, Http404

from account.access import is_system_admin
from account.tenancy import get_request_tenant, validate_tenant_relations
from Tesla.ssh import configured_ssh_client, ssh_connection_options
from account.permissions import IsPlatformAdmin
from project.access import require_project_manager
from project.models import Project
from .models import ServerConnection, SystemConfiguration
from .serializers import ServerConnectionSerializer, SystemConfigurationSerializer


def _test_ssh_connection(connection):
    """只验证 SSH 连通与身份认证，不执行远程业务命令。"""
    try:
        import paramiko
    except ImportError as exc:
        raise ValueError("服务端未安装 Paramiko，无法测试 SSH 连接。") from exc
    client = configured_ssh_client(paramiko, connection.strict_host_key)
    options = ssh_connection_options(connection.host, connection.port, connection.username, 10)
    if connection.auth_type == ServerConnection.AuthType.PRIVATE_KEY:
        key_path = Path(os.path.expanduser(connection.private_key_path))
        if not key_path.is_file():
            raise ValueError(f"私钥文件不存在或不可访问：{key_path}")
        options.update({"key_filename": str(key_path), "passphrase": connection.private_key_passphrase or None})
    else:
        options["password"] = connection.password
    started = time.perf_counter()
    try:
        client.connect(**options)
        if not client.get_transport() or not client.get_transport().is_active():
            raise ConnectionError("SSH 已建立但连接不可用。")
        return max(1, round((time.perf_counter() - started) * 1000))
    finally:
        client.close()


class CanMaintainServerConnections(BasePermission):
    message = "仅系统管理员或项目负责人可以维护服务器配置。"

    def has_permission(self, request, view):
        return bool(
            is_system_admin(request.user)
            or Project.objects.filter(pm=request.user).exists()
        )


class ServerConnectionViewSet(viewsets.ModelViewSet):
    """SSH 服务器连接，系统管理员管理全部，项目负责人管理所负责项目。"""
    queryset = ServerConnection.objects.select_related("created_by", "project").all()
    serializer_class = ServerConnectionSerializer
    permission_classes = [CanMaintainServerConnections]

    def get_queryset(self):
        queryset = self.queryset.filter(tenant=get_request_tenant(self.request))
        if not is_system_admin(self.request.user):
            queryset = queryset.filter(project__pm=self.request.user)
        project = self.request.query_params.get("project")
        if project:
            queryset = queryset.filter(project_id=project)
        return queryset

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        validate_tenant_relations(self.request, project=project)
        require_project_manager(self.request.user, project)
        serializer.save(tenant=get_request_tenant(self.request), created_by=self.request.user)

    def perform_update(self, serializer):
        connection = self.get_object()
        require_project_manager(self.request.user, connection.project)
        target_project = serializer.validated_data.get("project", connection.project)
        validate_tenant_relations(self.request, project=target_project)
        require_project_manager(self.request.user, target_project)
        serializer.save()

    def perform_destroy(self, instance):
        require_project_manager(self.request.user, instance.project)
        instance.delete()

    @action(detail=False, methods=["post"], url_path="test-connection-draft")
    def test_connection_draft(self, request):
        """使用当前表单参数测试 SSH，不创建或更新服务器连接记录。"""
        payload = request.data.copy()
        connection_id = payload.pop("id", None)
        instance = None
        if connection_id:
            try:
                instance = self.get_queryset().get(pk=connection_id)
            except ServerConnection.DoesNotExist:
                return Response({"detail": "服务器连接不存在。"}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(instance=instance, data=payload)
        serializer.is_valid(raise_exception=True)
        project = serializer.validated_data["project"]
        validate_tenant_relations(request, project=project)
        require_project_manager(request.user, project)
        if instance:
            # 保留已保存但本次未重新输入的敏感认证信息，仅在内存中覆盖本次编辑值。
            connection = ServerConnection()
            for field in ServerConnection._meta.fields:
                setattr(connection, field.attname, getattr(instance, field.attname))
            for field, value in serializer.validated_data.items():
                setattr(connection, field, value)
        else:
            connection = ServerConnection(**serializer.validated_data)

        try:
            elapsed_ms = _test_ssh_connection(connection)
        except Exception as exc:
            return Response({"detail": f"连接失败：{exc}"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"connected": True, "elapsed_ms": elapsed_ms})

    @action(detail=True, methods=["post"], url_path="test-connection")
    def test_connection(self, request, pk=None):
        connection = self.get_object()
        try:
            elapsed_ms = _test_ssh_connection(connection)
        except Exception as exc:
            message = str(exc)
            connection.last_tested_at = timezone.now()
            connection.last_test_status = False
            connection.last_test_message = message[:512]
            connection.save(update_fields=["last_tested_at", "last_test_status", "last_test_message", "updated_at"])
            return Response({"detail": f"连接失败：{message}"}, status=status.HTTP_400_BAD_REQUEST)
        connection.last_tested_at = timezone.now()
        connection.last_test_status = True
        connection.last_test_message = f"SSH 连接成功，耗时 {elapsed_ms} ms"
        connection.save(update_fields=["last_tested_at", "last_test_status", "last_test_message", "updated_at"])
        return Response({"connected": True, "elapsed_ms": elapsed_ms})


class SystemConfigurationView(APIView):
    """读取和更新平台级系统配置。"""

    permission_classes = [IsPlatformAdmin]

    @staticmethod
    def _get_configuration():
        configuration, _ = SystemConfiguration.objects.get_or_create(
            pk=1,
            defaults={
                "report_retention_days": settings.FILE_RETENTION_DAYS,
                "max_worker_count": max(1, int(settings.Q_CLUSTER.get("workers", 2))),
                "max_performance_worker_count": 1,
            },
        )
        return configuration

    def get(self, request):
        return Response(SystemConfigurationSerializer(self._get_configuration(), context={"request": request}).data)

    def put(self, request):
        configuration = self._get_configuration()
        serializer = SystemConfigurationSerializer(configuration, data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)


class BrandingConfigurationView(APIView):
    """登录前后均可读取的非敏感平台品牌配置。"""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        configuration = SystemConfigurationView._get_configuration()
        serializer = SystemConfigurationSerializer(configuration, context={"request": request})
        return Response({
            "platform_logo_light_url": serializer.data["platform_logo_light_url"],
            "platform_logo_dark_url": serializer.data["platform_logo_dark_url"],
            "favicon_url": serializer.data["favicon_url"],
            "updated_at": serializer.data["updated_at"],
        })


class BrandingAssetView(APIView):
    """输出已配置的品牌图片，避免依赖部署环境的媒体目录映射。"""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, kind):
        if kind not in {"platform_icon", "platform_icon_dark", "favicon"}:
            raise Http404
        configuration = SystemConfigurationView._get_configuration()
        image = (
            configuration.platform_icon_dark
            if kind == "platform_icon_dark"
            else configuration.platform_icon
        )
        if not image:
            raise Http404
        content_type = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
        response = FileResponse(image.open("rb"), content_type=content_type)
        response["Cache-Control"] = "no-cache"
        return response
