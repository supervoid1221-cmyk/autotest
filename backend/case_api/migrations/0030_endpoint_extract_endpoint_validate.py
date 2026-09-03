from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("case_api", "0029_encrypt_request_secrets"),
    ]

    operations = [
        migrations.AddField(
            model_name="endpoint",
            name="extract",
            field=models.JSONField(blank=True, default=dict, verbose_name="数据提取"),
        ),
        migrations.AddField(
            model_name="endpoint",
            name="validate",
            field=models.JSONField(blank=True, default=dict, verbose_name="断言"),
        ),
    ]
