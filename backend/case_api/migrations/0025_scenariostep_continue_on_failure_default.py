from django.db import migrations, models


def enable_continue_for_existing_steps(apps, schema_editor):
    """旧版页面没有暴露此配置，历史 False 实际代表旧缺省值。"""
    ScenarioStep = apps.get_model("case_api", "ScenarioStep")
    ScenarioStep.objects.filter(continue_on_failure=False).update(continue_on_failure=True)


class Migration(migrations.Migration):

    dependencies = [
        ("case_api", "0024_endpoint_scenario_created_by"),
    ]

    operations = [
        migrations.AlterField(
            model_name="scenariostep",
            name="continue_on_failure",
            field=models.BooleanField(default=True, verbose_name="失败后继续"),
        ),
        migrations.RunPython(enable_continue_for_existing_steps, migrations.RunPython.noop),
    ]
