from suite.notifications import deliver_notification, notification_payload
from .models import PerformanceNotificationDelivery, PerformanceRun


def notify_performance_run(run_id):
    run = PerformanceRun.objects.select_related("scenario", "project", "environment").get(pk=run_id)
    status_label = run.get_status_display()
    text = (
        f"性能测试任务完成\n"
        f"项目：{run.project.name}\n"
        f"场景：{run.scenario.name}\n"
        f"环境：{run.environment.name}\n"
        f"执行编号：{run.execution_no}\n"
        f"状态：{status_label}"
    )
    for channel in run.scenario.notification_channels.filter(enabled=True):
        payload = notification_payload(channel.platform, text, markdown_separator="  \n")
        delivery = PerformanceNotificationDelivery.objects.create(
            run=run,
            channel=channel,
            status=PerformanceNotificationDelivery.Status.FAILED,
        )
        deliver_notification(channel, payload, delivery, timeout=10)
