from django.db import migrations

import Tesla.model_fields


def encrypt_existing_values(apps, schema_editor):
    model = apps.get_model("system", "ServerConnection")
    for instance in model.objects.all().iterator(chunk_size=200):
        model.objects.filter(pk=instance.pk).update(
            password=instance.password,
            private_key_passphrase=instance.private_key_passphrase,
        )


class Migration(migrations.Migration):
    dependencies = [("system", "0004_serverconnection_project")]

    operations = [
        migrations.AlterField(
            model_name="serverconnection", name="password",
            field=Tesla.model_fields.EncryptedTextField(blank=True, verbose_name="登录密码"),
        ),
        migrations.AlterField(
            model_name="serverconnection", name="private_key_passphrase",
            field=Tesla.model_fields.EncryptedTextField(blank=True, verbose_name="私钥口令"),
        ),
        migrations.RunPython(encrypt_existing_values, migrations.RunPython.noop),
    ]
