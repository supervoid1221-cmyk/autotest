from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("project", "0014_recalculate_token_expiry_from_ttl")]

    operations = [migrations.DeleteModel(name="Config")]
