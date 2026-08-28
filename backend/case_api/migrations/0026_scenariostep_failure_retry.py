from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("case_api", "0025_scenariostep_continue_on_failure_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="scenariostep",
            name="retry_on_failure",
            field=models.BooleanField(default=False, verbose_name="失败后重试"),
        ),
        migrations.AddField(
            model_name="scenariostep",
            name="failure_retry_count",
            field=models.PositiveSmallIntegerField(default=1, verbose_name="失败重试次数"),
        ),
    ]
