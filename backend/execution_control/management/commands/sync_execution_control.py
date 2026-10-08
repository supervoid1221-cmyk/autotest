from django.core.management.base import BaseCommand

from execution_control.services import diagnose_tasks
from execution_control.sync import sync_all_existing


class Command(BaseCommand):
    help = "回填并对账统一执行控制中心的历史任务。"

    def handle(self, *args, **options):
        counts = sync_all_existing()
        diagnostics = diagnose_tasks()
        self.stdout.write(self.style.SUCCESS(f"同步完成：{counts}；诊断：{diagnostics}"))
