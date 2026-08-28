from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("suite", "0015_runresult_random_numeric_primary_key")]
    operations = [
        migrations.CreateModel(name="NotificationChannel", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("name", models.CharField(max_length=64, verbose_name="渠道名称")),
            ("platform", models.CharField(choices=[("lark", "飞书"), ("wecom", "企业微信")], max_length=16, verbose_name="平台")), ("webhook_url", models.URLField(max_length=1024, verbose_name="Webhook 地址")), ("enabled", models.BooleanField(default=True, verbose_name="启用")), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notification_channels", to="project.project")),
        ]),
        migrations.CreateModel(name="NotificationRule", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("event", models.CharField(choices=[("succeeded", "执行成功"), ("failed", "执行失败")], max_length=16, verbose_name="触发事件")), ("enabled", models.BooleanField(default=True, verbose_name="启用")), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("channel", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="rules", to="suite.notificationchannel")), ("suite", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="notification_rules", to="suite.suite")),
        ]),
        migrations.CreateModel(name="NotificationDelivery", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("event", models.CharField(max_length=16, verbose_name="触发事件")), ("status", models.CharField(choices=[("sent", "已发送"), ("failed", "发送失败")], max_length=16, verbose_name="投递状态")), ("payload", models.JSONField(blank=True, default=dict, verbose_name="消息内容")), ("response_code", models.IntegerField(blank=True, null=True, verbose_name="响应码")), ("response_summary", models.CharField(blank=True, max_length=500, verbose_name="响应摘要")), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("channel", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="deliveries", to="suite.notificationchannel")), ("result", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notification_deliveries", to="suite.runresult")), ("rule", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="deliveries", to="suite.notificationrule")),
        ]),
    ]
