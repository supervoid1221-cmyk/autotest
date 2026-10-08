from pathlib import Path
import uuid

from django.contrib.auth.models import User
from django.db import models



# 仅供历史迁移文件加载使用；头像上传功能已移除。
def user_head_img_path(obj, filename):
    return f"account/static/user_{obj.user.id}/{filename}"

class Profile(models.Model):
    """账户扩展资料。昵称、头像等个人展示字段已移除。"""

    objects: models.QuerySet

    user = models.OneToOneField(User, on_delete=models.CASCADE)


class Tenant(models.Model):
    """平台租户。

    用户仍作为全局登录身份，通过 TenantMembership 加入一个或多个租户。
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "正常"
        SUSPENDED = "suspended", "已停用"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField("租户名称", max_length=64)
    slug = models.SlugField("租户编码", max_length=64, unique=True)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    max_regular_concurrent_executions = models.PositiveSmallIntegerField(
        "普通任务最大并发数", default=2,
    )
    max_performance_concurrent_executions = models.PositiveSmallIntegerField(
        "性能任务最大并发数", default=1,
    )
    storage_quota_bytes = models.PositiveBigIntegerField("存储配额（字节）", default=10 * 1024 * 1024 * 1024)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "name"]

    def __str__(self):
        return self.name


def get_default_tenant_id():
    """为尚未显式传入租户的内部任务和旧代码提供过渡默认值。"""

    tenant, _ = Tenant.objects.get_or_create(
        slug="default",
        defaults={"name": "默认租户", "status": Tenant.Status.ACTIVE},
    )
    return tenant.pk


class TenantMembership(models.Model):
    """用户在租户内的身份和角色。"""

    class Role(models.TextChoices):
        OWNER = "owner", "租户所有者"
        ADMIN = "admin", "租户管理员"
        MEMBER = "member", "成员"
        VIEWER = "viewer", "只读成员"

    class Status(models.TextChoices):
        ACTIVE = "active", "正常"
        DISABLED = "disabled", "已停用"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tenant_memberships")
    role = models.CharField("租户角色", max_length=16, choices=Role.choices, default=Role.MEMBER)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["tenant_id", "user_id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "user"], name="unique_tenant_user_membership"),
        ]
        indexes = [models.Index(fields=["user", "status"], name="tenant_member_user_status_idx")]

    def __str__(self):
        return f"{self.tenant.name} / {self.user.username}"

