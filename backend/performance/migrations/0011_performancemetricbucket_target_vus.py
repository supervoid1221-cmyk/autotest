from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("performance", "0010_performancerun_load_timing")]

    operations = [
        migrations.AddField(
            model_name="performancemetricbucket",
            name="target_vus",
            field=models.FloatField(default=0),
        ),
    ]
