from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("execution_template", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="executiontemplate",
            name="output_fields",
            field=models.JSONField(blank=True, default=list, verbose_name="输出字段配置"),
        ),
    ]
