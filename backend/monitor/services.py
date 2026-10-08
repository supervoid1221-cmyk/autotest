import json
import os
import re
import shlex
import socket
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse, urlunparse

import requests
from Tesla.ssh import configured_ssh_client, ssh_connection_options
from django.utils import timezone

from .models import MonitorAlertEvent, MonitorTarget, ServiceMonitorEvent

PROMETHEUS_TIMEOUT_SECONDS = 8
VALID_LABEL = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class PrometheusRequestError(ValueError):
    pass


def _selector(target):
    labels = {"job": target.job, "instance": target.instance_label, **(target.extra_labels or {})}
    safe_labels = {key: str(value) for key, value in labels.items() if VALID_LABEL.match(str(key)) and value is not None}
    return ",".join(f"{key}={json.dumps(value, ensure_ascii=False)}" for key, value in safe_labels.items())


def _ssh_client(server):
    try:
        import paramiko
    except ImportError as exc:
        raise PrometheusRequestError("服务端未安装 Paramiko，无法通过 SSH 查询 Prometheus。") from exc

    client = configured_ssh_client(paramiko, server.strict_host_key)
    options = ssh_connection_options(server.host, server.port, server.username, PROMETHEUS_TIMEOUT_SECONDS)
    if server.auth_type == "private_key":
        key_path = Path(os.path.expanduser(server.private_key_path))
        if not key_path.is_file():
            client.close()
            raise PrometheusRequestError(f"SSH 私钥文件不存在或不可访问：{key_path}")
        options.update({"key_filename": str(key_path), "passphrase": server.private_key_passphrase or None})
    else:
        options["password"] = server.password
    try:
        client.connect(**options)
        return client
    except Exception as exc:
        client.close()
        raise PrometheusRequestError(f"SSH 连接失败：{exc}") from exc


def _request_through_server(instance, server, url):
    """通过关联服务器在其本机请求 Prometheus，避免本机访问 Docker 内网地址。"""
    command = ["curl", "--silent", "--show-error", "--fail", "--connect-timeout", "5", "--max-time", str(PROMETHEUS_TIMEOUT_SECONDS)]
    if instance.access_token:
        command.extend(["-H", f"Authorization: Bearer {instance.access_token}"])
    command.append(url)
    client = _ssh_client(server)
    try:
        _, stdout, stderr = client.exec_command(" ".join(shlex.quote(item) for item in command), timeout=PROMETHEUS_TIMEOUT_SECONDS + 2)
        content = stdout.read().decode("utf-8", errors="replace")
        error = stderr.read().decode("utf-8", errors="replace").strip()
        exit_code = stdout.channel.recv_exit_status()
    except Exception as exc:
        raise PrometheusRequestError(f"通过 SSH 查询 Prometheus 失败：{exc}") from exc
    finally:
        client.close()
    if exit_code != 0:
        raise PrometheusRequestError(f"Prometheus 请求失败：{error or '远程 curl 请求失败'}")
    try:
        return json.loads(content)
    except ValueError as exc:
        raise PrometheusRequestError("Prometheus 返回了非 JSON 数据。") from exc


def _request(instance, path, params=None, server=None):
    headers = {"Authorization": f"Bearer {instance.access_token}"} if instance.access_token else {}
    url = f"{instance.base_url.rstrip('/')}{path}"
    if params:
        parsed = urlparse(url)
        url = urlunparse(parsed._replace(query=urlencode(params, doseq=True)))
    try:
        if server:
            payload = _request_through_server(instance, server, url)
        else:
            response = requests.get(url, headers=headers, timeout=PROMETHEUS_TIMEOUT_SECONDS)
            response.raise_for_status()
            payload = response.json()
    except PrometheusRequestError:
        raise
    except requests.RequestException as exc:
        raise PrometheusRequestError(f"Prometheus 请求失败：{exc}") from exc
    except ValueError as exc:
        raise PrometheusRequestError("Prometheus 返回了非 JSON 数据。") from exc
    if payload.get("status") != "success":
        raise PrometheusRequestError(payload.get("error") or "Prometheus 查询失败。")
    return payload.get("data") or {}


def test_instance(instance):
    _request(instance, "/api/v1/status/buildinfo")
    return True


def sync_cluster(cluster):
    try:
        data = _request(cluster.prometheus, "/api/v1/targets", {"state": "active"}, cluster.server)
        now, found, created, updated, skipped = timezone.now(), set(), 0, 0, 0
        for item in data.get("activeTargets") or []:
            labels = {**(item.get("discoveredLabels") or {}), **(item.get("labels") or {})}
            if cluster.job and labels.get("job") != cluster.job: continue
            if any(str(labels.get(k, "")) != str(v) for k, v in (cluster.label_rules or {}).items()): continue
            instance_label = str(labels.get(cluster.instance_label_key, "")).strip()
            if not instance_label: skipped += 1; continue
            found.add(instance_label)
            defaults = {"tenant": cluster.tenant, "cluster": cluster, "mode": "cluster", "discovered": True, "discovery_active": True, "discovery_labels": labels, "last_discovered_at": now, "project": cluster.project, "server": cluster.server, "name": str(labels.get(cluster.node_name_label) or labels.get("nodename") or instance_label), "job": cluster.job, "extra_labels": cluster.label_rules, "enabled": True, "cpu_warning_threshold": cluster.cpu_warning_threshold, "cpu_critical_threshold": cluster.cpu_critical_threshold, "memory_warning_threshold": cluster.memory_warning_threshold, "memory_critical_threshold": cluster.memory_critical_threshold, "disk_warning_threshold": cluster.disk_warning_threshold, "disk_critical_threshold": cluster.disk_critical_threshold}
            _, made = MonitorTarget.objects.update_or_create(prometheus=cluster.prometheus, instance_label=instance_label, defaults=defaults)
            created += int(made); updated += int(not made)
        offline = cluster.targets.filter(discovered=True).exclude(instance_label__in=found).update(discovery_active=False)
        result = {"created": created, "updated": updated, "offline": offline, "skipped": skipped, "matched": len(found)}
        cluster.last_synced_at, cluster.last_sync_status, cluster.last_sync_message = now, "success", json.dumps(result, ensure_ascii=False)
        cluster.save(update_fields=["last_synced_at", "last_sync_status", "last_sync_message", "updated_at"]); return result
    except Exception as exc:
        cluster.last_synced_at, cluster.last_sync_status, cluster.last_sync_message = timezone.now(), "failed", str(exc)[:512]
        cluster.save(update_fields=["last_synced_at", "last_sync_status", "last_sync_message", "updated_at"])
        raise exc if isinstance(exc, PrometheusRequestError) else PrometheusRequestError(f"集群节点同步失败：{exc}")


def _instant_value(target, query, reducer="first"):
    result = _request(target.prometheus, "/api/v1/query", {"query": query}, target.server).get("result") or []
    values = []
    for item in result:
        try:
            values.append(float(item["value"][1]))
        except (KeyError, IndexError, TypeError, ValueError):
            continue
    if not values:
        return None
    return max(values) if reducer == "max" else values[0]


def _series(target, query, seconds, start_timestamp=None, end_timestamp=None):
    end = float(end_timestamp) if end_timestamp is not None else timezone.now().timestamp()
    start = float(start_timestamp) if start_timestamp is not None else end - seconds
    range_seconds = max(300, int(end - start))
    data = _request(target.prometheus, "/api/v1/query_range", {
        "query": query,
        "start": start,
        "end": end,
        "step": max(15, min(3600, range_seconds // 240)),
    }, target.server)
    result = data.get("result") or []
    points = {}
    for item in result:
        for timestamp, value in item.get("values", []):
            try:
                timestamp = int(float(timestamp) * 1000)
                numeric = float(value)
                points[timestamp] = max(points.get(timestamp, numeric), numeric)
            except (TypeError, ValueError):
                continue
    return [{"timestamp": timestamp, "value": round(value, 2)} for timestamp, value in sorted(points.items())]


def metric_queries(target):
    selector = _selector(target)
    disk_selector = f'{selector},device!~"loop.*|ram.*|fd.*|sr.*"'
    return {
        "up": f"up{{{selector}}}",
        "cpu": f"100 - (avg by (instance) (rate(node_cpu_seconds_total{{{selector},mode=\"idle\"}}[5m])) * 100)",
        "memory": f"(1 - (node_memory_MemAvailable_bytes{{{selector}}} / node_memory_MemTotal_bytes{{{selector}}})) * 100",
        "disk": f"100 * (1 - (node_filesystem_avail_bytes{{{selector},fstype!~\"tmpfs|overlay|squashfs\"}} / node_filesystem_size_bytes{{{selector},fstype!~\"tmpfs|overlay|squashfs\"}}))",
        "disk_read_iops": f"sum by (instance) (rate(node_disk_reads_completed_total{{{disk_selector}}}[5m]))",
        "disk_write_iops": f"sum by (instance) (rate(node_disk_writes_completed_total{{{disk_selector}}}[5m]))",
        "disk_iops": (
            f"sum by (instance) (rate(node_disk_reads_completed_total{{{disk_selector}}}[5m])) + "
            f"sum by (instance) (rate(node_disk_writes_completed_total{{{disk_selector}}}[5m]))"
        ),
    }


def snapshot(target, include_series=False, range_seconds=3600, start_timestamp=None, end_timestamp=None):
    queries = metric_queries(target)
    values = {
        "up": _instant_value(target, queries["up"]),
        "cpu": _instant_value(target, queries["cpu"]),
        "memory": _instant_value(target, queries["memory"]),
        "disk": _instant_value(target, queries["disk"], reducer="max"),
        "disk_read_iops": _instant_value(target, queries["disk_read_iops"]),
        "disk_write_iops": _instant_value(target, queries["disk_write_iops"]),
        "disk_iops": _instant_value(target, queries["disk_iops"]),
    }
    values = {key: (round(value, 2) if value is not None else None) for key, value in values.items()}
    result = {"current": values, "series": {}}
    if include_series:
        result["series"] = {
            key: _series(target, query, range_seconds, start_timestamp, end_timestamp)
            for key, query in queries.items()
            if key != "up"
        }
        effective_end = float(end_timestamp) if end_timestamp is not None else timezone.now().timestamp()
        effective_start = float(start_timestamp) if start_timestamp is not None else effective_end - range_seconds
        result["range"] = {"start": int(effective_start * 1000), "end": int(effective_end * 1000)}
    return result


def evaluate_alerts(target, values):
    rules = [
        ("host_down", "主机离线", values.get("up") is None or values.get("up") < 1, None, "critical"),
        ("cpu", "CPU 使用率", values.get("cpu"), target.cpu_warning_threshold, target.cpu_critical_threshold),
        ("memory", "内存使用率", values.get("memory"), target.memory_warning_threshold, target.memory_critical_threshold),
        ("disk", "磁盘使用率", values.get("disk"), target.disk_warning_threshold, target.disk_critical_threshold),
    ]
    for key, label, value, warning, critical in rules:
        if key == "host_down":
            active, severity, threshold = bool(value), "critical", None
        else:
            active = value is not None and value >= warning
            severity = "critical" if active and value >= critical else "warning"
            threshold = critical if severity == "critical" else warning
        existing = MonitorAlertEvent.objects.filter(target=target, alert_key=key, status="active").first()
        if active and existing:
            existing.severity, existing.metric_value, existing.threshold = severity, value, threshold
            existing.message = f"{label} 当前 {value if value is not None else '-'}{'%' if value is not None else ''}"
            existing.save(update_fields=["severity", "metric_value", "threshold", "message"])
            # 兜底处理“告警先产生、通知规则后配置”的场景。通知层会按告警事件去重，
            # 已成功发送的不再重复，失败投递按间隔重试。
            from .notifications import notify_monitor_event
            notify_monitor_event("alert", target=target, message=existing.message, alert_event=existing)
        elif active:
            event = MonitorAlertEvent.objects.create(target=target, alert_key=key, severity=severity, metric_value=value, threshold=threshold, message=f"{label} 当前 {value if value is not None else '-'}{'%' if value is not None else ''}")
            from .notifications import notify_monitor_event
            notify_monitor_event("alert", target=target, message=event.message, alert_event=event)
        elif existing:
            existing.status = "recovered"
            existing.recovered_at = timezone.now()
            existing.save(update_fields=["status", "recovered_at"])
            from .notifications import notify_monitor_event
            notify_monitor_event("recovered", target=target, message=f"{label} 已恢复正常", alert_event=existing)


def _remote_service_check(service):
    """在关联服务器中检查仅该服务器可访问的 HTTP/TCP 服务。"""
    timeout = str(service.timeout_seconds)
    if service.monitor_type == "http":
        command = [
            "curl", "--silent", "--show-error", "--output", "/dev/null",
            "--write-out", "%{http_code} %{time_total}", "--connect-timeout", timeout,
            "--max-time", timeout, service.address,
        ]
    elif service.monitor_type == "tcp":
        command = ["bash", "-lc", f"timeout {shlex.quote(timeout)} bash -c '</dev/tcp/{service.address}/{int(service.port)}'"]
    else:
        command = ["docker", "inspect", "--format", "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}", service.address]
    client = _ssh_client(service.server)
    try:
        started = time.perf_counter()
        _, stdout, stderr = client.exec_command(" ".join(shlex.quote(item) for item in command), timeout=service.timeout_seconds + 2)
        output = stdout.read().decode("utf-8", errors="replace").strip()
        error = stderr.read().decode("utf-8", errors="replace").strip()
        exit_code = stdout.channel.recv_exit_status()
        elapsed = max(1, round((time.perf_counter() - started) * 1000))
    finally:
        client.close()
    if service.monitor_type == "http" and exit_code == 0:
        try:
            status_code, seconds = output.split(maxsplit=1)
            return {"up": True, "status_code": int(status_code), "response_time_ms": round(float(seconds) * 1000), "message": ""}
        except (ValueError, TypeError):
            return {"up": False, "status_code": None, "response_time_ms": elapsed, "message": "远程 HTTP 检测返回格式异常。"}
    if service.monitor_type == "docker":
        states = output.split()
        container_state = states[0] if states else "unknown"
        health_state = states[1] if len(states) > 1 else ""
        up = exit_code == 0 and container_state == "running" and health_state not in {"unhealthy", "starting"}
        message = error or f"容器状态：{container_state}{f' / 健康检查：{health_state}' if health_state else ''}"
        return {"up": up, "status_code": None, "response_time_ms": elapsed, "message": message}
    return {"up": exit_code == 0, "status_code": None, "response_time_ms": elapsed, "message": error or ("TCP 端口可连接" if exit_code == 0 else "TCP 端口不可连接")}


def service_snapshot(service):
    """检测单个业务服务，所有连接问题统一转换为可展示状态。"""
    try:
        if service.server_id:
            result = _remote_service_check(service)
        else:
            started = time.perf_counter()
            if service.monitor_type == "http":
                response = requests.get(service.address, timeout=service.timeout_seconds, allow_redirects=True)
                result = {"up": True, "status_code": response.status_code, "response_time_ms": max(1, round((time.perf_counter() - started) * 1000)), "message": ""}
            elif service.monitor_type == "tcp":
                with socket.create_connection((service.address, int(service.port)), timeout=service.timeout_seconds):
                    pass
                result = {"up": True, "status_code": None, "response_time_ms": max(1, round((time.perf_counter() - started) * 1000)), "message": "TCP 端口可连接"}
            else:
                result = {"up": False, "status_code": None, "response_time_ms": None, "message": "Docker 容器监控必须关联服务器。"}
    except Exception as exc:
        result = {"up": False, "status_code": None, "response_time_ms": None, "message": str(exc)}
    expected = service.expected_status_codes or [200]
    if result["up"] and service.monitor_type == "http" and result["status_code"] not in expected:
        result["up"] = False
        result["message"] = f"HTTP 状态码 {result['status_code']}，期望 {', '.join(map(str, expected))}"
    return result


def record_service_status(service, data):
    """仅在服务状态发生变化时记录事件。"""
    status = "up" if data["up"] else "down"
    latest = service.events.first()
    if not latest or latest.status != status:
        event = ServiceMonitorEvent.objects.create(
            service=service,
            status=status,
            message=data.get("message", "")[:512],
            response_time_ms=data.get("response_time_ms"),
        )
        # 首次检测在线仅建立基线，不发送无意义的“恢复”消息；首次异常应立即告警。
        if status == "down" or latest:
            from .notifications import notify_monitor_event
            notify_monitor_event(
                "alert" if status == "down" else "recovered",
                service=service,
                message=event.message or ("服务不可用" if status == "down" else "服务已恢复"),
                response_time_ms=event.response_time_ms,
                service_event=event,
            )
        return event
    return None
