"""监控告警复用测试套件既有的飞书、企业微信通知渠道。"""

from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from suite.notifications import deliver_notification, notification_payload

from .models import MonitorAlertEvent, MonitorNotificationDelivery, MonitorNotificationRule, ServiceMonitor


def _subject(target=None, service=None):
    if target:
        return "主机", target.name, target.project.name if target.project_id else "平台级"
    return "服务", service.name, service.project.name if service.project_id else "平台级"


def notify_monitor_event(
    event,
    target=None,
    service=None,
    message="",
    response_time_ms=None,
    alert_event=None,
    service_event=None,
    only_rule=None,
):
    """发送异常或恢复通知；调用方仅在状态变化时调用，避免重复告警。"""
    if bool(target) == bool(service):
        return
    kind, name, project_name = _subject(target, service)
    is_recovered = event == MonitorNotificationRule.Event.RECOVERED
    event_filter = MonitorNotificationRule.Event.RECOVERED if is_recovered else MonitorNotificationRule.Event.ALERT
    rules = MonitorNotificationRule.objects.select_related("channel").filter(
        enabled=True,
        channel__enabled=True,
    ).filter(Q(event=event_filter) | Q(event=MonitorNotificationRule.Event.ALL))
    if target:
        rules = rules.filter(target=target)
    else:
        rules = rules.filter(
            Q(services=service)
            | Q(all_services=True, channel__projects=service.project)
        ).distinct()
    if only_rule:
        rules = rules.filter(pk=only_rule.pk)
    title = "监控恢复" if is_recovered else "监控异常告警"
    text = "\n".join([
        "自动化测试平台 · 服务监控",
        f"事件：{title}",
        f"对象：{kind} · {name}",
        f"所属项目：{project_name}",
        f"详情：{message or ('状态已恢复' if is_recovered else '检测异常')}",
        f"响应耗时：{response_time_ms if response_time_ms is not None else '-'} ms",
    ])
    for rule in rules:
        event_deliveries = MonitorNotificationDelivery.objects.filter(
            rule=rule,
            event=event,
            alert_event=alert_event,
            service_event=service_event,
        )
        if alert_event or service_event:
            if event_deliveries.filter(status=MonitorNotificationDelivery.Status.SENT).exists():
                continue
            # 活动告警会随大盘轮询持续评估。失败后留出重试窗口，避免网络异常时每次轮询都重复发送。
            retry_after = timezone.now() - timedelta(minutes=5)
            if event_deliveries.filter(
                status=MonitorNotificationDelivery.Status.FAILED,
                created_at__gte=retry_after,
            ).exists():
                continue
        payload = notification_payload(rule.channel.platform, text)
        delivery = MonitorNotificationDelivery.objects.create(
            channel=rule.channel,
            rule=rule,
            target=target,
            service=service,
            alert_event=alert_event,
            service_event=service_event,
            event=event,
            status=MonitorNotificationDelivery.Status.FAILED,
            payload=payload,
        )
        deliver_notification(rule.channel, payload, delivery)


def backfill_active_alerts(rule):
    """规则保存后补发仍处于活动状态、且该规则尚未成功投递的告警。"""
    if not rule.enabled or not rule.channel.enabled:
        return
    if rule.event not in (MonitorNotificationRule.Event.ALERT, MonitorNotificationRule.Event.ALL):
        return
    if rule.target_id:
        alerts = MonitorAlertEvent.objects.filter(target=rule.target, status=MonitorAlertEvent.Status.ACTIVE)
        for alert in alerts:
            notify_monitor_event(
                MonitorNotificationRule.Event.ALERT,
                target=rule.target,
                message=alert.message,
                alert_event=alert,
                only_rule=rule,
            )
    else:
        services = rule.services.all()
        if rule.all_services:
            services = ServiceMonitor.objects.filter(
                enabled=True,
                project__in=rule.channel.projects.all(),
            )
        for service in services:
            latest = service.events.first()
            if latest and latest.status == "down":
                notify_monitor_event(
                    MonitorNotificationRule.Event.ALERT,
                    service=service,
                    message=latest.message or "服务不可用",
                    response_time_ms=latest.response_time_ms,
                    service_event=latest,
                    only_rule=rule,
                )
