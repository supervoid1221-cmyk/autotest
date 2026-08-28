from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("project", "0009_databaseconnection"),
    ]

    operations = [
        migrations.AddField(
            model_name="databaseconnection",
            name="ssl_mode",
            field=models.CharField(
                choices=[
                    ("preferred", "优先使用 TLS"),
                    ("required", "强制使用 TLS"),
                    ("disabled", "关闭 TLS"),
                ],
                default="preferred",
                max_length=16,
                verbose_name="TLS 模式",
            ),
        ),
    ]
