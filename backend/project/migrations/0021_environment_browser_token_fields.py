from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("project", "0020_encrypt_sensitive_fields")]

    operations = [
        migrations.AddField(
            model_name="environment", name="browser_token_enabled",
            field=models.BooleanField(default=True, verbose_name="注入浏览器 Token"),
        ),
        migrations.AddField(
            model_name="environment", name="browser_token_storage",
            field=models.CharField(
                choices=[("local_storage", "localStorage"), ("session_storage", "sessionStorage"), ("cookie", "Cookie")],
                default="local_storage", max_length=24, verbose_name="浏览器 Token 存储位置",
            ),
        ),
        migrations.AddField(
            model_name="environment", name="browser_token_key",
            field=models.CharField(blank=True, default="", max_length=128, verbose_name="浏览器 Token 存储键"),
        ),
        migrations.AddField(
            model_name="environment", name="browser_token_include_prefix",
            field=models.BooleanField(default=False, verbose_name="浏览器 Token 包含请求头前缀"),
        ),
        migrations.AddField(
            model_name="environment", name="browser_cookie_domain",
            field=models.CharField(blank=True, default="", max_length=255, verbose_name="Cookie 域"),
        ),
        migrations.AddField(
            model_name="environment", name="browser_cookie_path",
            field=models.CharField(blank=True, default="/", max_length=255, verbose_name="Cookie 路径"),
        ),
    ]
