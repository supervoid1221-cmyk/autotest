from django.db import migrations

import Tesla.model_fields


def encrypt_existing_values(apps, schema_editor):
    for model_name in ("UiStep", "PlaywrightStep"):
        model = apps.get_model("case_ui", model_name)
        for instance in model.objects.all().iterator(chunk_size=100):
            model.objects.filter(pk=instance.pk).update(
                value=instance.value,
                options=instance.options,
            )


class Migration(migrations.Migration):
    dependencies = [("case_ui", "0014_remove_uistep_name")]

    operations = [
        migrations.AlterField(
            model_name="uistep", name="value",
            field=Tesla.model_fields.EncryptedTextField(blank=True, verbose_name="操作值"),
        ),
        migrations.AlterField(
            model_name="uistep", name="options",
            field=Tesla.model_fields.EncryptedJSONField(blank=True, default=dict, verbose_name="扩展配置"),
        ),
        migrations.AlterField(
            model_name="playwrightstep", name="value",
            field=Tesla.model_fields.EncryptedTextField(blank=True, default="", verbose_name="操作值"),
        ),
        migrations.AlterField(
            model_name="playwrightstep", name="options",
            field=Tesla.model_fields.EncryptedJSONField(blank=True, default=dict, verbose_name="扩展配置"),
        ),
        migrations.RunPython(encrypt_existing_values, migrations.RunPython.noop),
    ]
