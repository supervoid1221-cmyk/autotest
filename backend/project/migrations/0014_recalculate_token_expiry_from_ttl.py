from datetime import timedelta

from django.db import migrations


def recalculate_token_expiry(apps, schema_editor):
    Environment = apps.get_model("project", "Environment")
    for environment in Environment.objects.all().iterator():
        if environment.cached_token and environment.token_refreshed_at:
            ttl = max(1, int(environment.token_ttl or 1800))
            expires_at = environment.token_refreshed_at + timedelta(seconds=ttl)
        else:
            expires_at = None
        Environment.objects.filter(pk=environment.pk).update(token_expires_at=expires_at)


class Migration(migrations.Migration):
    dependencies = [
        ("project", "0013_projectvariable_and_more"),
    ]

    operations = [
        migrations.RunPython(recalculate_token_expiry, migrations.RunPython.noop),
    ]
