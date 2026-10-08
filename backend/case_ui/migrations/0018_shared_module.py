"""把 UI 元素目录并入共享的项目级目录。

与 case_api/0036 同构：先 AlterField 把 Element.module 指向 project.Module，
再按 (project, name) 合并旧目录行，最后删掉 ElementModule。

这里合并会命中接口侧已经建好的目录行——这正是共享的意义：接口管理里已有的
「登录」目录，UI 元素管理直接复用，不再新建一条同名记录。
"""

from django.db import migrations, models
import django.db.models.deletion


def merge_into_shared_module(apps, schema_editor):
    ElementModule = apps.get_model("case_ui", "ElementModule")
    Element = apps.get_model("case_ui", "Element")
    Module = apps.get_model("project", "Module")

    mapping = {}
    for legacy in ElementModule.objects.all().order_by("id"):
        module, _ = Module.objects.get_or_create(project_id=legacy.project_id, name=legacy.name)
        mapping[legacy.id] = module.id
    for legacy_id, shared_id in mapping.items():
        Element.objects.filter(module_id=legacy_id).update(module_id=shared_id)


def restore_legacy_modules(apps, schema_editor):
    """回滚：按当前元素引用到的共享目录重建 UI 元素目录行。

    与 case_api/0036 同样是**有损回滚**：主键重新分配，且只重建仍被元素引用的
    目录，空目录不会回来。
    """
    Module = apps.get_model("project", "Module")
    ElementModule = apps.get_model("case_ui", "ElementModule")
    Element = apps.get_model("case_ui", "Element")

    referenced = set(Element.objects.exclude(module_id=None).values_list("module_id", flat=True))
    mapping = {}
    for module in Module.objects.filter(id__in=referenced).order_by("id"):
        legacy = ElementModule.objects.create(project_id=module.project_id, name=module.name)
        mapping[module.id] = legacy.id
    for shared_id, legacy_id in mapping.items():
        Element.objects.filter(module_id=shared_id).update(module_id=legacy_id)


class Migration(migrations.Migration):

    dependencies = [
        ('project', '0024_shared_module'),
        ('case_ui', '0017_playwrightcase_tenant_uicase_tenant_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='element',
            name='module',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='ui_elements', to='project.module', verbose_name='所属模块'),
        ),
        migrations.RunPython(merge_into_shared_module, restore_legacy_modules),
        migrations.DeleteModel(
            name='ElementModule',
        ),
    ]
