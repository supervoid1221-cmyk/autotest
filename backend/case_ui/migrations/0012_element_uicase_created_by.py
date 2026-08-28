from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("case_ui", "0011_playwrightcase_created_by"),
    ]

    operations = [
        migrations.AddField(
            model_name="element",
            name="created_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_ui_elements", to=settings.AUTH_USER_MODEL,
                verbose_name="创建人",
            ),
        ),
        migrations.AddField(
            model_name="uicase",
            name="created_by",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_ui_cases", to=settings.AUTH_USER_MODEL,
                verbose_name="创建人",
            ),
        ),
    ]
