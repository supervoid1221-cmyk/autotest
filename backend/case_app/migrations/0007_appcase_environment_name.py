from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("case_app", "0006_appstepresult_detail")]

    operations = [
        migrations.AddField(
            model_name="appcase",
            name="environment_name",
            field=models.CharField(blank=True, default="", max_length=64, verbose_name="执行环境"),
        ),
    ]
