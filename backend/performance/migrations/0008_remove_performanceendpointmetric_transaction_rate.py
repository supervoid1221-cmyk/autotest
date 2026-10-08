from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("performance", "0007_thread_group_and_aggregate_report"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="performanceendpointmetric",
            name="transaction_rate",
        ),
    ]
