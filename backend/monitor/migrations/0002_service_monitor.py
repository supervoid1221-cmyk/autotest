from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("monitor", "0001_initial"),
        ("project", "0001_initial"),
        ("system", "0003_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceMonitor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=96, verbose_name="服务名称")),
                ("monitor_type", models.CharField(choices=[("http", "HTTP"), ("tcp", "TCP")], default="http", max_length=16, verbose_name="监控类型")),
                ("address", models.CharField(help_text="HTTP 使用完整 URL；TCP 使用主机名或 IP", max_length=512, verbose_name="服务地址")),
                ("port", models.PositiveIntegerField(blank=True, help_text="TCP 监控必填", null=True, verbose_name="端口")),
                ("expected_status_codes", models.JSONField(blank=True, default=list, verbose_name="期望状态码")),
                ("timeout_seconds", models.PositiveIntegerField(default=5, verbose_name="超时秒数")),
                ("enabled", models.BooleanField(default=True, verbose_name="启用监控")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_service_monitors", to=settings.AUTH_USER_MODEL)),
                ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="service_monitors", to="project.project")),
                ("server", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="service_monitors", to="system.serverconnection")),
            ],
            options={"ordering": ["-id"]},
        ),
        migrations.CreateModel(
            name="ServiceMonitorEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("up", "在线"), ("down", "离线")], max_length=16, verbose_name="状态")),
                ("message", models.CharField(blank=True, max_length=512, verbose_name="检测信息")),
                ("response_time_ms", models.PositiveIntegerField(blank=True, null=True, verbose_name="响应耗时")),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                ("service", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="monitor.servicemonitor")),
            ],
            options={"ordering": ["-id"]},
        ),
    ]
