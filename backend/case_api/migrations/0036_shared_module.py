"""把接口目录并入共享的项目级目录。

改造前接口、UI 元素、App 元素各有一套目录表，同一个业务模块要在三个页面各建
一遍。这里把接口目录的行按 (project, name) 合并进 project.Module，并把
Endpoint.module 指过去；另外两个应用各自做同样的事。

先用临时外键写入新目录，再移除旧外键并重命名。MySQL 在 AlterField 时立即
检查外键，不能先改变外键指向、再更新旧目录 ID。
"""

from django.db import migrations, models
import django.db.models.deletion


def merge_into_shared_module(apps, schema_editor):
    EndpointModule = apps.get_model("case_api", "EndpointModule")
    Endpoint = apps.get_model("case_api", "Endpoint")
    Module = apps.get_model("project", "Module")

    mapping = {}
    for legacy in EndpointModule.objects.all().order_by("id"):
        module, _ = Module.objects.get_or_create(project_id=legacy.project_id, name=legacy.name)
        mapping[legacy.id] = module.id
    for legacy_id, shared_id in mapping.items():
        Endpoint.objects.filter(module_id=legacy_id).update(shared_module_id=shared_id)


def restore_legacy_modules(apps, schema_editor):
    """回滚：按当前接口引用到的共享目录重建接口目录行。

    这是有损回滚，两点需要注意：
    ① 主键无法还原（合并时可能与其他应用的同名目录共用一行），会重新分配；
    ② 只重建仍被接口引用的目录——没有任何接口的「空目录」在 DeleteModel 之后
       已无迹可循，回滚后会消失。
    """
    Module = apps.get_model("project", "Module")
    EndpointModule = apps.get_model("case_api", "EndpointModule")
    Endpoint = apps.get_model("case_api", "Endpoint")

    referenced = set(Endpoint.objects.exclude(shared_module_id=None).values_list("shared_module_id", flat=True))
    mapping = {}
    for module in Module.objects.filter(id__in=referenced).order_by("id"):
        legacy = EndpointModule.objects.create(project_id=module.project_id, name=module.name)
        mapping[module.id] = legacy.id
    for shared_id, legacy_id in mapping.items():
        Endpoint.objects.filter(shared_module_id=shared_id).update(module_id=legacy_id)


class Migration(migrations.Migration):

    dependencies = [
        ('project', '0024_shared_module'),
        ('case_api', '0035_scenario_tenant_scenario_api_scn_tenant_proj_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='endpoint',
            name='shared_module',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='project.module', verbose_name='所属模块'),
        ),
        migrations.RunPython(merge_into_shared_module, restore_legacy_modules),
        migrations.RemoveField(model_name='endpoint', name='module'),
        migrations.RenameField(model_name='endpoint', old_name='shared_module', new_name='module'),
        migrations.AlterField(
            model_name='endpoint',
            name='module',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='endpoints', to='project.module', verbose_name='所属模块'),
        ),
        migrations.DeleteModel(
            name='EndpointModule',
        ),
    ]
