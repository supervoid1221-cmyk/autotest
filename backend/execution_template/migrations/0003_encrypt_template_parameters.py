from django.db import migrations

import Tesla.model_fields


def encrypt_existing_values(apps, schema_editor):
    model = apps.get_model("execution_template", "ExecutionTemplate")
    for instance in model.objects.all().iterator(chunk_size=100):
        model.objects.filter(pk=instance.pk).update(parameters=instance.parameters)


class Migration(migrations.Migration):
    dependencies = [("execution_template", "0002_executiontemplate_output_fields")]

    operations = [
        migrations.AlterField(
            model_name="executiontemplate", name="parameters",
            field=Tesla.model_fields.EncryptedJSONField(blank=True, default=list, verbose_name="参数定义"),
        ),
        migrations.RunPython(encrypt_existing_values, migrations.RunPython.noop),
    ]
