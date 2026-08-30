from django.db import migrations, models
import django.db.models.deletion


def infer_server_projects(apps, schema_editor):
    ServerConnection = apps.get_model("system", "ServerConnection")
    MonitorTarget = apps.get_model("monitor", "MonitorTarget")
    ServiceMonitor = apps.get_model("monitor", "ServiceMonitor")
    for server in ServerConnection.objects.filter(project__isnull=True):
        project_id = (
            MonitorTarget.objects.filter(server_id=server.id, project__isnull=False)
            .values_list("project_id", flat=True)
            .first()
        ) or (
            ServiceMonitor.objects.filter(server_id=server.id, project__isnull=False)
            .values_list("project_id", flat=True)
            .first()
        )
        if project_id:
            server.project_id = project_id
            server.save(update_fields=["project"])


class Migration(migrations.Migration):
    dependencies = [
        ("project", "0019_databaseconnection_ssh_host_and_more"),
        ("monitor", "0005_monitor_check_settings"),
        ("system", "0003_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="serverconnection",
            name="project",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="server_connections", to="project.project", verbose_name="所属项目"),
        ),
        migrations.RunPython(infer_server_projects, migrations.RunPython.noop),
    ]
