from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("monitor", "0003_monitor_notifications")]

    operations = [
        migrations.AddField(
            model_name="monitornotificationdelivery",
            name="alert_event",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notification_deliveries", to="monitor.monitoralertevent"),
        ),
        migrations.AddField(
            model_name="monitornotificationdelivery",
            name="service_event",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="notification_deliveries", to="monitor.servicemonitorevent"),
        ),
    ]
