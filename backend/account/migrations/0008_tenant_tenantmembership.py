import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


DEFAULT_TENANT_SLUG = "default"


def create_default_tenant_and_memberships(apps, schema_editor):
    Tenant = apps.get_model("account", "Tenant")
    TenantMembership = apps.get_model("account", "TenantMembership")
    User = apps.get_model("auth", "User")

    tenant, _ = Tenant.objects.get_or_create(
        slug=DEFAULT_TENANT_SLUG,
        defaults={"name": "默认租户", "status": "active"},
    )
    memberships = [
        TenantMembership(
            tenant_id=tenant.id,
            user_id=user.id,
            role="owner" if user.is_superuser or user.is_staff else "member",
            status="active",
        )
        for user in User.objects.all().iterator()
    ]
    TenantMembership.objects.bulk_create(memberships, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0007_remove_profile_name"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Tenant",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=64, verbose_name="租户名称")),
                ("slug", models.SlugField(max_length=64, unique=True, verbose_name="租户编码")),
                ("status", models.CharField(choices=[("active", "正常"), ("suspended", "已停用")], db_index=True, default="active", max_length=16, verbose_name="状态")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["created_at", "name"]},
        ),
        migrations.CreateModel(
            name="TenantMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("owner", "租户所有者"), ("admin", "租户管理员"), ("member", "成员"), ("viewer", "只读成员")], default="member", max_length=16, verbose_name="租户角色")),
                ("status", models.CharField(choices=[("active", "正常"), ("disabled", "已停用")], db_index=True, default="active", max_length=16, verbose_name="状态")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("tenant", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="account.tenant")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tenant_memberships", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["tenant_id", "user_id"],
                "indexes": [models.Index(fields=["user", "status"], name="tenant_member_user_status_idx")],
                "constraints": [models.UniqueConstraint(fields=("tenant", "user"), name="unique_tenant_user_membership")],
            },
        ),
        migrations.RunPython(create_default_tenant_and_memberships, migrations.RunPython.noop),
    ]
