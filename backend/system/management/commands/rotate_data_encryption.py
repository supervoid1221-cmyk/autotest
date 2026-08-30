from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "使用 DATA_ENCRYPTION_KEYS 中的首个密钥重新加密全部敏感字段"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="只检查现有密文能否解密")

    def handle(self, *args, **options):
        from case_api.models import Endpoint, ScenarioStep
        from case_ui.models import PlaywrightStep, UiStep
        from execution_template.models import ExecutionTemplate
        from monitor.models import PrometheusInstance
        from project.models import DatabaseConnection, Environment, ProjectVariable
        from suite.models import NotificationChannel, Suite
        from system.models import ServerConnection

        registry = (
            (ProjectVariable, ("value",)),
            (Environment, ("login_headers", "login_params", "login_data", "login_json", "cached_token")),
            (DatabaseConnection, ("password", "ssh_private_key_passphrase")),
            (ServerConnection, ("password", "private_key_passphrase")),
            (PrometheusInstance, ("access_token",)),
            (Suite, ("hook_key",)),
            (NotificationChannel, ("webhook_url",)),
            (Endpoint, ("params", "data", "json", "parametrize", "cookies", "headers")),
            (ScenarioStep, ("request_override", "post_sql")),
            (UiStep, ("value", "options")),
            (PlaywrightStep, ("value", "options")),
            (ExecutionTemplate, ("parameters",)),
        )

        checked = 0
        with transaction.atomic():
            for model, field_names in registry:
                for instance in model.objects.all().iterator(chunk_size=100):
                    values = {field: getattr(instance, field) for field in field_names}
                    checked += 1
                    if not options["dry_run"]:
                        model.objects.filter(pk=instance.pk).update(**values)
            if options["dry_run"]:
                transaction.set_rollback(True)

        action = "检查" if options["dry_run"] else "重新加密"
        self.stdout.write(self.style.SUCCESS(f"敏感数据{action}完成，共处理 {checked} 条记录。"))
