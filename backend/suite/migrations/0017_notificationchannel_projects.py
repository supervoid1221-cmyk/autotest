from django.db import migrations, models


def copy_channel_project_to_projects(apps, schema_editor):
    NotificationChannel = apps.get_model("suite", "NotificationChannel")
    for channel in NotificationChannel.objects.exclude(project_id=None):
        channel.projects.add(channel.project_id)


class Migration(migrations.Migration):
    dependencies = [("suite", "0016_notifications")]

    operations = [
        migrations.AddField(
            model_name="notificationchannel",
            name="projects",
            field=models.ManyToManyField(related_name="notification_channels", to="project.project", verbose_name="关联项目"),
        ),
        migrations.RunPython(copy_channel_project_to_projects, migrations.RunPython.noop),
        migrations.RemoveField(model_name="notificationchannel", name="project"),
    ]
