from datetime import timedelta

from django.db import migrations
from django.utils import timezone


SCHEDULE_NAME = "清理过期执行文件"


def create_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    now = timezone.now()
    next_run = now.replace(hour=3, minute=30, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    Schedule.objects.update_or_create(
        name=SCHEDULE_NAME,
        defaults={
            "func": "suite.tasks.cleanup_expired_files",
            "args": "()",
            "kwargs": "{}",
            "schedule_type": "D",
            "repeats": -1,
            "next_run": next_run,
        },
    )


def remove_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(name=SCHEDULE_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("suite", "0019_suite_execution_items"),
    ]

    operations = [
        migrations.RunPython(create_schedule, remove_schedule),
    ]
