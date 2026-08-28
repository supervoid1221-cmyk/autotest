from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("case_ui", "0012_element_uicase_created_by"),
    ]

    operations = [
        migrations.CreateModel(
            name="UiUploadedFile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("original_name", models.CharField(max_length=255, verbose_name="原始文件名")),
                ("stored_path", models.CharField(max_length=512, unique=True, verbose_name="存储路径")),
                ("size", models.PositiveBigIntegerField(default=0, verbose_name="文件大小")),
                ("create_datetime", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="uploaded_ui_test_files", to=settings.AUTH_USER_MODEL, verbose_name="上传人")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ui_uploaded_files", to="project.project")),
            ],
            options={"ordering": ["-id"]},
        ),
        migrations.AlterField(
            model_name="uistep",
            name="action",
            field=models.CharField(choices=[("goto", "打开页面"), ("click", "点击元素"), ("input", "输入文本"), ("upload_file", "上传文件"), ("clear", "清空输入"), ("save_text", "提取文本"), ("assert_text", "断言文本"), ("assert_value", "断言值"), ("iframe_enter", "进入 IFrame"), ("iframe_exit", "退出 IFrame"), ("select", "选择下拉项"), ("js_code", "执行 JavaScript"), ("sleep", "固定等待")], max_length=24, verbose_name="操作"),
        ),
        migrations.AlterField(
            model_name="playwrightstep",
            name="action",
            field=models.CharField(choices=[("goto", "打开页面"), ("input", "输入文本"), ("upload_file", "上传文件"), ("click", "点击"), ("clear", "清空输入"), ("select", "选择下拉项"), ("check", "勾选"), ("uncheck", "取消勾选"), ("assert_visible", "断言可见"), ("assert_text", "断言文本"), ("save_text", "提取文本"), ("sleep", "固定等待")], max_length=32, verbose_name="操作方式"),
        ),
    ]
