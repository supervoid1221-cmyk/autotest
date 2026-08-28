import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("project", "0011_databaseconnection_projects"),
        ("suite", "0015_runresult_random_numeric_primary_key"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExecutionTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=64, verbose_name="模板名称")),
                ("description", models.CharField(blank=True, max_length=250, verbose_name="模板描述")),
                ("parameters", models.JSONField(blank=True, default=list, verbose_name="参数定义")),
                ("enabled", models.BooleanField(default=True, verbose_name="启用")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="execution_templates", to="project.project", verbose_name="归属项目")),
                ("suite", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="execution_templates", to="suite.suite", verbose_name="关联套件")),
            ],
            options={
                "ordering": ["-id"],
            },
        ),
    ]
