from django.db import migrations
from django.utils import timezone


SCHEDULE_NAME = "清理超时 App 元素检查会话"


def create_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.update_or_create(
        name=SCHEDULE_NAME,
        defaults={
            "func": "case_app.tasks.cleanup_expired_inspection_sessions",
            "args": "()",
            "kwargs": "{}",
            "schedule_type": "I",
            "minutes": 1,
            "repeats": -1,
            "next_run": timezone.now(),
        },
    )


def remove_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(name=SCHEDULE_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("django_q", "0017_task_cluster_alter"),
        ("case_app", "0002_appinspectionsession_and_more"),
    ]

    operations = [migrations.RunPython(create_schedule, remove_schedule)]
