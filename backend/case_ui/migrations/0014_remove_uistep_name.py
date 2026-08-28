from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("case_ui", "0013_uiuploadedfile_and_upload_actions"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="uistep",
            name="name",
        ),
    ]
