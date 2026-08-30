from django.db import migrations, models
import django.db.models.deletion


def infer_prometheus_projects(apps, schema_editor):
    PrometheusInstance = apps.get_model("monitor", "PrometheusInstance")
    MonitorTarget = apps.get_model("monitor", "MonitorTarget")
    for prometheus in PrometheusInstance.objects.filter(project__isnull=True):
        project_id = (
            MonitorTarget.objects.filter(prometheus_id=prometheus.id, project__isnull=False)
            .values_list("project_id", flat=True)
            .first()
        )
        if project_id:
            prometheus.project_id = project_id
            prometheus.save(update_fields=["project"])


class Migration(migrations.Migration):
    dependencies = [
        ("project", "0019_databaseconnection_ssh_host_and_more"),
        ("system", "0004_serverconnection_project"),
        ("monitor", "0005_monitor_check_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="prometheusinstance",
            name="project",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="prometheus_instances", to="project.project", verbose_name="所属项目"),
        ),
        migrations.RunPython(infer_prometheus_projects, migrations.RunPython.noop),
    ]
