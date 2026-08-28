from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("case_api", "0016_scenariostep_condition_branch")]

    operations = [
        migrations.RemoveField(model_name="scenariostep", name="parent_condition"),
        migrations.RemoveField(model_name="scenariostep", name="branch_key"),
        migrations.RemoveField(model_name="scenariostep", name="condition"),
        migrations.RemoveField(model_name="scenariostep", name="node_type"),
    ]
