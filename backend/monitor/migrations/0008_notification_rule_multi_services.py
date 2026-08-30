from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("monitor", "0007_monitor_cluster_mode"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="monitornotificationrule",
            name="service",
        ),
        migrations.AddField(
            model_name="monitornotificationrule",
            name="all_services",
            field=models.BooleanField(default=False, verbose_name="全部服务"),
        ),
        migrations.AddField(
            model_name="monitornotificationrule",
            name="services",
            field=models.ManyToManyField(blank=True, related_name="notification_rules", to="monitor.servicemonitor"),
        ),
    ]
