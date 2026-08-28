import re

from django.db import migrations


LEGACY_PLAIN_PATTERN = re.compile(r"\$(?!ddt\{)([A-Za-z_]\w*)")


def transform(value, converter):
    if isinstance(value, dict):
        return {transform(key, converter): transform(item, converter) for key, item in value.items()}
    if isinstance(value, list):
        return [transform(item, converter) for item in value]
    if isinstance(value, str):
        return converter(value)
    return value


def to_current(value):
    return LEGACY_PLAIN_PATTERN.sub(lambda match: "{{" + match.group(1) + "}}", value)


def migrate_placeholders(apps, schema_editor, converter=to_current):
    Endpoint = apps.get_model("case_api", "Endpoint")
    ScenarioStep = apps.get_model("case_api", "ScenarioStep")
    model_fields = {
        Endpoint: ("url", "headers", "params", "data", "json", "files"),
        ScenarioStep: ("request_override", "validate"),
    }
    for model, field_names in model_fields.items():
        for instance in model.objects.all().iterator():
            updates = {}
            for field_name in field_names:
                original = getattr(instance, field_name)
                converted = transform(original, converter)
                if converted != original:
                    updates[field_name] = converted
            if updates:
                model.objects.filter(pk=instance.pk).update(**updates)


def migrate_to_current(apps, schema_editor):
    migrate_placeholders(apps, schema_editor, to_current)


class Migration(migrations.Migration):
    dependencies = [("case_api", "0018_scenariostep_post_sql")]

    operations = [migrations.RunPython(migrate_to_current, migrations.RunPython.noop)]
