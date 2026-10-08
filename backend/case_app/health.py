"""Appium 执行节点健康检查与过期状态维护。"""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from .appium_client import AppiumClient
from .models import AppExecutionNode


def _probe_appium(server_url, timeout):
    try:
        return True, AppiumClient(server_url, timeout=timeout).status(), "Appium Server 已就绪"
    except Exception as exc:
        return False, None, str(exc)[:500]


def _store_probe_result(node, connected, message):
    if connected:
        node.status = "online"
        node.last_message = message
        node.last_seen_at = timezone.now()
    else:
        node.status = "offline"
        node.last_message = message
    node.save(update_fields=["status", "last_message", "last_seen_at", "updated_at"])


def check_appium_node(node, *, timeout=None):
    """探测单个 Appium 节点，并持久化本次健康状态。"""
    probe_timeout = timeout or settings.APPIUM_HEALTH_CHECK_TIMEOUT_SECONDS
    connected, value, message = _probe_appium(node.server_url, probe_timeout)
    _store_probe_result(node, connected, message)
    return connected, value


def check_appium_nodes(queryset=None):
    """周期探测全部启用节点；由统一监控任务每分钟调用。"""
    nodes = list(
        (queryset if queryset is not None else AppExecutionNode.objects.filter(enabled=True)).iterator()
    )
    result = {"checked": 0, "online": 0, "offline": 0, "errors": []}
    if not nodes:
        return result
    timeout = settings.APPIUM_HEALTH_CHECK_TIMEOUT_SECONDS
    with ThreadPoolExecutor(max_workers=min(8, len(nodes)), thread_name_prefix="appium-health") as executor:
        probes = executor.map(lambda node: _probe_appium(node.server_url, timeout), nodes)
    for node, (connected, _, message) in zip(nodes, probes):
        _store_probe_result(node, connected, message)
        result["checked"] += 1
        result["online" if connected else "offline"] += 1
        if not connected:
            result["errors"].append({"node": node.name, "message": node.last_message})
    return result


def refresh_stale_appium_nodes(queryset=None):
    """将超过心跳有效期仍标记在线的节点转为离线。"""
    cutoff = timezone.now() - timedelta(seconds=settings.APPIUM_NODE_OFFLINE_SECONDS)
    nodes = queryset if queryset is not None else AppExecutionNode.objects.filter(enabled=True)
    return nodes.filter(status="online").filter(
        Q(last_seen_at__isnull=True) | Q(last_seen_at__lt=cutoff)
    ).update(status="offline", last_message="心跳超时，Appium 节点可能未启动或不可达。")
