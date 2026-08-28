import case_ui.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("case_ui", "0004_uicase_run_mode"),
    ]

    operations = [
        migrations.AddField(
            model_name="uicase",
            name="tabs",
            field=models.JSONField(
                blank=True,
                default=case_ui.models.default_ui_case_tabs,
                verbose_name="页签配置",
            ),
        ),
        migrations.AddField(
            model_name="uistep",
            name="tab_key",
            field=models.CharField(default="tab-1", max_length=64, verbose_name="所属页签"),
        ),
    ]
