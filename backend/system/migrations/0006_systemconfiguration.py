from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("system", "0005_encrypt_server_credentials"),
    ]

    operations = [
        migrations.CreateModel(
            name="SystemConfiguration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("report_retention_days", models.PositiveSmallIntegerField(default=15, verbose_name="执行报告保留天数")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="创建时间")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新时间")),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="updated_system_configurations",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="更新人",
                    ),
                ),
            ],
            options={"verbose_name": "系统配置", "verbose_name_plural": "系统配置"},
        ),
    ]
