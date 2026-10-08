import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("case_ui", "0019_playwrightscenariofile"),
    ]

    operations = [
        migrations.AddField(
            model_name="playwrightcase",
            name="source_yaml_file",
            field=models.ForeignKey(
                blank=True, editable=False, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="converted_cases", to="case_ui.playwrightscenariofile",
                verbose_name="来源 YAML 文件",
            ),
        ),
        migrations.AddField(
            model_name="playwrightcase",
            name="source_yaml_scene_key",
            field=models.CharField(
                blank=True, default="", editable=False, max_length=128,
                verbose_name="来源场景标识",
            ),
        ),
        migrations.AddConstraint(
            model_name="playwrightcase",
            constraint=models.UniqueConstraint(
                fields=("source_yaml_file", "source_yaml_scene_key"),
                name="unique_playwright_yaml_scene",
            ),
        ),
    ]
