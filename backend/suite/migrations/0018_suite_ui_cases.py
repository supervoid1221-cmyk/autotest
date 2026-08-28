from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("case_ui", "0003_uicase_uistep"),
        ("suite", "0017_notificationchannel_projects"),
    ]

    operations = [
        migrations.CreateModel(
            name="SuiteUiCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order", models.PositiveIntegerField(default=1, verbose_name="执行顺序")),
                ("suite", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="suite.suite")),
                ("ui_case", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="case_ui.uicase")),
            ],
            options={"ordering": ["order", "id"]},
        ),
        migrations.AddField(
            model_name="suite",
            name="ui_cases",
            field=models.ManyToManyField(blank=True, through="suite.SuiteUiCase", to="case_ui.uicase"),
        ),
        migrations.AddConstraint(
            model_name="suiteuicase",
            constraint=models.UniqueConstraint(fields=("suite", "ui_case"), name="unique_suite_ui_case"),
        ),
        migrations.AddConstraint(
            model_name="suiteuicase",
            constraint=models.UniqueConstraint(fields=("suite", "order"), name="unique_suite_ui_case_order"),
        ),
    ]
