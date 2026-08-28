from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("case_api", "0017_remove_scenariostep_branch_fields")]

    operations = [
        migrations.AddField(
            model_name="scenariostep",
            name="post_sql",
            field=models.JSONField(blank=True, default=list, verbose_name="后置数据库操作"),
        ),
    ]
