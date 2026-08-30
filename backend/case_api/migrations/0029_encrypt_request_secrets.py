from django.db import migrations

import Tesla.model_fields


def encrypt_existing_values(apps, schema_editor):
    field_map = {
        "Endpoint": ("params", "data", "json", "parametrize", "cookies", "headers"),
        "ScenarioStep": ("request_override", "post_sql"),
    }
    for model_name, field_names in field_map.items():
        model = apps.get_model("case_api", model_name)
        for instance in model.objects.all().iterator(chunk_size=100):
            values = {field: getattr(instance, field) for field in field_names}
            model.objects.filter(pk=instance.pk).update(**values)


class Migration(migrations.Migration):
    dependencies = [("case_api", "0028_scenario_created_at_ordering")]

    operations = [
        migrations.AlterField(
            model_name="endpoint", name="params",
            field=Tesla.model_fields.EncryptedJSONField(blank=True, max_length=10240, null=True, verbose_name="查询字符串"),
        ),
        migrations.AlterField(
            model_name="endpoint", name="data",
            field=Tesla.model_fields.EncryptedJSONField(blank=True, max_length=10240, null=True, verbose_name="表单参数"),
        ),
        migrations.AlterField(
            model_name="endpoint", name="json",
            field=Tesla.model_fields.EncryptedJSONField(blank=True, max_length=10240, null=True, verbose_name="JSON参数"),
        ),
        migrations.AlterField(
            model_name="endpoint", name="parametrize",
            field=Tesla.model_fields.EncryptedJSONField(blank=True, default=list, verbose_name="数据驱动参数"),
        ),
        migrations.AlterField(
            model_name="endpoint", name="cookies",
            field=Tesla.model_fields.EncryptedJSONField(blank=True, max_length=10240, null=True, verbose_name="Cookies"),
        ),
        migrations.AlterField(
            model_name="endpoint", name="headers",
            field=Tesla.model_fields.EncryptedJSONField(blank=True, max_length=10240, null=True, verbose_name="请求头"),
        ),
        migrations.AlterField(
            model_name="scenariostep", name="request_override",
            field=Tesla.model_fields.EncryptedJSONField(blank=True, default=dict, verbose_name="参数覆盖"),
        ),
        migrations.AlterField(
            model_name="scenariostep", name="post_sql",
            field=Tesla.model_fields.EncryptedJSONField(blank=True, default=list, verbose_name="后置数据库操作"),
        ),
        migrations.RunPython(encrypt_existing_values, migrations.RunPython.noop),
    ]
