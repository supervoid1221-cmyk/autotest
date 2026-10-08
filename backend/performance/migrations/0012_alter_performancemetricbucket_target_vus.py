from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("performance", "0011_performancemetricbucket_target_vus")]

    operations = [
        migrations.AlterField(
            model_name="performancemetricbucket",
            name="target_vus",
            field=models.FloatField(blank=True, default=0, null=True),
        ),
    ]
