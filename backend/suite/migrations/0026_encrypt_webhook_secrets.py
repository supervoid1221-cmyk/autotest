from django.db import migrations

import Tesla.model_fields


def encrypt_existing_values(apps, schema_editor):
    field_map = {
        "Suite": ("hook_key",),
        "NotificationChannel": ("webhook_url",),
    }
    for model_name, field_names in field_map.items():
        model = apps.get_model("suite", model_name)
        for instance in model.objects.all().iterator(chunk_size=200):
            values = {field: getattr(instance, field) for field in field_names}
            model.objects.filter(pk=instance.pk).update(**values)


class Migration(migrations.Migration):
    dependencies = [("suite", "0025_webhook_replay_nonce")]

    operations = [
        migrations.AlterField(
            model_name="suite", name="hook_key",
            field=Tesla.model_fields.EncryptedTextField(blank=True, verbose_name="hook密钥"),
        ),
        migrations.AlterField(
            model_name="notificationchannel", name="webhook_url",
            field=Tesla.model_fields.EncryptedURLField(max_length=1024, verbose_name="Webhook 地址"),
        ),
        migrations.RunPython(encrypt_existing_values, migrations.RunPython.noop),
    ]
