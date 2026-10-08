import account.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import Tesla.model_fields


class Migration(migrations.Migration):
    dependencies = [
        ("case_ui", "0018_shared_module"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PlaywrightScenarioFile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("filename", models.CharField(max_length=128, verbose_name="文件名")),
                ("content", Tesla.model_fields.EncryptedTextField(verbose_name="场景原文")),
                ("environment_name", models.CharField(blank=True, default="", max_length=64, verbose_name="执行环境")),
                ("browser", models.CharField(default="chromium", max_length=16, verbose_name="浏览器")),
                ("run_mode", models.CharField(default="headless", max_length=16, verbose_name="运行模式")),
                ("create_datetime", models.DateTimeField(auto_now_add=True)),
                ("update_datetime", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_playwright_scenario_files", to=settings.AUTH_USER_MODEL)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="playwright_scenario_files", to="project.project")),
                ("tenant", models.ForeignKey(default=account.models.get_default_tenant_id, editable=False, on_delete=django.db.models.deletion.PROTECT, related_name="playwright_scenario_files", to="account.tenant")),
            ],
            options={
                "ordering": ["-id"],
                "constraints": [models.UniqueConstraint(fields=("project", "filename"), name="unique_playwright_scenario_filename")],
            },
        ),
    ]
