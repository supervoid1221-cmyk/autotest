from django.db import migrations, models


def copy_dynamic_function_projects(apps, schema_editor):
    DynamicFunction = apps.get_model("project", "DynamicFunction")
    Project = apps.get_model("project", "Project")
    all_project_ids = list(Project.objects.values_list("id", flat=True))
    for dynamic_function in DynamicFunction.objects.all():
        project_ids = [dynamic_function.project_id] if dynamic_function.project_id else all_project_ids
        dynamic_function.assigned_projects.add(*project_ids)


class Migration(migrations.Migration):
    dependencies = [("project", "0016_projectvariable_description")]

    operations = [
        migrations.AddField(
            model_name="dynamicfunction",
            name="assigned_projects",
            field=models.ManyToManyField(
                blank=True,
                related_name="dynamic_function_assignments",
                to="project.project",
                verbose_name="所属项目",
            ),
        ),
        migrations.RunPython(copy_dynamic_function_projects, migrations.RunPython.noop),
        migrations.RemoveField(model_name="dynamicfunction", name="project"),
        migrations.RenameField(
            model_name="dynamicfunction",
            old_name="assigned_projects",
            new_name="projects",
        ),
        migrations.AlterField(
            model_name="dynamicfunction",
            name="projects",
            field=models.ManyToManyField(
                related_name="dynamic_functions",
                to="project.project",
                verbose_name="所属项目",
            ),
        ),
    ]
