from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("case_api", "0015_endpoint_parametrize")]

    operations = [
        migrations.AddField(
            model_name="scenariostep",
            name="node_type",
            field=models.CharField(
                choices=[("endpoint", "接口步骤"), ("condition", "条件分支")],
                default="endpoint", max_length=16, verbose_name="节点类型",
            ),
        ),
        migrations.AddField(
            model_name="scenariostep",
            name="parent_condition",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, related_name="branch_steps", to="case_api.scenariostep", verbose_name="所属条件节点"),
        ),
        migrations.AddField(
            model_name="scenariostep",
            name="branch_key",
            field=models.CharField(blank=True, default="", max_length=64, verbose_name="分支标识"),
        ),
        migrations.AddField(
            model_name="scenariostep",
            name="condition",
            field=models.JSONField(blank=True, default=dict, verbose_name="分支条件"),
        ),
    ]
