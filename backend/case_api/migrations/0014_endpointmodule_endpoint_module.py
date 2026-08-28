from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("case_api", "0013_scenariostep_polling"),
    ]

    operations = [
        migrations.CreateModel(
            name="EndpointModule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=64, verbose_name="模块名称")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="endpoint_modules", to="project.project", verbose_name="所属项目")),
            ],
            options={"ordering": ["project_id", "id"]},
        ),
        migrations.AddConstraint(
            model_name="endpointmodule",
            constraint=models.UniqueConstraint(fields=("project", "name"), name="unique_endpoint_module_name"),
        ),
        migrations.AddField(
            model_name="endpoint",
            name="module",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="endpoints", to="case_api.endpointmodule", verbose_name="所属模块"),
        ),
    ]
