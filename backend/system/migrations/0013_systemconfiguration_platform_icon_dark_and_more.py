from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("system", "0012_serverconnection_tenant_alter_serverconnection_name_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="systemconfiguration",
            name="platform_icon",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="system/branding/",
                verbose_name="浅色背景 Logo",
            ),
        ),
        migrations.AddField(
            model_name="systemconfiguration",
            name="platform_icon_dark",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="system/branding/",
                verbose_name="深色背景 Logo",
            ),
        ),
    ]
