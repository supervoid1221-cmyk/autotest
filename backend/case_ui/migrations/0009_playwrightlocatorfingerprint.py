# Generated manually for Playwright smart locator fingerprints.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("case_ui", "0008_playwrightcase_tabs_playwrightstep_tab_key"),
    ]

    operations = [
        migrations.CreateModel(
            name="PlaywrightLocatorFingerprint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("environment_name", models.CharField(blank=True, default="", max_length=64, verbose_name="执行环境")),
                ("fingerprint", models.JSONField(default=dict, verbose_name="元素指纹")),
                ("strategy", models.CharField(max_length=64, verbose_name="最后定位策略")),
                ("success_count", models.PositiveIntegerField(default=1, verbose_name="成功次数")),
                ("last_seen_at", models.DateTimeField(auto_now=True, verbose_name="最后成功时间")),
                ("step", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="locator_fingerprints", to="case_ui.playwrightstep")),
            ],
            options={"ordering": ["-last_seen_at"]},
        ),
        migrations.AddConstraint(
            model_name="playwrightlocatorfingerprint",
            constraint=models.UniqueConstraint(fields=("step", "environment_name"), name="unique_playwright_locator_fingerprint_environment"),
        ),
    ]
