from django.db import migrations, models

import suite.models


def clear_historical_execution_numbers(apps, schema_editor):
    RunResult = apps.get_model("suite", "RunResult")
    RunResult.objects.update(execution_no=None)


class Migration(migrations.Migration):

    dependencies = [
        ("suite", "0013_runresult_execution_no"),
    ]

    operations = [
        migrations.AlterField(
            model_name="runresult",
            name="execution_no",
            field=models.PositiveBigIntegerField(
                default=suite.models.generate_execution_no,
                editable=False,
                null=True,
                unique=True,
                verbose_name="执行编号",
            ),
        ),
        migrations.RunPython(clear_historical_execution_numbers, migrations.RunPython.noop),
    ]
