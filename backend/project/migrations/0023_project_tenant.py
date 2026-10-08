from django.db import migrations, models
import django.db.models.deletion
import account.models


def assign_projects_to_default_tenant(apps, schema_editor):
    Tenant = apps.get_model("account", "Tenant")
    Project = apps.get_model("project", "Project")
    tenant, _ = Tenant.objects.get_or_create(
        slug="default",
        defaults={"name": "默认租户", "status": "active"},
    )
    Project.objects.filter(tenant__isnull=True).update(tenant_id=tenant.id)


class Migration(migrations.Migration):
    dependencies = [
        ("account", "0008_tenant_tenantmembership"),
        ("project", "0022_dynamic_function_execution_policy"),
    ]

    operations = [
        migrations.AddField(
            model_name="project",
            name="tenant",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="projects",
                to="account.tenant",
                verbose_name="所属租户",
            ),
        ),
        migrations.RunPython(assign_projects_to_default_tenant, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="project",
            name="tenant",
            field=models.ForeignKey(
                default=account.models.get_default_tenant_id,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="projects",
                to="account.tenant",
                verbose_name="所属租户",
            ),
        ),
        migrations.AddIndex(
            model_name="project",
            index=models.Index(fields=["tenant", "name"], name="project_tenant_name_idx"),
        ),
    ]
