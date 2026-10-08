from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("account", "0009_tenant_execution_storage_quotas")]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="max_performance_worker_count",
            field=models.PositiveSmallIntegerField(default=1, verbose_name="最大性能 Worker 数"),
        ),
    ]
