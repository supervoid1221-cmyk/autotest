from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("case_ui", "0002_delete_case"),
        ("project", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="UiCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=64, verbose_name="用例名称")),
                ("description", models.CharField(blank=True, max_length=250, verbose_name="用例描述")),
                ("browser", models.CharField(choices=[("chrome", "Chrome")], default="chrome", max_length=16, verbose_name="浏览器")),
                ("enabled", models.BooleanField(default=True, verbose_name="启用")),
                ("create_datetime", models.DateTimeField(auto_now_add=True)),
                ("update_datetime", models.DateTimeField(auto_now=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ui_cases", to="project.project")),
            ],
            options={"ordering": ["-id"]},
        ),
        migrations.AlterModelOptions(name="element", options={"ordering": ["-id"]}),
        migrations.CreateModel(
            name="UiStep",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order", models.PositiveIntegerField(default=1, verbose_name="执行顺序")),
                ("name", models.CharField(max_length=64, verbose_name="步骤名称")),
                ("action", models.CharField(choices=[("goto", "打开页面"), ("click", "点击元素"), ("input", "输入文本"), ("clear", "清空输入"), ("save_text", "提取文本"), ("assert_text", "断言文本"), ("assert_value", "断言值"), ("iframe_enter", "进入 IFrame"), ("iframe_exit", "退出 IFrame"), ("select", "选择下拉项"), ("js_code", "执行 JavaScript"), ("sleep", "固定等待")], max_length=24, verbose_name="操作")),
                ("value", models.TextField(blank=True, verbose_name="操作值")),
                ("options", models.JSONField(blank=True, default=dict, verbose_name="扩展配置")),
                ("continue_on_failure", models.BooleanField(default=False, verbose_name="失败后继续")),
                ("element", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="ui_steps", to="case_ui.element")),
                ("ui_case", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="steps", to="case_ui.uicase")),
            ],
            options={"ordering": ["order", "id"]},
        ),
        migrations.AddConstraint(
            model_name="uistep",
            constraint=models.UniqueConstraint(fields=("ui_case", "order"), name="unique_ui_case_step_order"),
        ),
    ]
