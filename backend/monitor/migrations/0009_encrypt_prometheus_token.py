from django.db import migrations

import Tesla.model_fields


def encrypt_existing_values(apps, schema_editor):
    model = apps.get_model("monitor", "PrometheusInstance")
    for instance in model.objects.all().iterator(chunk_size=200):
        model.objects.filter(pk=instance.pk).update(access_token=instance.access_token)


class Migration(migrations.Migration):
    dependencies = [("monitor", "0008_notification_rule_multi_services")]

    operations = [
        migrations.AlterField(
            model_name="prometheusinstance", name="access_token",
            field=Tesla.model_fields.EncryptedTextField(blank=True, default="", verbose_name="访问令牌"),
        ),
        migrations.RunPython(encrypt_existing_values, migrations.RunPython.noop),
    ]
