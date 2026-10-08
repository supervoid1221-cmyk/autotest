from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("performance", "0009_remove_unused_performance_fields")]

    operations = [
        migrations.AddField(
            model_name="performancerun",
            name="load_started_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="实际压测开始时间"),
        ),
        migrations.AddField(
            model_name="performancerun",
            name="load_finished_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="实际压测结束时间"),
        ),
        migrations.AddField(
            model_name="performancerun",
            name="load_duration_ms",
            field=models.PositiveBigIntegerField(blank=True, null=True, verbose_name="实际压测时长（毫秒）"),
        ),
    ]
