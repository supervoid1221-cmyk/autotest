"""把 App 元素目录并入共享的项目级目录。

与 case_api/0036、case_ui/0018 同构，唯一区别是旧模型多一个「所属应用」维度：
AppElementModule 的唯一键是 (application, name)，而共享目录只有 (project, name)。
因此同一项目下不同应用的同名目录会合并成一条，迁移结束时会打印合并清单。

注意这是有意的产品变更：目录改为项目级后不再按应用隔离，应用退化为 App 元素
列表的筛选项（AppElement.application 本身保持不变）。
"""

import sys

from django.db import migrations, models
import django.db.models.deletion


def merge_into_shared_module(apps, schema_editor):
    AppElementModule = apps.get_model("case_app", "AppElementModule")
    AppElement = apps.get_model("case_app", "AppElement")
    Module = apps.get_model("project", "Module")

    mapping = {}
    collapsed = []
    for legacy in AppElementModule.objects.all().order_by("id"):
        module, created = Module.objects.get_or_create(project_id=legacy.project_id, name=legacy.name)
        mapping[legacy.id] = module.id
        if not created:
            collapsed.append(legacy.name)
    for legacy_id, shared_id in mapping.items():
        AppElement.objects.filter(module_id=legacy_id).update(shared_module_id=shared_id)
    if collapsed:
        # 元素本身不丢（仍挂在合并后的目录上），但合并掉了几条目录值得人工过一眼。
        sys.stdout.write(
            "共享目录迁移：以下 App 元素目录与其他应用的目录同名，已合并为一条：{}\n".format(
                "、".join(sorted(set(collapsed)))
            )
        )


def restore_legacy_modules(apps, schema_editor):
    """回滚：按当前 App 元素反推重建 App 元素目录。

    这是有损回滚。旧模型的 application 非空，而共享目录没有这个维度，只能从
    引用该目录的元素里取一个应用来填充；取不到应用（元素未绑定应用）的目录无法
    还原，其元素会退化为「未分组」而不是留下悬空外键。
    """
    Module = apps.get_model("project", "Module")
    AppElementModule = apps.get_model("case_app", "AppElementModule")
    AppElement = apps.get_model("case_app", "AppElement")

    referenced = set(AppElement.objects.exclude(shared_module_id=None).values_list("shared_module_id", flat=True))
    mapping = {}
    for module in Module.objects.filter(id__in=referenced).order_by("id"):
        application_id = (
            AppElement.objects.filter(shared_module_id=module.id)
            .exclude(application_id=None)
            .order_by("id")
            .values_list("application_id", flat=True)
            .first()
        )
        if not application_id:
            AppElement.objects.filter(shared_module_id=module.id).update(shared_module=None)
            continue
        legacy = AppElementModule.objects.create(
            project_id=module.project_id, application_id=application_id, name=module.name
        )
        mapping[module.id] = legacy.id
    for shared_id, legacy_id in mapping.items():
        AppElement.objects.filter(shared_module_id=shared_id).update(module_id=legacy_id)


class Migration(migrations.Migration):

    dependencies = [
        ('project', '0024_shared_module'),
        ('case_app', '0008_remove_appcase_unique_project_app_case_name_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='appelement',
            name='shared_module',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='project.module'),
        ),
        migrations.RunPython(merge_into_shared_module, restore_legacy_modules),
        migrations.RemoveField(model_name='appelement', name='module'),
        migrations.RenameField(model_name='appelement', old_name='shared_module', new_name='module'),
        migrations.AlterField(
            model_name='appelement',
            name='module',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='app_elements', to='project.module'),
        ),
        migrations.DeleteModel(
            name='AppElementModule',
        ),
    ]
