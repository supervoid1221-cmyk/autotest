from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("project", "0015_delete_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="projectvariable",
            name="description",
            field=models.CharField(blank=True, default="", max_length=256, verbose_name="参数描述"),
        ),
    ]
