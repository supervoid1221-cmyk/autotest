from django.db import migrations, models


def backfill_environment_name(apps, schema_editor):
    RunResult = apps.get_model("suite", "RunResult")
    for result in RunResult.objects.select_related("suite__environment").iterator():
        environment = getattr(result.suite, "environment", None)
        if environment:
            result.environment_name = environment.name
            result.save(update_fields=["environment_name"])


class Migration(migrations.Migration):
    dependencies = [("suite", "0011_suite_execution_timeout_runresult_execution_fields")]

    operations = [
        migrations.AddField(
            model_name="runresult",
            name="environment_name",
            field=models.CharField(blank=True, max_length=16, verbose_name="执行环境"),
        ),
        migrations.RunPython(backfill_environment_name, migrations.RunPython.noop),
    ]
