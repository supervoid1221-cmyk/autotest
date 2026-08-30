from django.conf import settings
from django.db import models

from Tesla.model_fields import EncryptedTextField


class ServerConnection(models.Model):
    """SSH 服务器连接，由系统管理员或所属项目负责人维护。"""

    class AuthType(models.TextChoices):
        PRIVATE_KEY = "private_key", "私钥认证"
        PASSWORD = "password", "密码认证"

    name = models.CharField("连接名称", max_length=64, unique=True)
    project = models.ForeignKey(
        "project.Project",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="server_connections",
        verbose_name="所属项目",
    )
    host = models.CharField("服务器地址", max_length=255)
    port = models.PositiveIntegerField("SSH 端口", default=22)
    username = models.CharField("登录账号", max_length=128)
    auth_type = models.CharField("认证方式", max_length=16, choices=AuthType.choices, default=AuthType.PRIVATE_KEY)
    private_key_path = models.CharField("服务器可访问的私钥路径", max_length=512, blank=True)
    private_key_passphrase = EncryptedTextField("私钥口令", blank=True)
    password = EncryptedTextField("登录密码", blank=True)
    strict_host_key = models.BooleanField("校验主机指纹", default=True)
    enabled = models.BooleanField("启用", default=True)
    description = models.CharField("备注", max_length=256, blank=True)
    last_tested_at = models.DateTimeField("最近测试时间", null=True, blank=True)
    last_test_status = models.BooleanField("最近测试成功", null=True, blank=True)
    last_test_message = models.CharField("最近测试信息", max_length=512, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_server_connections", verbose_name="创建人",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return f"{self.name} ({self.username}@{self.host}:{self.port})"
