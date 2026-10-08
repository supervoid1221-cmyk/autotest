from django.db import migrations, models


def normalize_scenario_snapshots(apps, schema_editor):
    scenario_model = apps.get_model("performance", "PerformanceScenario")
    for scenario in scenario_model.objects.iterator():
        snapshot = scenario.scenario_snapshot or {}
        if snapshot.get("groups") or not snapshot.get("steps"):
            continue
        source_type = snapshot.get("source_type") or scenario.source_type or "scenario"
        source_id = snapshot.get("source_id") or (
            scenario.source_endpoint_id if source_type == "endpoint" else scenario.source_scenario_id
        )
        source_name = snapshot.get("source_name") or scenario.name
        scenario.scenario_snapshot = {
            "source_type": "mixed",
            "source_name": source_name,
            "groups": [{
                "key": f"{source_type}-{source_id}",
                "name": source_name,
                "source_type": source_type,
                "source_id": source_id,
                "weight": 100,
                "steps": snapshot.get("steps") or [],
            }],
        }
        scenario.save(update_fields=["scenario_snapshot"])


class Migration(migrations.Migration):
    dependencies = [
        ("performance", "0008_remove_performanceendpointmetric_transaction_rate"),
    ]

    operations = [
        migrations.RunPython(normalize_scenario_snapshots, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="performanceendpointmetric",
            name="actual_ratio",
        ),
        migrations.RemoveField(
            model_name="performancescenario",
            name="parameter_format",
        ),
        migrations.AlterField(
            model_name="performancescenario",
            name="load_type",
            field=models.CharField(
                choices=[
                    ("smoke", "冒烟测试"),
                    ("load", "负载测试"),
                    ("stress", "压力测试"),
                    ("spike", "峰值测试"),
                    ("soak", "稳定性测试"),
                    ("custom", "自定义"),
                ],
                default="load",
                max_length=16,
                verbose_name="负载模板",
            ),
        ),
    ]
