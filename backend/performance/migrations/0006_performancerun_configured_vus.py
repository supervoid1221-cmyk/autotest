from django.db import migrations, models


def populate_configured_vus(apps, schema_editor):
    PerformanceRun = apps.get_model("performance", "PerformanceRun")
    for run in PerformanceRun.objects.select_related("scenario").iterator():
        stages = run.scenario.stages if isinstance(run.scenario.stages, list) else []
        targets = []
        for stage in stages:
            if not isinstance(stage, dict):
                continue
            try:
                targets.append(float(stage.get("target", 0)))
            except (TypeError, ValueError):
                continue
        run.configured_vus = max(targets, default=0)
        run.save(update_fields=["configured_vus"])


class Migration(migrations.Migration):

    dependencies = [
        ("performance", "0005_performancescenario_business_mix_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="performancerun",
            name="configured_vus",
            field=models.FloatField(default=0, verbose_name="配置峰值并发"),
        ),
        migrations.RunPython(populate_configured_vus, migrations.RunPython.noop),
    ]
