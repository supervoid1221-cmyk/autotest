from django.db import migrations


def add_tenant_to_schedule_args(apps, schema_editor):
    Suite = apps.get_model("suite", "Suite")
    Schedule = apps.get_model("django_q", "Schedule")
    for suite in Suite.objects.exclude(schedule_id=None).only("id", "tenant_id", "schedule_id"):
        Schedule.objects.filter(
            pk=suite.schedule_id,
            func="suite.tasks.run_by_cron",
        ).update(args=repr((suite.pk, str(suite.tenant_id))))


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0009_tenant_execution_storage_quotas"),
        ("suite", "0028_alter_runresult_options_runresult_tenant_and_more"),
    ]

    operations = [migrations.RunPython(add_tenant_to_schedule_args, migrations.RunPython.noop)]
