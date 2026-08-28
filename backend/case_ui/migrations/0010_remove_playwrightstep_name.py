from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("case_ui", "0009_playwrightlocatorfingerprint")]

    operations = [
        migrations.RemoveField(model_name="playwrightstep", name="name"),
    ]
