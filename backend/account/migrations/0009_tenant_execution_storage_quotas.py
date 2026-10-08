from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("account", "0008_tenant_tenantmembership")]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="max_concurrent_executions",
            field=models.PositiveSmallIntegerField(default=2, verbose_name="最大并发执行数"),
        ),
        migrations.AddField(
            model_name="tenant",
            name="storage_quota_bytes",
            field=models.PositiveBigIntegerField(default=10737418240, verbose_name="存储配额（字节）"),
        ),
    ]
