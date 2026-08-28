from django.db import migrations, models
import django.db.models.deletion


def seed_execution_items(apps, schema_editor):
    Suite = apps.get_model("suite", "Suite")
    SuiteScenario = apps.get_model("suite", "SuiteScenario")
    SuiteUiCase = apps.get_model("suite", "SuiteUiCase")
    SuiteExecutionItem = apps.get_model("suite", "SuiteExecutionItem")

    pending = []
    for suite in Suite.objects.all().iterator():
        order = 1
        for link in SuiteScenario.objects.filter(suite_id=suite.id).order_by("order", "id"):
            pending.append(SuiteExecutionItem(
                suite_id=suite.id, item_type="api", scenario_id=link.scenario_id, order=order
            ))
            order += 1
        for link in SuiteUiCase.objects.filter(suite_id=suite.id).order_by("order", "id"):
            pending.append(SuiteExecutionItem(
                suite_id=suite.id, item_type="ui", ui_case_id=link.ui_case_id, order=order
            ))
            order += 1
    SuiteExecutionItem.objects.bulk_create(pending)


class Migration(migrations.Migration):
    dependencies = [
        ("suite", "0018_suite_ui_cases"),
    ]

    operations = [
        migrations.AddField(
            model_name="suite",
            name="enabled",
            field=models.BooleanField(default=True, verbose_name="启用"),
        ),
        migrations.CreateModel(
            name="SuiteExecutionItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("item_type", models.CharField(choices=[("api", "接口场景"), ("ui", "UI 用例")], max_length=8, verbose_name="类型")),
                ("order", models.PositiveIntegerField(verbose_name="执行顺序")),
                ("scenario", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="case_api.scenario")),
                ("suite", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="execution_items", to="suite.suite")),
                ("ui_case", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to="case_ui.uicase")),
            ],
            options={"ordering": ["order", "id"]},
        ),
        migrations.RunPython(seed_execution_items, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="suiteexecutionitem",
            constraint=models.UniqueConstraint(fields=("suite", "order"), name="unique_suite_execution_order"),
        ),
        migrations.AddConstraint(
            model_name="suiteexecutionitem",
            constraint=models.UniqueConstraint(condition=models.Q(("scenario__isnull", False)), fields=("suite", "scenario"), name="unique_suite_execution_scenario"),
        ),
        migrations.AddConstraint(
            model_name="suiteexecutionitem",
            constraint=models.UniqueConstraint(condition=models.Q(("ui_case__isnull", False)), fields=("suite", "ui_case"), name="unique_suite_execution_ui_case"),
        ),
        migrations.AddConstraint(
            model_name="suiteexecutionitem",
            constraint=models.CheckConstraint(
                check=(
                    models.Q(("item_type", "api"), ("scenario__isnull", False), ("ui_case__isnull", True))
                    | models.Q(("item_type", "ui"), ("scenario__isnull", True), ("ui_case__isnull", False))
                ),
                name="suite_execution_item_matches_type",
            ),
        ),
    ]
