from django.db import migrations

import Tesla.model_fields


def encrypt_existing_values(apps, schema_editor):
    field_map = {
        "ProjectVariable": ("value",),
        "Environment": ("login_headers", "login_params", "login_data", "login_json", "cached_token"),
        "DatabaseConnection": ("password", "ssh_private_key_passphrase"),
    }
    for model_name, field_names in field_map.items():
        model = apps.get_model("project", model_name)
        for instance in model.objects.all().iterator(chunk_size=200):
            values = {field: getattr(instance, field) for field in field_names}
            model.objects.filter(pk=instance.pk).update(**values)


class Migration(migrations.Migration):
    dependencies = [("project", "0019_databaseconnection_ssh_host_and_more")]

    operations = [
        migrations.AlterField(
            model_name="projectvariable", name="value",
            field=Tesla.model_fields.EncryptedTextField(blank=True, default="", verbose_name="变量值"),
        ),
        migrations.AlterField(
            model_name="environment", name="login_headers",
            field=Tesla.model_fields.EncryptedJSONField(blank=True, default=dict, verbose_name="登录请求头"),
        ),
        migrations.AlterField(
            model_name="environment", name="login_params",
            field=Tesla.model_fields.EncryptedJSONField(blank=True, default=dict, verbose_name="登录查询参数"),
        ),
        migrations.AlterField(
            model_name="environment", name="login_data",
            field=Tesla.model_fields.EncryptedJSONField(blank=True, default=dict, verbose_name="登录表单参数"),
        ),
        migrations.AlterField(
            model_name="environment", name="login_json",
            field=Tesla.model_fields.EncryptedJSONField(blank=True, default=dict, verbose_name="登录 JSON 参数"),
        ),
        migrations.AlterField(
            model_name="environment", name="cached_token",
            field=Tesla.model_fields.EncryptedTextField(blank=True, default="", verbose_name="共享 Token 缓存"),
        ),
        migrations.AlterField(
            model_name="databaseconnection", name="password",
            field=Tesla.model_fields.EncryptedTextField(blank=True, verbose_name="密码"),
        ),
        migrations.AlterField(
            model_name="databaseconnection", name="ssh_private_key_passphrase",
            field=Tesla.model_fields.EncryptedTextField(blank=True, verbose_name="SSH 私钥口令"),
        ),
        migrations.RunPython(encrypt_existing_values, migrations.RunPython.noop),
    ]
