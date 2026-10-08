import Tesla.model_fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("performance", "0006_performancerun_configured_vus"),
    ]

    operations = [
        migrations.AddField(model_name="performancescenario", name="load_mode", field=models.CharField(choices=[("stages", "阶段模式"), ("thread_group", "线程组模式")], default="stages", max_length=16, verbose_name="负载模式")),
        migrations.AddField(model_name="performancescenario", name="thread_count", field=models.PositiveIntegerField(default=10, verbose_name="线程数")),
        migrations.AddField(model_name="performancescenario", name="duration_seconds", field=models.PositiveIntegerField(default=60, verbose_name="持续时间（秒）")),
        migrations.AddField(model_name="performancescenario", name="ramp_up_seconds", field=models.PositiveIntegerField(default=0, verbose_name="启动时间（秒）")),
        migrations.AddField(model_name="performancescenario", name="graceful_stop_seconds", field=models.PositiveIntegerField(default=5, verbose_name="停止等待时间（秒）")),
        migrations.AddField(model_name="performancerun", name="execution_config", field=Tesla.model_fields.EncryptedJSONField(blank=True, default=dict, verbose_name="执行配置快照")),
        migrations.AddField(model_name="performanceendpointmetric", name="duration_min", field=models.FloatField(default=0)),
        migrations.AddField(model_name="performanceendpointmetric", name="duration_median", field=models.FloatField(default=0)),
        migrations.AddField(model_name="performanceendpointmetric", name="duration_max", field=models.FloatField(default=0)),
        migrations.AddField(model_name="performanceendpointmetric", name="duration_p90", field=models.FloatField(default=0)),
        migrations.AddField(model_name="performanceendpointmetric", name="transaction_rate", field=models.FloatField(default=0)),
        migrations.AddField(model_name="performanceendpointmetric", name="throughput", field=models.FloatField(default=0)),
        migrations.AddField(model_name="performanceendpointmetric", name="received_bytes", field=models.BigIntegerField(default=0)),
        migrations.AddField(model_name="performanceendpointmetric", name="sent_bytes", field=models.BigIntegerField(default=0)),
        migrations.AddField(model_name="performanceendpointmetric", name="configured_ratio", field=models.FloatField(default=0)),
        migrations.AddField(model_name="performanceendpointmetric", name="actual_ratio", field=models.FloatField(default=0)),
    ]
