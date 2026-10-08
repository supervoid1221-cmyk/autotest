"""将分散的 ``<业务目录>/tenant_<UUID>`` 合并到租户独立根目录。"""
import json
import os
from datetime import datetime
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from account.models import Tenant
from account.tenant_runtime import (
    MANAGED_STORAGE_ROOTS,
    TENANT_STORAGE_ROOT,
    initialize_tenant_storage,
    legacy_tenant_path,
    tenant_directory_name,
    tenant_path,
)


BASE_DIR = Path(settings.BASE_DIR).resolve()
PATH_FIELDS = (
    ("suite", "RunResult", "path"),
    ("performance", "PerformanceRun", "work_dir"),
    ("case_app", "AppArtifact", "file_path"),
    ("case_app", "AppVersion", "file_path"),
    ("case_ui", "UiUploadedFile", "stored_path"),
)
JSON_FIELDS = (("case_api", "Endpoint", "files"),)


def _relative_parts(value):
    raw = str(value or "").strip()
    if not raw:
        return [], False
    path = Path(raw)
    absolute = path.is_absolute()
    if absolute:
        try:
            path = path.resolve().relative_to(BASE_DIR)
        except ValueError:
            return [], True
    return list(path.parts), absolute


def _rewrite_path(value, mappings):
    parts, absolute = _relative_parts(value)
    if not parts:
        return None
    text = "/".join(parts)
    for old_prefix, new_prefix in mappings.items():
        if text == old_prefix or text.startswith(old_prefix + "/"):
            suffix = text[len(old_prefix):].lstrip("/")
            rewritten = f"{new_prefix}/{suffix}" if suffix else new_prefix
            return str(BASE_DIR / rewritten) if absolute else rewritten
    return None


def _rewrite_json(value, mappings):
    if isinstance(value, str):
        rewritten = _rewrite_path(value, mappings)
        return (rewritten, 1) if rewritten else (value, 0)
    if isinstance(value, list):
        result, count = [], 0
        for item in value:
            rewritten, changed = _rewrite_json(item, mappings)
            result.append(rewritten)
            count += changed
        return result, count
    if isinstance(value, dict):
        result, count = {}, 0
        for key, item in value.items():
            rewritten, changed = _rewrite_json(item, mappings)
            result[key] = rewritten
            count += changed
        return result, count
    return value, 0


class Command(BaseCommand):
    help = "合并文件到 tenant_<租户编码>_<UUID> 独立目录。"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="真正执行；不加则只演练")
        parser.add_argument("--force", action="store_true", help="存在活动任务时仍执行")
        parser.add_argument("--manifest", default="", help="自定义迁移清单路径")

    def handle(self, *args, **options):
        self.apply = bool(options["apply"])
        self.moves = []
        self.db_changes = []
        self.notes = []
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.manifest_path = Path(options["manifest"]) if options["manifest"] else (
            BASE_DIR.parent / f"tenant_storage_manifest_{stamp}.json"
        )

        if self.apply and not options["force"]:
            ExecutionTask = apps.get_model("execution_control", "ExecutionTask")
            if ExecutionTask.objects.filter(
                status__in=("queued", "preparing", "running", "paused", "reporting")
            ).exists():
                raise CommandError("存在活动执行任务，请等待任务结束后再迁移。")

        mappings = self._build_mappings()
        self._move_namespaces(mappings)
        if self.apply:
            for tenant in Tenant.objects.all():
                initialize_tenant_storage(tenant, base_dir=BASE_DIR)
        self._rewrite_database(mappings)
        self._write_manifest()
        self._report()

    @staticmethod
    def _build_mappings():
        mappings = {}
        for tenant in Tenant.objects.all().order_by("created_at", "id"):
            tenant_root = BASE_DIR / TENANT_STORAGE_ROOT / tenant_directory_name(tenant)
            for namespace in MANAGED_STORAGE_ROOTS:
                old = legacy_tenant_path(BASE_DIR / namespace, tenant)
                new = tenant_path(BASE_DIR / namespace, tenant)
                mappings[old.relative_to(BASE_DIR).as_posix()] = new.relative_to(BASE_DIR).as_posix()
                consolidated_old = tenant_root / namespace
                if consolidated_old != new:
                    mappings[
                        consolidated_old.relative_to(BASE_DIR).as_posix()
                    ] = new.relative_to(BASE_DIR).as_posix()
        return mappings

    def _move_namespaces(self, mappings):
        self.stdout.write(self.style.MIGRATE_HEADING(
            "执行迁移" if self.apply else "演练（不修改文件和数据库）"
        ))
        for old_prefix, new_prefix in mappings.items():
            source = BASE_DIR / old_prefix
            target = BASE_DIR / new_prefix
            if not source.exists():
                continue
            if target.exists():
                self.notes.append(f"目标已存在，未合并：{target}")
                continue
            size = self._size(source)
            self.moves.append({"source": str(source), "target": str(target), "size": size})
            self.stdout.write(f"  {source.relative_to(BASE_DIR)} -> {target.relative_to(BASE_DIR)}")
            if self.apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                os.rename(source, target)

    @staticmethod
    def _size(path):
        if path.is_file():
            return path.stat().st_size
        return sum(
            item.stat().st_size for item in path.rglob("*")
            if item.is_file() and not item.is_symlink()
        )

    def _rewrite_database(self, mappings):
        with transaction.atomic():
            for app_label, model_name, field in PATH_FIELDS:
                model = apps.get_model(app_label, model_name)
                changed = []
                for obj in model.objects.all().iterator():
                    old = getattr(obj, field, "")
                    new = _rewrite_path(old, mappings)
                    if not new or new == old:
                        continue
                    setattr(obj, field, new)
                    changed.append(obj)
                    self.db_changes.append({
                        "model": f"{app_label}.{model_name}", "id": str(obj.pk),
                        "field": field, "old": str(old), "new": new,
                    })
                if changed and self.apply:
                    model.objects.bulk_update(changed, [field])

            for app_label, model_name, field in JSON_FIELDS:
                model = apps.get_model(app_label, model_name)
                changed = []
                for obj in model.objects.all().iterator():
                    new, count = _rewrite_json(getattr(obj, field, None), mappings)
                    if not count:
                        continue
                    setattr(obj, field, new)
                    changed.append(obj)
                    self.db_changes.append({
                        "model": f"{app_label}.{model_name}", "id": str(obj.pk),
                        "field": field, "changed_paths": count,
                    })
                if changed and self.apply:
                    model.objects.bulk_update(changed, [field])

            if not self.apply:
                transaction.set_rollback(True)

    def _write_manifest(self):
        if not self.apply:
            return
        self.manifest_path.write_text(json.dumps({
            "created_at": datetime.now().astimezone().isoformat(),
            "layout": f"{TENANT_STORAGE_ROOT}/tenant_<slug>_<uuid>/<namespace>",
            "moves": self.moves,
            "database_changes": self.db_changes,
            "notes": self.notes,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    def _report(self):
        total = sum(item["size"] for item in self.moves)
        self.stdout.write(self.style.SUCCESS(
            f"\n目录 {len(self.moves)} 个，文件 {total / 1024 / 1024:.2f} MiB，"
            f"数据库路径 {len(self.db_changes)} 条。"
        ))
        for note in self.notes:
            self.stdout.write(self.style.WARNING(f"  - {note}"))
        if self.apply:
            self.stdout.write(f"迁移清单：{self.manifest_path}")
        else:
            self.stdout.write(self.style.WARNING("未产生改动；确认后使用 --apply。"))
