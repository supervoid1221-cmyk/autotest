from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("system", "0001_initial")]

    operations = [
        migrations.DeleteModel(name="Role"),
        migrations.DeleteModel(name="Department"),
        migrations.DeleteModel(name="Position"),
    ]
