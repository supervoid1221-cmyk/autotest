from django.conf import settings
from django.db import models

from Tesla.model_fields import EncryptedTextField
from account.models import get_default_tenant_id


class ServerConnection(models.Model):
    """SSH 服务器连接，由系统管理员或所属项目负责人维护。"""

    class AuthType(models.TextChoices):
        PRIVATE_KEY = "private_key", "私钥认证"
        PASSWORD = "password", "密码认证"

    tenant = models.ForeignKey(
        "account.Tenant",
        on_delete=models.PROTECT,
        related_name="server_connections",
        default=get_default_tenant_id,
        editable=False,
        verbose_name="所属租户",
    )
    name = models.CharField("连接名称", max_length=64)
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
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"], name="unique_tenant_server_connection_name",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "project"], name="server_tenant_project_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.username}@{self.host}:{self.port})"


class SystemConfiguration(models.Model):
    """平台级单例配置，仅系统管理员可维护。"""

    report_retention_days = models.PositiveSmallIntegerField("执行报告保留天数", default=15)
    max_worker_count = models.PositiveSmallIntegerField(
        "最大 Worker 数", default=2,
        help_text="API、UI 和 App 任务共用的平台最大并发 Worker 数。",
    )
    max_performance_worker_count = models.PositiveSmallIntegerField(
        "最大性能 Worker 数", default=1,
        help_text="性能测试任务可同时启动的 k6 工作进程数。",
    )
    platform_icon = models.FileField(
        "浅色背景 Logo", upload_to="system/branding/", blank=True, null=True,
    )
    platform_icon_dark = models.FileField(
        "深色背景 Logo", upload_to="system/branding/", blank=True, null=True,
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_system_configurations",
        verbose_name="更新人",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        verbose_name = "系统配置"
        verbose_name_plural = "系统配置"

    def __str__(self):
        return (
            f"系统配置（Worker {self.max_worker_count}，"
            f"性能 Worker {self.max_performance_worker_count}，"
            f"报告保留 {self.report_retention_days} 天）"
        )
