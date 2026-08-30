import os
import time
from pathlib import Path

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from account.access import is_system_admin
from project.access import require_project_manager
from project.models import Project
from .models import ServerConnection
from .serializers import ServerConnectionSerializer


def _test_ssh_connection(connection):
    """只验证 SSH 连通与身份认证，不执行远程业务命令。"""
    try:
        import paramiko
    except ImportError as exc:
        raise ValueError("服务端未安装 Paramiko，无法测试 SSH 连接。") from exc
    client = paramiko.SSHClient()
    if connection.strict_host_key:
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.RejectPolicy())
    else:
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    options = {
        "hostname": connection.host, "port": connection.port, "username": connection.username,
        "timeout": 10, "banner_timeout": 10, "auth_timeout": 10,
        "look_for_keys": False, "allow_agent": False,
    }
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
        queryset = self.queryset.all()
        if not is_system_admin(self.request.user):
            queryset = queryset.filter(project__pm=self.request.user)
        project = self.request.query_params.get("project")
        if project:
            queryset = queryset.filter(project_id=project)
        return queryset

    def perform_create(self, serializer):
        require_project_manager(self.request.user, serializer.validated_data["project"])
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        connection = self.get_object()
        require_project_manager(self.request.user, connection.project)
        target_project = serializer.validated_data.get("project", connection.project)
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
        require_project_manager(request.user, serializer.validated_data["project"])
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
