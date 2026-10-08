import json
import math
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone as datetime_timezone
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from account.tenant_runtime import tenant_path

from project.models import ProjectVariable
from .models import PerformanceEndpointMetric, PerformanceMetricBucket, PerformanceRun


def _duration_seconds(value):
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(ms|s|m|h)\s*", str(value or ""), re.I)
    if not match:
        raise ValueError(f"不支持的持续时间：{value}")
    number, unit = float(match.group(1)), match.group(2).lower()
    return max(1, int(number * {"ms": 0.001, "s": 1, "m": 60, "h": 3600}[unit]))


def _percentile(values, percentile):
    if not values:
        return 0
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile / 100
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _safe_name(value):
    return re.sub(r"[^0-9A-Za-z_.-]+", "_", str(value or "endpoint"))[:80]


def _metric_datetime(value):
    """将 k6 ISO 时间转换为与当前 Django USE_TZ 配置一致的时间。"""
    occurred = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if settings.USE_TZ:
        if timezone.is_naive(occurred):
            return timezone.make_aware(occurred, datetime_timezone.utc)
        return occurred
    if timezone.is_aware(occurred):
        return timezone.make_naive(occurred, timezone.get_default_timezone())
    return occurred


def _threshold_results(summary):
    """统一兼容 k6 legacy 布尔格式与新版包含 ok 字段的汇总格式。"""
    normalized = {}
    for metric_name, metric in (summary.get("metrics") or {}).items():
        rules = metric.get("thresholds") or {}
        if not rules:
            continue
        normalized[metric_name] = {}
        for rule, result in rules.items():
            if isinstance(result, dict):
                passed = bool(result.get("ok"))
            else:
                # legacy --summary-export 中布尔值表示“是否失败”：false 为通过。
                passed = not bool(result)
            normalized[metric_name][rule] = {"ok": passed}
    return normalized


def _summary_metric(summary, name, key):
    """兼容 k6 新旧汇总结构读取聚合指标。"""
    metric = (summary.get("metrics") or {}).get(name) or {}
    values = metric.get("values") or metric
    try:
        return float(values.get(key) or 0)
    except (AttributeError, TypeError, ValueError):
        return 0


def build_script(run):
    scenario = run.scenario
    execution = run.execution_config or {}
    load_mode = execution.get("load_mode") or getattr(scenario, "load_mode", "stages")
    stages = execution.get("stages") or scenario.stages or [{"duration": "1m", "target": 1}]
    thresholds = execution.get("thresholds") or scenario.thresholds or {}
    p95 = float(thresholds.get("p95_ms", 500))
    error_rate = float(thresholds.get("error_rate", 1)) / 100
    minimum_rps = float(thresholds.get("minimum_rps", 0))
    k6_thresholds = {
        "http_req_duration": [f"p(95)<{p95:g}"],
        "http_req_failed": [f"rate<{error_rate:g}"],
    }
    if minimum_rps > 0:
        k6_thresholds["http_reqs"] = [f"rate>{minimum_rps:g}"]
    snapshot = scenario.scenario_snapshot or {}
    groups = execution.get("groups") or snapshot.get("groups") or [{"key": f"{snapshot.get('source_type', 'scenario')}-{snapshot.get('source_id', scenario.id)}", "name": snapshot.get("source_name") or scenario.name, "weight": 100, "steps": snapshot.get("steps", [])}]
    if load_mode == "thread_group":
        thread_count = int(execution.get("thread_count") or scenario.thread_count)
        duration_seconds = int(execution.get("duration_seconds") or scenario.duration_seconds)
        ramp_up_seconds = int(execution.get("ramp_up_seconds") if execution.get("ramp_up_seconds") is not None else scenario.ramp_up_seconds)
        graceful_stop_seconds = int(execution.get("graceful_stop_seconds") if execution.get("graceful_stop_seconds") is not None else scenario.graceful_stop_seconds)
        if ramp_up_seconds:
            k6_options = {"scenarios": {"thread_group": {"executor": "ramping-vus", "startVUs": 0, "stages": [{"duration": f"{ramp_up_seconds}s", "target": thread_count}, {"duration": f"{duration_seconds}s", "target": thread_count}], "gracefulStop": f"{graceful_stop_seconds}s"}}, "thresholds": k6_thresholds}
        else:
            k6_options = {"scenarios": {"thread_group": {"executor": "constant-vus", "vus": thread_count, "duration": f"{duration_seconds}s", "gracefulStop": f"{graceful_stop_seconds}s"}}, "thresholds": k6_thresholds}
    else:
        k6_options = {"stages": stages, "thresholds": k6_thresholds}
    config = {
        "loadMode": load_mode,
        "groups": groups,
        "parameterData": execution.get("parameter_data", scenario.parameter_data) or [],
        "parameterStrategy": execution.get("parameter_strategy") or scenario.parameter_strategy,
        "baseUrl": execution.get("base_url") or run.environment.base_url.rstrip("/"),
    }
    encoded = json.dumps(config, ensure_ascii=False).replace("</", "<\\/")
    encoded_options = json.dumps(k6_options, ensure_ascii=False).replace("</", "<\\/")
    return f'''import http from 'k6/http';
import {{ check, fail }} from 'k6';
import exec from 'k6/execution';

const config = {encoded};
const runtimeVariables = JSON.parse(__ENV.PERF_VARIABLES_JSON || '{{}}');
const authHeader = __ENV.PERF_AUTH_HEADER || '';
const authValue = __ENV.PERF_AUTH_VALUE || '';

export const options = {encoded_options};

function resolve(value) {{
  if (typeof value === 'string') return value.replace(/\$\{{([^}}]+)\}}/g, (_, key) => runtimeVariables[key] ?? '');
  if (Array.isArray(value)) return value.map(resolve);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, resolve(v)]));
  return value;
}}

function jsonPath(data, path) {{
  if (!path || path === '$' || path === '$.') return data;
  const parts = String(path).replace(/^\$\.?/, '').replace(/\[(\d+)\]/g, '.$1').split('.').filter(Boolean);
  return parts.reduce((value, key) => value == null ? undefined : value[key], data);
}}

function appendQuery(url, params) {{
  const entries = Object.entries(resolve(params || {{}}));
  if (!entries.length) return url;
  const query = entries.map(([key, value]) => `${{encodeURIComponent(key)}}=${{encodeURIComponent(value)}}`).join('&');
  return `${{url}}${{url.includes('?') ? '&' : '?'}}${{query}}`;
}}

function compare(operator, actual, expected) {{
  if (operator === 'equals') return String(actual) === String(expected);
  if (operator === 'not_equals') return String(actual) !== String(expected);
  if (operator === 'contains') return String(actual).includes(String(expected));
  if (operator === 'not_contains') return !String(actual).includes(String(expected));
  if (operator === 'greater_than') return Number(actual) > Number(expected);
  if (operator === 'less_than') return Number(actual) < Number(expected);
  return true;
}}

function parameterRow() {{
  if (!config.parameterData.length) return {{}};
  if (config.parameterStrategy === 'random') {{
    return config.parameterData[Math.floor(Math.random() * config.parameterData.length)];
  }}
  const index = exec.scenario.iterationInTest;
  if (config.parameterStrategy === 'unique' && index >= config.parameterData.length) {{
    fail(`参数化数据已耗尽：共 ${{config.parameterData.length}} 行`);
  }}
  return config.parameterData[index % config.parameterData.length];
}}

function selectBusiness() {{
  const total = config.groups.reduce((sum, item) => sum + Number(item.weight || 0), 0);
  let cursor = config.loadMode === 'thread_group'
    ? (exec.scenario.iterationInTest % total) + 1
    : Math.random() * total;
  for (const group of config.groups) {{
    cursor -= Number(group.weight || 0);
    if (cursor <= 0) return group;
  }}
  return config.groups[config.groups.length - 1];
}}

export default function () {{
  Object.assign(runtimeVariables, parameterRow());
  const business = selectBusiness();
  for (const step of business.steps) {{
    const request = step.request || {{}};
    let url = resolve(request.url || '');
    if (!/^https?:\/\//.test(url)) url = `${{config.baseUrl}}/${{url.replace(/^\/+/, '')}}`;
    url = appendQuery(url, request.params);
    const headers = resolve(request.headers || {{}});
    if (authHeader && authValue) headers[authHeader] = authValue;
    let body = null;
    if (request.json && Object.keys(request.json).length) {{
      body = JSON.stringify(resolve(request.json));
      if (!Object.keys(headers).some(key => key.toLowerCase() === 'content-type')) headers['Content-Type'] = 'application/json';
    }} else if (request.data && Object.keys(request.data).length) body = resolve(request.data);
    const endpointName = step.name;
    const response = http.request(request.method || 'GET', url, body, {{ headers, tags: {{ name: `${{request.method || 'GET'}} ${{endpointName}}`, business: business.name }} }});
    let payload = {{}};
    try {{ payload = response.json(); }} catch (_) {{ payload = {{}}; }}
    const context = Object.assign({{ status_code: response.status, body: response.body }}, payload || {{}});
    let passed = true;
    for (const [operator, assertions] of Object.entries(step.validate || {{}})) {{
      for (const [label, pair] of Object.entries(assertions || {{}})) {{
        const actual = jsonPath(context, pair[0]);
        const expected = resolve(pair[1]);
        const result = check(response, {{ [label]: () => compare(operator, actual, expected) }});
        passed = passed && result;
      }}
    }}
    for (const [name, spec] of Object.entries(step.extract || {{}})) {{
      const expression = Array.isArray(spec) ? spec[1] : spec.expression;
      const index = Array.isArray(spec) ? Number(spec[2] || 0) : Number(spec.index || 0);
      const value = jsonPath(context, expression);
      runtimeVariables[name] = Array.isArray(value) ? value[index] : value;
    }}
    if (!passed && !step.continue_on_failure) fail(`步骤 ${{step.name}} 断言失败`);
  }}
}}
'''


def _runtime_environment(run, work_dir):
    variables = ProjectVariable.values_for_projects([run.project_id])
    auth_headers = {}
    if run.environment.auth_enabled:
        # prepare_auth 会按既有执行协议写一份变量文件。性能任务只需要认证头，
        # 因此使用自动销毁的临时目录，避免 Token 明文留在性能报告目录。
        with tempfile.TemporaryDirectory(prefix="performance-auth-") as directory:
            auth_headers = run.environment.prepare_auth(Path(directory), "default")
    process_env = dict(os.environ)
    process_env["PLATFORM_TENANT_ID"] = str(run.tenant_id)
    process_env["PERF_VARIABLES_JSON"] = json.dumps(variables, ensure_ascii=False, default=str)
    if auth_headers:
        header, value = next(iter(auth_headers.items()))
        process_env["PERF_AUTH_HEADER"] = str(header)
        process_env["PERF_AUTH_VALUE"] = str(value)
    return process_env


def _parse_points(path):
    buckets = defaultdict(lambda: {"vus": [], "requests": 0, "iterations": 0, "failed": 0, "durations": []})
    endpoints = defaultdict(lambda: {"requests": 0, "failed": 0, "durations": [], "method": "", "url": "", "business": "", "received": 0, "sent": 0})
    if not path.exists():
        return buckets, endpoints
    last_endpoint_name = None
    with path.open(encoding="utf-8", errors="replace") as stream:
        for line in stream:
            try:
                item = json.loads(line)
            except (ValueError, TypeError):
                continue
            if item.get("type") != "Point":
                continue
            metric = item.get("metric")
            data = item.get("data") or {}
            try:
                occurred = _metric_datetime(data.get("time"))
                bucket_time = occurred.replace(second=occurred.second - occurred.second % 5, microsecond=0)
                value = float(data.get("value", 0))
            except (ValueError, TypeError):
                continue
            bucket = buckets[bucket_time]
            tags = data.get("tags") or {}
            endpoint_name = str(tags.get("name") or "未命名接口")
            if metric == "vus":
                bucket["vus"].append(value)
            elif metric == "http_reqs":
                bucket["requests"] += int(value)
            elif metric == "iterations":
                bucket["iterations"] += int(value)
            elif metric == "http_req_failed":
                bucket["failed"] += int(value >= 1)
            elif metric == "http_req_duration":
                bucket["durations"].append(value)
                last_endpoint_name = endpoint_name
                endpoints[endpoint_name]["requests"] += 1
                endpoints[endpoint_name]["durations"].append(value)
                endpoints[endpoint_name]["method"] = str(tags.get("method") or "")
                endpoints[endpoint_name]["url"] = str(tags.get("url") or "")[:512]
                endpoints[endpoint_name]["business"] = str(tags.get("business") or "")
            elif metric == "data_received" and last_endpoint_name:
                endpoints[last_endpoint_name]["received"] += max(0, int(value))
            elif metric == "data_sent" and last_endpoint_name:
                endpoints[last_endpoint_name]["sent"] += max(0, int(value))
            if metric == "http_req_failed":
                endpoints[endpoint_name]["failed"] += int(value >= 1)
    return buckets, endpoints


def _target_vus_for_bucket(run, timestamp):
    """计算 5 秒采样桶结束时刻的计划并发用户数。"""
    if not run.load_started_at:
        return 0
    elapsed = max(0, (timestamp + timedelta(seconds=5) - run.load_started_at).total_seconds())
    execution = run.execution_config or {}
    if execution.get("load_mode") == "thread_group":
        thread_count = float(execution.get("thread_count") or 0)
        ramp_up_seconds = float(execution.get("ramp_up_seconds") or 0)
        duration_seconds = float(execution.get("duration_seconds") or 0)
        if ramp_up_seconds > 0 and elapsed < ramp_up_seconds:
            return thread_count * elapsed / ramp_up_seconds
        return thread_count if elapsed <= ramp_up_seconds + duration_seconds else 0

    previous_target = 0.0
    stage_started_at = 0.0
    for stage in execution.get("stages") or run.scenario.stages or []:
        stage_duration = float(_duration_seconds(stage.get("duration")))
        stage_target = float(stage.get("target") or 0)
        stage_finished_at = stage_started_at + stage_duration
        if elapsed <= stage_finished_at:
            progress = min(1, max(0, (elapsed - stage_started_at) / stage_duration))
            return previous_target + (stage_target - previous_target) * progress
        previous_target = stage_target
        stage_started_at = stage_finished_at
    return previous_target


def _save_metrics(run, metrics_path, elapsed_seconds=1):
    buckets, endpoints = _parse_points(metrics_path)
    PerformanceMetricBucket.objects.filter(run=run).delete()
    records = []
    for timestamp, values in sorted(buckets.items()):
        durations = values["durations"]
        count = values["requests"] or len(durations)
        failed = values["failed"]
        records.append(PerformanceMetricBucket(
            run=run, timestamp=timestamp, vus=max(values["vus"] or [0]), target_vus=_target_vus_for_bucket(run, timestamp), rps=count / 5,
            tps=values["iterations"] / 5,
            request_count=count, failed_count=failed, error_rate=(failed / count * 100) if count else 0,
            duration_avg=sum(durations) / len(durations) if durations else 0,
            duration_min=min(durations or [0]), duration_max=max(durations or [0]),
            duration_p90=_percentile(durations, 90), duration_p95=_percentile(durations, 95), duration_p99=_percentile(durations, 99),
        ))
    PerformanceMetricBucket.objects.bulk_create(records)
    PerformanceEndpointMetric.objects.filter(run=run).delete()
    endpoint_records = []
    total_requests = sum(max(values["requests"], len(values["durations"])) for values in endpoints.values())
    groups = (run.execution_config or {}).get("groups") or []
    total_weight = sum(float(item.get("weight") or 0) for item in groups) or 100
    configured_ratios = {str(item.get("name") or ""): float(item.get("weight") or 0) / total_weight * 100 for item in groups}
    for name, values in endpoints.items():
        durations = values["durations"]
        count = max(values["requests"], len(durations))
        parts = name.split(" ", 1)
        endpoint_records.append(PerformanceEndpointMetric(
            run=run, endpoint_name=parts[1] if len(parts) > 1 else name,
            method=values["method"] or (parts[0] if len(parts) > 1 else ""), url=values["url"],
            request_count=count, failed_count=values["failed"], error_rate=(values["failed"] / count * 100) if count else 0,
            duration_avg=sum(durations) / len(durations) if durations else 0,
            duration_min=min(durations or [0]), duration_median=_percentile(durations, 50), duration_max=max(durations or [0]),
            duration_p90=_percentile(durations, 90), duration_p95=_percentile(durations, 95), duration_p99=_percentile(durations, 99),
            throughput=count / max(elapsed_seconds, 1),
            received_bytes=values["received"], sent_bytes=values["sent"],
            configured_ratio=configured_ratios.get(values["business"], 100 if len(endpoints) == 1 else 0),
        ))
    PerformanceEndpointMetric.objects.bulk_create(endpoint_records)
    all_durations = [duration for values in endpoints.values() for duration in values["durations"]]
    return {
        "duration_p99": _percentile(all_durations, 99),
        "duration_median": _percentile(all_durations, 50),
        "duration_p90": _percentile(all_durations, 90),
    }


def _consume_live_points(path, offset, accumulators, endpoint_accumulators, run, elapsed_seconds):
    """增量消费 k6 JSON，同步更新 5 秒趋势桶和接口聚合指标。"""
    if not path.exists():
        return offset, 0, 0, 0
    with path.open("rb") as stream:
        stream.seek(offset)
        chunk = stream.read()
    complete_end = chunk.rfind(b"\n")
    if complete_end < 0:
        return offset, 0, 0, 0
    payload = chunk[:complete_end + 1]
    new_offset = offset + complete_end + 1
    dirty = set()
    for raw_line in payload.splitlines():
        try:
            item = json.loads(raw_line.decode("utf-8", errors="ignore"))
            if item.get("type") != "Point":
                continue
            data = item.get("data") or {}
            metric = item.get("metric")
            occurred = _metric_datetime(data.get("time"))
            bucket_time = occurred.replace(second=occurred.second - occurred.second % 5, microsecond=0)
            value = float(data.get("value", 0))
            bucket = accumulators[bucket_time]
            dirty.add(bucket_time)
            tags = data.get("tags") or {}
            raw_endpoint_name = str(tags.get("name") or "")
            endpoint = endpoint_accumulators[raw_endpoint_name] if raw_endpoint_name else None
            if metric == "vus":
                bucket["vus"].append(value)
            elif metric == "http_reqs":
                bucket["requests"] += int(value)
            elif metric == "iterations":
                bucket["iterations"] += int(value)
            elif metric == "http_req_failed":
                bucket["failed"] += int(value >= 1)
                if endpoint is not None:
                    endpoint["failed"] += int(value >= 1)
            elif metric == "http_req_duration":
                bucket["durations"].append(value)
                if endpoint is not None:
                    endpoint["requests"] += 1
                    endpoint["durations"].append(value)
                    endpoint["method"] = str(tags.get("method") or "")
                    endpoint["url"] = str(tags.get("url") or "")[:512]
                    endpoint["business"] = str(tags.get("business") or "")
            elif metric == "data_received" and endpoint is not None:
                endpoint["received"] += max(0, int(value))
            elif metric == "data_sent" and endpoint is not None:
                endpoint["sent"] += max(0, int(value))
        except (ValueError, TypeError):
            continue
    for timestamp in dirty:
        values = accumulators[timestamp]
        durations = values["durations"]
        count = values["requests"] or len(durations)
        failed = values["failed"]
        PerformanceMetricBucket.objects.update_or_create(
            run=run, timestamp=timestamp,
            defaults={
                "vus": max(values["vus"] or [0]), "target_vus": _target_vus_for_bucket(run, timestamp), "rps": count / 5,
                "tps": values["iterations"] / 5,
                "request_count": count, "failed_count": failed,
                "error_rate": (failed / count * 100) if count else 0,
                "duration_avg": sum(durations) / len(durations) if durations else 0,
                "duration_min": min(durations or [0]), "duration_max": max(durations or [0]),
                "duration_p90": _percentile(durations, 90), "duration_p95": _percentile(durations, 95),
                "duration_p99": _percentile(durations, 99),
            },
        )
    groups = (run.execution_config or {}).get("groups") or []
    total_weight = sum(float(item.get("weight") or 0) for item in groups) or 100
    configured_ratios = {
        str(item.get("name") or ""): float(item.get("weight") or 0) / total_weight * 100
        for item in groups
    }
    for raw_name, values in endpoint_accumulators.items():
        durations = values["durations"]
        count = max(values["requests"], len(durations))
        parts = raw_name.split(" ", 1)
        endpoint_name = parts[1] if len(parts) > 1 else raw_name
        PerformanceEndpointMetric.objects.update_or_create(
            run=run,
            endpoint_name=endpoint_name,
            defaults={
                "method": values["method"] or (parts[0] if len(parts) > 1 else ""),
                "url": values["url"],
                "request_count": count,
                "failed_count": values["failed"],
                "error_rate": (values["failed"] / count * 100) if count else 0,
                "duration_avg": sum(durations) / len(durations) if durations else 0,
                "duration_min": min(durations or [0]),
                "duration_median": _percentile(durations, 50),
                "duration_max": max(durations or [0]),
                "duration_p90": _percentile(durations, 90),
                "duration_p95": _percentile(durations, 95),
                "duration_p99": _percentile(durations, 99),
                "throughput": count / max(elapsed_seconds, 1),
                "received_bytes": values["received"],
                "sent_bytes": values["sent"],
                "configured_ratio": configured_ratios.get(
                    values["business"], 100 if len(endpoint_accumulators) == 1 else 0
                ),
            },
        )
    if not accumulators:
        return new_offset, 0, 0, 0
    latest = accumulators[max(accumulators)]
    return (
        new_offset,
        max(latest["vus"] or [0]),
        (latest["requests"] or len(latest["durations"])) / 5,
        latest["iterations"] / 5,
    )


def execute_run(run_id, tenant_id=None):
    run = PerformanceRun.objects.select_related("scenario", "project", "environment").get(pk=run_id)
    if tenant_id is not None and str(run.tenant_id) != str(tenant_id):
        raise ValueError("执行任务租户与性能执行记录不一致。")
    if run.status not in {PerformanceRun.Status.QUEUED, PerformanceRun.Status.PREPARING}:
        return
    run.status = PerformanceRun.Status.PREPARING
    run.started_at = timezone.now()
    run.save(update_fields=["status", "started_at", "updated_at"])
    base_dir = tenant_path(
        Path(settings.BASE_DIR) / "performance_runs", run.tenant_id, run.execution_no
    )
    base_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    base_dir.chmod(0o700)
    run.work_dir = str(base_dir)
    run.save(update_fields=["work_dir", "updated_at"])
    script_path = base_dir / "script.js"
    metrics_path = base_dir / "metrics.json"
    summary_path = base_dir / "summary.json"
    log_path = base_dir / "runner.log"
    process = None
    try:
        if not shutil.which("k6"):
            raise RuntimeError("服务器未安装 k6，请安装 k6 或使用包含 k6 的平台镜像。")
        script_path.write_text(build_script(run), encoding="utf-8")
        script_path.chmod(0o600)
        process_env = _runtime_environment(run, base_dir)
        execution = run.execution_config or {}
        if execution.get("load_mode") == "thread_group":
            duration = int(execution.get("duration_seconds") or 1) + int(execution.get("ramp_up_seconds") or 0)
        else:
            duration = sum(_duration_seconds(item.get("duration")) for item in (execution.get("stages") or run.scenario.stages or []))
        command = ["k6", "run", "--out", f"json={metrics_path}", "--summary-export", str(summary_path), str(script_path)]
        with log_path.open("a", encoding="utf-8") as log:
            process = subprocess.Popen(command, cwd=base_dir, env=process_env, stdout=log, stderr=subprocess.STDOUT, text=True)
            started = time.monotonic()
            run.status = PerformanceRun.Status.RUNNING
            run.process_id = process.pid
            run.load_started_at = timezone.now()
            run.load_finished_at = None
            run.load_duration_ms = None
            run.save(update_fields=["status", "process_id", "load_started_at", "load_finished_at", "load_duration_ms", "updated_at"])
            last_live_update = 0
            metrics_offset = 0
            live_accumulators = defaultdict(lambda: {"vus": [], "requests": 0, "iterations": 0, "failed": 0, "durations": []})
            live_endpoint_accumulators = defaultdict(lambda: {"requests": 0, "failed": 0, "durations": [], "method": "", "url": "", "business": "", "received": 0, "sent": 0})
            while process.poll() is None:
                time.sleep(1)
                run.refresh_from_db(fields=["stop_requested"])
                if run.stop_requested:
                    process.send_signal(signal.SIGTERM)
                    break
                progress = min(99, int((time.monotonic() - started) / max(duration, 1) * 100))
                run.progress = progress
                if time.monotonic() - last_live_update >= 5:
                    metrics_offset, run.current_vus, run.current_rps, run.current_tps = _consume_live_points(
                        metrics_path,
                        metrics_offset,
                        live_accumulators,
                        live_endpoint_accumulators,
                        run,
                        max(time.monotonic() - started, 1),
                    )
                    last_live_update = time.monotonic()
                run.save(update_fields=["progress", "current_vus", "current_rps", "current_tps", "updated_at"])
            try:
                return_code = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                return_code = process.wait()
        run.load_finished_at = timezone.now()
        run.load_duration_ms = max(0, round((time.monotonic() - started) * 1000))
        run.status = PerformanceRun.Status.REPORTING
        run.process_id = None
        run.save(update_fields=["status", "process_id", "load_finished_at", "load_duration_ms", "updated_at"])
        aggregate_summary = _save_metrics(run, metrics_path, max(time.monotonic() - started, 1))
        summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
        summary["aggregate"] = aggregate_summary
        k6_duration_ms = round(float((summary.get("state") or {}).get("testRunDurationMs") or 0))
        if k6_duration_ms > 0:
            run.load_duration_ms = k6_duration_ms
            if run.load_started_at:
                run.load_finished_at = run.load_started_at + timedelta(milliseconds=k6_duration_ms)
        for artifact_path in (metrics_path, summary_path, log_path):
            if artifact_path.exists():
                artifact_path.chmod(0o600)
        threshold_results = _threshold_results(summary)
        threshold_failed = any(not result.get("ok", False) for results in threshold_results.values() for result in results.values())
        run.summary = summary
        run.threshold_results = threshold_results
        run.progress = 100
        run.current_rps = _summary_metric(summary, "http_reqs", "rate")
        run.current_tps = _summary_metric(summary, "iterations", "rate")
        run.finished_at = timezone.now()
        if run.stop_requested:
            run.status = PerformanceRun.Status.STOPPED
        elif return_code == 0 and not threshold_failed:
            run.status = PerformanceRun.Status.PASSED
        else:
            run.status = PerformanceRun.Status.FAILED
        run.save(update_fields=["summary", "threshold_results", "progress", "current_rps", "current_tps", "load_finished_at", "load_duration_ms", "finished_at", "status", "updated_at"])
    except Exception as exc:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        run.status = PerformanceRun.Status.ERROR
        run.error_message = str(exc)
        run.finished_at = timezone.now()
        if run.load_started_at and not run.load_finished_at:
            run.load_finished_at = run.finished_at
            run.load_duration_ms = max(0, round((run.load_finished_at - run.load_started_at).total_seconds() * 1000))
        run.process_id = None
        run.save(update_fields=["status", "error_message", "finished_at", "load_finished_at", "load_duration_ms", "process_id", "updated_at"])
    finally:
        try:
            from .notifications import notify_performance_run
            notify_performance_run(run.id)
        except Exception:
            pass
