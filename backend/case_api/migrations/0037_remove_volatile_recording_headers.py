from django.db import migrations


VOLATILE_HEADER_NAMES = {"x-timestamp", "x-nonce", "x-signature"}


def remove_volatile_headers(apps, schema_editor):
    Endpoint = apps.get_model("case_api", "Endpoint")
    for endpoint in Endpoint.objects.all().iterator(chunk_size=200):
        headers = endpoint.headers or {}
        if not isinstance(headers, dict):
            continue
        sanitized = {
            key: value
            for key, value in headers.items()
            if str(key).strip().lower() not in VOLATILE_HEADER_NAMES
        }
        if len(sanitized) != len(headers):
            endpoint.headers = sanitized
            endpoint.save(update_fields=["headers"])


class Migration(migrations.Migration):
    dependencies = [("case_api", "0036_shared_module")]

    operations = [
        migrations.RunPython(remove_volatile_headers, migrations.RunPython.noop),
    ]
