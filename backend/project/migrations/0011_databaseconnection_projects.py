from django.db import migrations, models


def copy_project_to_projects(apps, schema_editor):
    DatabaseConnection = apps.get_model("project", "DatabaseConnection")
    for connection in DatabaseConnection.objects.exclude(project_id=None).iterator():
        connection.projects.add(connection.project_id)


class Migration(migrations.Migration):

    dependencies = [
        ("project", "0010_databaseconnection_ssl_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="databaseconnection",
            name="projects",
            field=models.ManyToManyField(
                related_name="database_connections",
                to="project.project",
                verbose_name="所属项目",
            ),
        ),
        migrations.RunPython(copy_project_to_projects, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="databaseconnection",
            name="unique_project_environment_database_function",
        ),
        migrations.RemoveField(
            model_name="databaseconnection",
            name="project",
        ),
        migrations.AlterModelOptions(
            name="databaseconnection",
            options={"ordering": ["environment_name", "id"]},
        ),
    ]
