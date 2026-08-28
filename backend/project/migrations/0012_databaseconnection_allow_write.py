from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("project", "0011_databaseconnection_projects")]

    operations = [
        migrations.AddField(
            model_name="databaseconnection",
            name="allow_write",
            field=models.BooleanField(default=False, verbose_name="允许执行 UPDATE"),
        ),
    ]
