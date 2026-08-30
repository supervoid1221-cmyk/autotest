import logging
from datetime import timedelta

from django.db import transaction
from django.db import models
from django.utils import timezone

from .models import MonitorCheckSettings, MonitorCluster, MonitorTarget, ServiceMonitor
from .services import PrometheusRequestError, evaluate_alerts, record_service_status, service_snapshot, snapshot, sync_cluster


logger = logging.getLogger(__name__)


def _claim_due_check(field_name, interval_seconds):
    """原子领取一类检查，防止多个 qcluster Worker 重复执行。"""
    now = timezone.now()
    with transaction.atomic():
        settings = MonitorCheckSettings.objects.select_for_update().get(pk=1)
        last_checked_at = getattr(settings, field_name)
        if last_checked_at and last_checked_at > now - timedelta(seconds=interval_seconds):
            return False
        setattr(settings, field_name, now)
        settings.save(update_fields=[field_name, "updated_at"])
    return True


def _check_targets(settings):
    if settings.target_check_interval_seconds == 0:
        return {"checked": 0, "skipped": True, "disabled": True, "errors": []}
    if not _claim_due_check("last_target_check_at", settings.target_check_interval_seconds):
        return {"checked": 0, "skipped": True, "errors": []}
    checked, errors = 0, []
    for cluster in MonitorCluster.objects.select_related("prometheus", "server", "project").filter(enabled=True, prometheus__enabled=True):
        try: sync_cluster(cluster)
        except PrometheusRequestError as exc: errors.append({"cluster": cluster.name, "message": str(exc)})
    targets = MonitorTarget.objects.select_related("prometheus", "project", "server").filter(
        enabled=True,
        prometheus__enabled=True,
    ).filter(models.Q(mode="standalone") | models.Q(discovery_active=True))
    for target in targets.iterator():
        try:
            data = snapshot(target)
            evaluate_alerts(target, data["current"])
            checked += 1
        except PrometheusRequestError as exc:
            errors.append({"target": target.name, "message": str(exc)})
            logger.warning("监控目标 %s 检查失败：%s", target.name, exc)
        except Exception:
            logger.exception("监控目标 %s 检查异常", target.name)
            errors.append({"target": target.name, "message": "检查任务异常"})
    return {"checked": checked, "skipped": False, "errors": errors}


def _check_services(settings):
    if settings.service_check_interval_seconds == 0:
        return {"checked": 0, "skipped": True, "disabled": True, "errors": []}
    if not _claim_due_check("last_service_check_at", settings.service_check_interval_seconds):
        return {"checked": 0, "skipped": True, "errors": []}
    checked, errors = 0, []
    services = ServiceMonitor.objects.select_related("project", "server").filter(enabled=True)
    for service in services.iterator():
        try:
            data = service_snapshot(service)
            record_service_status(service, data)
            checked += 1
        except Exception:
            logger.exception("服务监控 %s 检查异常", service.name)
            errors.append({"service": service.name, "message": "检查任务异常"})
    return {"checked": checked, "skipped": False, "errors": errors}


def run_scheduled_monitor_checks():
    """Django-Q 每分钟调用；两类检查按平台配置的独立频率执行。"""
    settings = MonitorCheckSettings.current()
    return {
        "targets": _check_targets(settings),
        "services": _check_services(settings),
        "finished_at": timezone.now().isoformat(),
    }
