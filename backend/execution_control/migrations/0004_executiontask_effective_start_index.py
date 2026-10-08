from django.db import migrations, models
from django.db.models.functions import Coalesce


class Migration(migrations.Migration):

    dependencies = [
        ("execution_control", "0003_remove_executiontask_unique_execution_control_source_and_more"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="executiontask",
            index=models.Index(
                models.F("tenant"),
                Coalesce("started_at", "queued_at").desc(),
                models.F("id").desc(),
                name="exec_task_tenant_started_idx",
            ),
        ),
    ]
