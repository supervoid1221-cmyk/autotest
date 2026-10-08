from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("case_ui", "0019_playwrightscenariofile"),
        ("suite", "0030_suite_creator_name"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="suiteexecutionitem", name="suite_execution_item_matches_type",
        ),
        migrations.AddField(
            model_name="suiteexecutionitem", name="yaml_case",
            field=models.ForeignKey(
                to="case_ui.playwrightscenariofile", null=True, blank=True,
                on_delete=django.db.models.deletion.CASCADE,
            ),
        ),
        migrations.AlterField(
            model_name="suiteexecutionitem", name="item_type",
            field=models.CharField(
                verbose_name="类型", max_length=16,
                choices=[
                    ("api", "接口场景"), ("ui", "UI 用例"),
                    ("playwright_ui", "Playwright 智能 UI"),
                    ("yaml_ui", "YAML 智能 UI"), ("app", "App 用例"),
                ],
            ),
        ),
        migrations.AddConstraint(
            model_name="suiteexecutionitem",
            constraint=models.UniqueConstraint(
                fields=("suite", "yaml_case"), condition=models.Q(yaml_case__isnull=False),
                name="unique_suite_execution_yaml_case",
            ),
        ),
        migrations.AddConstraint(
            model_name="suiteexecutionitem",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(item_type="api", scenario__isnull=False, ui_case__isnull=True, playwright_case__isnull=True, yaml_case__isnull=True, app_case__isnull=True)
                    | models.Q(item_type="ui", scenario__isnull=True, ui_case__isnull=False, playwright_case__isnull=True, yaml_case__isnull=True, app_case__isnull=True)
                    | models.Q(item_type="playwright_ui", scenario__isnull=True, ui_case__isnull=True, playwright_case__isnull=False, yaml_case__isnull=True, app_case__isnull=True)
                    | models.Q(item_type="yaml_ui", scenario__isnull=True, ui_case__isnull=True, playwright_case__isnull=True, yaml_case__isnull=False, app_case__isnull=True)
                    | models.Q(item_type="app", scenario__isnull=True, ui_case__isnull=True, playwright_case__isnull=True, yaml_case__isnull=True, app_case__isnull=False)
                ),
                name="suite_execution_item_matches_type",
            ),
        ),
    ]
