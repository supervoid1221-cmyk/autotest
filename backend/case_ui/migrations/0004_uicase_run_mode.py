from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("case_ui", "0003_uicase_uistep"),
    ]

    operations = [
        migrations.AddField(
            model_name="uicase",
            name="run_mode",
            field=models.CharField(
                choices=[("headless", "无头模式"), ("headed", "有界面模式")],
                default="headless",
                max_length=16,
                verbose_name="运行模式",
            ),
        ),
    ]
