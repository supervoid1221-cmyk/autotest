from django.db import migrations, models


def infer_body_type(apps, schema_editor):
    Endpoint = apps.get_model("case_api", "Endpoint")
    for endpoint in Endpoint.objects.all().only("id", "data", "json", "files"):
        if endpoint.files:
            body_type = "form_data"
        elif endpoint.data and not endpoint.json:
            body_type = "data"
        else:
            body_type = "json"
        Endpoint.objects.filter(pk=endpoint.pk).update(body_type=body_type)


class Migration(migrations.Migration):
    dependencies = [
        ("case_api", "0032_endpoint_dataset_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="endpoint",
            name="body_type",
            field=models.CharField(
                choices=[
                    ("json", "JSON"),
                    ("data", "x-www-form-urlencoded"),
                    ("form_data", "form-data"),
                ],
                default="json",
                max_length=16,
                verbose_name="请求体类型",
            ),
        ),
        migrations.RunPython(infer_body_type, migrations.RunPython.noop),
    ]
