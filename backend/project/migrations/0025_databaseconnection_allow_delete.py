from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("project", "0024_shared_module"),
    ]

    operations = [
        migrations.AddField(
            model_name="databaseconnection",
            name="allow_delete",
            field=models.BooleanField(default=False, verbose_name="允许执行 DELETE"),
        ),
    ]
