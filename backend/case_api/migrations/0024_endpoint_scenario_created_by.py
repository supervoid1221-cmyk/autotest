from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("case_api", "0023_scenario_step_request_target"),
    ]

    operations = [
        migrations.AddField(
            model_name="endpoint",
            name="created_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_endpoints", to=settings.AUTH_USER_MODEL,
                verbose_name="创建人",
            ),
        ),
        migrations.AddField(
            model_name="scenario",
            name="created_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_scenarios", to=settings.AUTH_USER_MODEL,
                verbose_name="创建人",
            ),
        ),
    ]
