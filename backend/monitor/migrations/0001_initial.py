from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("project", "0001_initial"),
        ("system", "0003_initial"),
    ]
    operations = [
        migrations.CreateModel(
            name="PrometheusInstance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=64, unique=True, verbose_name="名称")),
                ("base_url", models.URLField(max_length=256, verbose_name="访问地址")),
                ("access_token", models.TextField(blank=True, default="", verbose_name="访问令牌")),
                ("enabled", models.BooleanField(default=True, verbose_name="启用")),
                ("description", models.CharField(blank=True, default="", max_length=256, verbose_name="备注")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_prometheus_instances", to=settings.AUTH_USER_MODEL)),
            ], options={"ordering": ["-id"]},
        ),
        migrations.CreateModel(
            name="MonitorTarget",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=96, verbose_name="目标名称")), ("job", models.CharField(default="node", max_length=128, verbose_name="Prometheus Job")),
                ("instance_label", models.CharField(help_text="如 10.0.0.12:9100", max_length=256, verbose_name="Instance 标签")),
                ("extra_labels", models.JSONField(blank=True, default=dict, verbose_name="附加标签")), ("enabled", models.BooleanField(default=True, verbose_name="启用监控")),
                ("cpu_warning_threshold", models.FloatField(default=80, verbose_name="CPU 预警阈值")), ("cpu_critical_threshold", models.FloatField(default=90, verbose_name="CPU 告警阈值")),
                ("memory_warning_threshold", models.FloatField(default=85, verbose_name="内存预警阈值")), ("memory_critical_threshold", models.FloatField(default=95, verbose_name="内存告警阈值")),
                ("disk_warning_threshold", models.FloatField(default=80, verbose_name="磁盘预警阈值")), ("disk_critical_threshold", models.FloatField(default=90, verbose_name="磁盘告警阈值")),
                ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_monitor_targets", to=settings.AUTH_USER_MODEL)),
                ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="monitor_targets", to="project.project")),
                ("prometheus", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="targets", to="monitor.prometheusinstance")),
                ("server", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="monitor_targets", to="system.serverconnection")),
            ], options={"ordering": ["-id"]},
        ),
        migrations.AddConstraint(model_name="monitortarget", constraint=models.UniqueConstraint(fields=("prometheus", "instance_label"), name="unique_prometheus_monitor_target")),
        migrations.CreateModel(
            name="MonitorAlertEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("alert_key", models.CharField(max_length=32, verbose_name="规则标识")),
                ("severity", models.CharField(choices=[("warning", "预警"), ("critical", "告警")], max_length=16, verbose_name="严重程度")),
                ("status", models.CharField(choices=[("active", "告警中"), ("recovered", "已恢复")], default="active", max_length=16, verbose_name="状态")),
                ("metric_value", models.FloatField(blank=True, null=True, verbose_name="指标值")), ("threshold", models.FloatField(blank=True, null=True, verbose_name="阈值")),
                ("message", models.CharField(max_length=256, verbose_name="告警内容")), ("started_at", models.DateTimeField(auto_now_add=True)), ("recovered_at", models.DateTimeField(blank=True, null=True)),
                ("target", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="alert_events", to="monitor.monitortarget")),
            ], options={"ordering": ["-id"]},
        ),
    ]
