from django.core.management.base import BaseCommand, CommandError

from suite.retention import cleanup_expired_files


class Command(BaseCommand):
    help = "清理超过保留天数的本地执行目录、报告和日志"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, help="保留天数，默认读取 FILE_RETENTION_DAYS")
        parser.add_argument("--dry-run", action="store_true", help="只预览将被清理的文件")

    def handle(self, *args, **options):
        days = options["days"]
        if days is not None and days < 1:
            raise CommandError("保留天数必须大于 0")
        result = cleanup_expired_files(days, dry_run=options["dry_run"])
        action = "预览" if result["dry_run"] else "清理"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action}完成：保留 {result['retention_days']} 天，"
                f"命中 {result['removed_count']} 项，失败 {len(result['errors'])} 项。"
            )
        )
        for path in result["removed"]:
            self.stdout.write(path)
        for error in result["errors"]:
            self.stderr.write(f"{error['path']}: {error['error']}")
