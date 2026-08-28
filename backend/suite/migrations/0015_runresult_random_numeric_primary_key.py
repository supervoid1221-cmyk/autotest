from django.db import migrations, models

import suite.models


class Migration(migrations.Migration):

    dependencies = [
        ("suite", "0014_runresult_numeric_execution_no"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="runresult",
            name="execution_no",
        ),
        migrations.AlterField(
            model_name="runresult",
            name="id",
            field=models.PositiveBigIntegerField(
                default=suite.models.generate_execution_no,
                editable=False,
                primary_key=True,
                serialize=False,
            ),
        ),
    ]
