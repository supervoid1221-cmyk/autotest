from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0010_tenant_max_performance_worker_count"),
    ]

    operations = [
        migrations.RenameField(
            model_name="tenant",
            old_name="max_concurrent_executions",
            new_name="max_regular_concurrent_executions",
        ),
        migrations.RenameField(
            model_name="tenant",
            old_name="max_performance_worker_count",
            new_name="max_performance_concurrent_executions",
        ),
        migrations.AlterField(
            model_name="tenant",
            name="max_regular_concurrent_executions",
            field=models.PositiveSmallIntegerField(default=2, verbose_name="普通任务最大并发数"),
        ),
        migrations.AlterField(
            model_name="tenant",
            name="max_performance_concurrent_executions",
            field=models.PositiveSmallIntegerField(default=1, verbose_name="性能任务最大并发数"),
        ),
    ]
