"""新建项目级共享目录。

改造前接口、UI 元素、App 元素各有一套目录表，同一个业务模块要在三个页面各建
一遍。本迁移只负责建表；三处旧目录的数据合并由各自应用的下一个迁移完成
（case_api/0036、case_ui/0018、case_app/0009），它们都依赖本迁移。
"""

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('project', '0023_project_tenant'),
    ]

    operations = [
        migrations.CreateModel(
            name='Module',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=96, verbose_name='模块名称')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_modules', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('project', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='modules', to='project.project', verbose_name='所属项目')),
            ],
            options={
                'ordering': ['project_id', 'id'],
            },
        ),
        migrations.AddConstraint(
            model_name='module',
            constraint=models.UniqueConstraint(fields=('project', 'name'), name='unique_project_module_name'),
        ),
    ]
