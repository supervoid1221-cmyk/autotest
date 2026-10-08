from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("case_ui", "0015_encrypt_step_values")]

    operations = [
        migrations.AddField(
            model_name="uicase",
            name="environment_name",
            field=models.CharField(blank=True, default="", max_length=64, verbose_name="执行环境"),
        ),
    ]
