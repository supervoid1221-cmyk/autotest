from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("monitor", "0002_service_monitor"),
        ("suite", "0025_webhook_replay_nonce"),
    ]

    operations = [
        migrations.CreateModel(
            name="MonitorNotificationRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event", models.CharField(choices=[("alert", "异常告警"), ("recovered", "恢复通知"), ("all", "异常和恢复")], default="alert", max_length=16, verbose_name="触发事件")),
                ("enabled", models.BooleanField(default=True, verbose_name="启用")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("channel", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="monitor_rules", to="suite.notificationchannel")),
                ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_monitor_notification_rules", to=settings.AUTH_USER_MODEL)),
                ("service", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="notification_rules", to="monitor.servicemonitor")),
                ("target", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="notification_rules", to="monitor.monitortarget")),
            ], options={"ordering": ["-id"]},
        ),
        migrations.CreateModel(
            name="MonitorNotificationDelivery",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event", models.CharField(max_length=16, verbose_name="触发事件")),
                ("status", models.CharField(choices=[("sent", "已发送"), ("failed", "发送失败")], max_length=16, verbose_name="投递状态")),
                ("payload", models.JSONField(blank=True, default=dict, verbose_name="消息内容")),
                ("response_code", models.IntegerField(blank=True, null=True, verbose_name="响应码")),
                ("response_summary", models.CharField(blank=True, max_length=500, verbose_name="响应摘要")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("channel", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="monitor_deliveries", to="suite.notificationchannel")),
                ("rule", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="deliveries", to="monitor.monitornotificationrule")),
                ("service", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="notification_deliveries", to="monitor.servicemonitor")),
                ("target", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="notification_deliveries", to="monitor.monitortarget")),
            ], options={"ordering": ["-id"]},
        ),
    ]
