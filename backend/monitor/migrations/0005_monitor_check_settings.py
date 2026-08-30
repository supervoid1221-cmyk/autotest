from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone


SCHEDULE_NAME = "平台监控统一检查"


def initialize_monitor_schedule(apps, schema_editor):
    MonitorCheckSettings = apps.get_model("monitor", "MonitorCheckSettings")
    Schedule = apps.get_model("django_q", "Schedule")
    MonitorCheckSettings.objects.get_or_create(
        pk=1,
        defaults={
            "target_check_interval_seconds": 60,
            "service_check_interval_seconds": 60,
        },
    )
    Schedule.objects.update_or_create(
        name=SCHEDULE_NAME,
        defaults={
            "func": "monitor.tasks.run_scheduled_monitor_checks",
            "args": "()",
            "kwargs": "{}",
            "schedule_type": "I",
            "minutes": 1,
            "repeats": -1,
            "next_run": timezone.now(),
        },
    )


def remove_monitor_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(name=SCHEDULE_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("django_q", "0017_task_cluster_alter"),
        ("monitor", "0004_notification_delivery_events"),
    ]

    operations = [
        migrations.CreateModel(
            name="MonitorCheckSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("target_check_interval_seconds", models.PositiveIntegerField(default=60, verbose_name="监控目标检查频率（秒）")),
                ("service_check_interval_seconds", models.PositiveIntegerField(default=60, verbose_name="服务监控检查频率（秒）")),
                ("last_target_check_at", models.DateTimeField(blank=True, null=True, verbose_name="最近监控目标检查时间")),
                ("last_service_check_at", models.DateTimeField(blank=True, null=True, verbose_name="最近服务监控检查时间")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("updated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="updated_monitor_check_settings", to=settings.AUTH_USER_MODEL)),
            ],
            options={"verbose_name": "监控检查频率", "verbose_name_plural": "监控检查频率"},
        ),
        migrations.RunPython(initialize_monitor_schedule, remove_monitor_schedule),
    ]
