import requests
from django.conf import settings
from django.db.models import Q
from .models import NotificationDelivery, NotificationRule, RunResult


def validate_notification_response(platform, response):
    """同时校验 HTTP 与机器人平台业务码，返回（是否成功，失败原因）。"""
    if not response.ok:
        return False, f"HTTP {response.status_code}"
    try:
        data = response.json()
    except (TypeError, ValueError):
        return False, "HTTP 成功，但响应体不是有效 JSON"
    if not isinstance(data, dict):
        return False, "HTTP 成功，但响应体不是 JSON 对象"

    if platform == "lark":
        # 飞书新旧机器人接口分别使用 code、StatusCode；至少出现一个且所有已出现值均为 0。
        codes = [data[key] for key in ("code", "StatusCode") if key in data]
        if not codes:
            return False, "飞书响应缺少业务码 code/StatusCode"
        if all(str(code) == "0" for code in codes):
            return True, ""
        return False, f"飞书业务码异常：{codes[0]}"

    if platform == "wecom":
        if "errcode" not in data:
            return False, "企业微信响应缺少业务码 errcode"
        if str(data["errcode"]) == "0":
            return True, ""
        return False, f"企业微信业务码异常：{data['errcode']}"

    return False, f"不支持的通知平台：{platform}"


def notification_response_summary(response, validation_error=""):
    body = (response.text or "")[:500]
    if not validation_error:
        return body
    return f"{validation_error}；响应：{body}"[:500]


def notification_payload(platform, text, *, markdown_separator="\n> "):
    """统一机器人协议，调用方保留各自的正文格式。"""
    if platform == "lark":
        return {"msg_type": "text", "content": {"text": text}}
    return {"msgtype": "markdown", "markdown": {"content": text.replace("\n", markdown_separator)}}


def deliver_notification(channel, payload, delivery, *, timeout=8):
    """发送并保存投递结果；渠道选择和重试策略由业务模块负责。"""
    try:
        response = requests.post(channel.webhook_url, json=payload, timeout=timeout)
        succeeded, detail = validate_notification_response(channel.platform, response)
        delivery.response_code = response.status_code
        delivery.response_summary = notification_response_summary(response, detail)
        delivery.status = "sent" if succeeded else "failed"
    except Exception as exc:
        delivery.response_summary = str(exc)[:500]
    delivery.save(update_fields=["status", "response_code", "response_summary"])


def _format_duration(result, report):
    """将本次执行耗时格式化为“2分18秒”。"""
    duration_ms = report.get("duration_ms")
    if duration_ms is not None:
        try:
            seconds = max(0, round(float(duration_ms) / 1000))
        except (TypeError, ValueError):
            seconds = None
    elif result.started_at and result.finished_at:
        seconds = max(0, round((result.finished_at - result.started_at).total_seconds()))
    else:
        seconds = None

    if seconds is None:
        return "-"
    minutes, remaining_seconds = divmod(seconds, 60)
    return f"{minutes}分{remaining_seconds}秒" if minutes else f"{remaining_seconds}秒"


def _get_native_report_url(result):
    """返回可由飞书/企业微信直接打开的平台执行报告页。"""
    return f"{settings.REPORT_PUBLIC_BASE_URL}/suite/report/{result.id}"


def _build_notification_text(result, event):
    report = result.native_report or {}
    summary = report.get("summary") or {}
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    # 跳过、待执行步骤不参与通过率，避免中断任务被错误稀释。
    total = passed + failed
    try:
        pass_rate = round(float(passed) / float(total) * 100) if float(total) else 0
    except (TypeError, ValueError, ZeroDivisionError):
        pass_rate = 0

    environment = result.environment_name or (result.suite.environment.name if result.suite.environment_id else "-")
    execution_result = "成功" if event == NotificationRule.Event.SUCCEEDED else "失败"
    return "\n".join(
        [
            "自动化测试平台",
            f"执行结果：{execution_result}",
            f"套件：{result.suite.name}",
            f"环境：{environment}",
            f"耗时：{_format_duration(result, report)}",
            f"通过/失败：{passed} / {failed}",
            f"通过率：{pass_rate}%",
            f"报告详情：{_get_native_report_url(result)}",
        ]
    )


def notify_execution_result(result_id):
    result = RunResult.objects.select_related("suite", "suite__environment", "project").get(pk=result_id)
    event = NotificationRule.Event.SUCCEEDED if result.status == RunResult.RunStatus.Done and result.is_pass else NotificationRule.Event.FAILED
    rules = NotificationRule.objects.select_related("channel").filter(enabled=True, channel__enabled=True, channel__projects=result.project).filter(Q(event=event) | Q(event=NotificationRule.Event.ALL)).filter(Q(suite__isnull=True) | Q(suite=result.suite)).distinct()
    text = _build_notification_text(result, event)
    for rule in rules:
        payload = notification_payload(rule.channel.platform, text)
        delivery = NotificationDelivery.objects.create(result=result, channel=rule.channel, rule=rule, event=event, status=NotificationDelivery.Status.FAILED, payload=payload)
        deliver_notification(rule.channel, payload, delivery)
