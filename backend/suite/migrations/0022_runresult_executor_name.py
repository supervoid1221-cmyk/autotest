from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("suite", "0021_suiteplaywrightcase_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="runresult",
            name="executor_name",
            field=models.CharField(default="系统", max_length=150, verbose_name="执行人"),
        ),
    ]
