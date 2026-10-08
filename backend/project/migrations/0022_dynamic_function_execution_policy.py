import hashlib
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def populate_code_hash(apps, schema_editor):
    DynamicFunction = apps.get_model("project", "DynamicFunction")
    DynamicFunctionRevision = apps.get_model("project", "DynamicFunctionRevision")
    for item in DynamicFunction.objects.only("id", "code").iterator():
        digest = hashlib.sha256(str(item.code or "").encode("utf-8")).hexdigest()
        DynamicFunction.objects.filter(pk=item.pk).update(code_hash=digest)
        DynamicFunctionRevision.objects.create(dynamic_function_id=item.pk, version=1, code=item.code, code_hash=digest, project_ids=list(item.projects.values_list("id", flat=True)), timeout_seconds=3, memory_mb=128)


class Migration(migrations.Migration):
    dependencies = [("project", "0021_environment_browser_token_fields")]
    operations = [
        migrations.AddField(model_name="dynamicfunction", name="language", field=models.CharField(default="python", editable=False, max_length=16, verbose_name="运行语言")),
        migrations.AddField(model_name="dynamicfunction", name="version", field=models.PositiveIntegerField(default=1, verbose_name="版本")),
        migrations.AddField(model_name="dynamicfunction", name="code_hash", field=models.CharField(blank=True, default="", editable=False, max_length=64, verbose_name="代码摘要")),
        migrations.AddField(model_name="dynamicfunction", name="approval_status", field=models.CharField(choices=[("draft", "待审批"), ("approved", "已审批"), ("rejected", "已驳回")], default="approved", max_length=16, verbose_name="审批状态")),
        migrations.AddField(model_name="dynamicfunction", name="timeout_seconds", field=models.PositiveSmallIntegerField(default=3, verbose_name="超时秒数")),
        migrations.AddField(model_name="dynamicfunction", name="memory_mb", field=models.PositiveSmallIntegerField(default=128, verbose_name="内存上限 MB")),
        migrations.AddField(model_name="dynamicfunction", name="created_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_dynamic_functions", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="dynamicfunction", name="approved_by", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_dynamic_functions", to=settings.AUTH_USER_MODEL)),
        migrations.AddField(model_name="dynamicfunction", name="approved_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.CreateModel(
            name="DynamicFunctionRevision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveIntegerField()), ("code", models.TextField()), ("code_hash", models.CharField(max_length=64)),
                ("project_ids", models.JSONField(default=list)), ("timeout_seconds", models.PositiveSmallIntegerField(default=3)),
                ("memory_mb", models.PositiveSmallIntegerField(default=128)), ("approved_at", models.DateTimeField(auto_now_add=True)),
                ("approved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="approved_dynamic_function_revisions", to=settings.AUTH_USER_MODEL)),
                ("dynamic_function", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="revisions", to="project.dynamicfunction")),
            ],
            options={"ordering": ["-version"]},
        ),
        migrations.AddConstraint(model_name="dynamicfunctionrevision", constraint=models.UniqueConstraint(fields=("dynamic_function", "version"), name="unique_dynamic_function_revision")),
        migrations.RunPython(populate_code_hash, migrations.RunPython.noop),
        # 旧数据先按已审批迁移；此后任何新建记录默认待审批。
        migrations.AlterField(model_name="dynamicfunction", name="approval_status", field=models.CharField(choices=[("draft", "待审批"), ("approved", "已审批"), ("rejected", "已驳回")], default="draft", max_length=16, verbose_name="审批状态")),
    ]
