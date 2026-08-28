import uuid

from django.db import migrations, models


def populate_execution_numbers(apps, schema_editor):
    RunResult = apps.get_model("suite", "RunResult")
    for result in RunResult.objects.filter(execution_no__isnull=True).iterator():
        result.execution_no = uuid.uuid4()
        result.save(update_fields=["execution_no"])


class Migration(migrations.Migration):

    dependencies = [
        ("suite", "0012_runresult_environment_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="runresult",
            name="execution_no",
            field=models.UUIDField(editable=False, null=True, verbose_name="执行编号"),
        ),
        migrations.RunPython(populate_execution_numbers, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="runresult",
            name="execution_no",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, verbose_name="执行编号"),
        ),
    ]
