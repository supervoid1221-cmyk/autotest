from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("project", "0008_environment_shared_token_cache"),
    ]

    operations = [
        migrations.CreateModel(
            name="DatabaseConnection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("environment_name", models.CharField(choices=[("Dev", "Dev"), ("Test", "Test"), ("Pre", "Pre"), ("Prod", "Prod")], max_length=16, verbose_name="执行环境")),
                ("database_type", models.CharField(choices=[("mysql", "MySQL"), ("postgresql", "PostgreSQL")], max_length=16, verbose_name="数据库类型")),
                ("function_name", models.CharField(max_length=64, verbose_name="调用函数")),
                ("host", models.CharField(max_length=255, verbose_name="Host")),
                ("port", models.PositiveIntegerField(verbose_name="Port")),
                ("database", models.CharField(max_length=128, verbose_name="Database")),
                ("username", models.CharField(max_length=128, verbose_name="用户名")),
                ("password", models.CharField(blank=True, max_length=512, verbose_name="密码")),
                ("connect_timeout", models.PositiveIntegerField(default=10, verbose_name="连接超时（秒）")),
                ("enabled", models.BooleanField(default=True, verbose_name="启用")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="database_connections", to="project.project")),
            ],
            options={"ordering": ["project_id", "environment_name", "id"]},
        ),
        migrations.AddConstraint(
            model_name="databaseconnection",
            constraint=models.UniqueConstraint(fields=("project", "environment_name", "function_name"), name="unique_project_environment_database_function"),
        ),
    ]
