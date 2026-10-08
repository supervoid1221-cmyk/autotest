from django.apps import AppConfig


class ExecutionControlConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "execution_control"
    verbose_name = "统一执行控制中心"

    def ready(self):
        from . import signals  # noqa: F401
        from django.db.models.signals import post_migrate
        from .signals import backfill_execution_tasks

        post_migrate.connect(
            backfill_execution_tasks,
            sender=self,
            dispatch_uid="execution_control.backfill_execution_tasks",
        )
