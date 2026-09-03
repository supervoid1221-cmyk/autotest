from copy import deepcopy

from django.db import migrations


def snapshot_endpoint_rules(apps, schema_editor):
    ScenarioStep = apps.get_model("case_api", "ScenarioStep")
    for step in ScenarioStep.objects.select_related("endpoint").iterator():
        endpoint = step.endpoint
        if endpoint is None:
            continue
        updates = []
        if not step.extract and endpoint.extract:
            step.extract = deepcopy(endpoint.extract)
            updates.append("extract")
        if not step.validate and endpoint.validate:
            step.validate = deepcopy(endpoint.validate)
            updates.append("validate")
        if updates:
            step.save(update_fields=updates)


class Migration(migrations.Migration):
    dependencies = [("case_api", "0030_endpoint_extract_endpoint_validate")]

    operations = [migrations.RunPython(snapshot_endpoint_rules, migrations.RunPython.noop)]
