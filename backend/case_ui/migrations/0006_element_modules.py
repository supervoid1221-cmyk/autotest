from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("project", "0012_databaseconnection_allow_write"),
        ("case_ui", "0005_uicase_tabs_uistep_tab_key"),
    ]

    operations = [
        migrations.CreateModel(
            name="ElementModule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=64, verbose_name="模块名称")),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ui_element_modules",
                        to="project.project",
                        verbose_name="所属项目",
                    ),
                ),
            ],
            options={"ordering": ["project_id", "id"]},
        ),
        migrations.AddField(
            model_name="element",
            name="module",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="elements",
                to="case_ui.elementmodule",
                verbose_name="所属模块",
            ),
        ),
        migrations.AddConstraint(
            model_name="elementmodule",
            constraint=models.UniqueConstraint(
                fields=("project", "name"), name="unique_ui_element_module_name"
            ),
        ),
    ]
