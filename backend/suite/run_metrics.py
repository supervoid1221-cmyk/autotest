"""从测试计划的执行报告里折算「用例级」执行指标。

场景 / UI 用例 / 智能用例 / App 用例的列表页都要展示「最近执行 + 通过率」，
但这四类用例的结果都**不落库**——只存在 ``RunResult.native_report["scenarios"]``
这个 JSON 里，无法用 SQL 聚合。这里把扫描与折算逻辑收口，避免四处各写一遍。

各类型在报告里的 ``scenarios[].id`` 形态不同，必须按前缀区分：

    API 场景    "42"                    （裸整数，无前缀）
    UI 用例     "ui-42"
    智能用例    "playwright-ui-42"
    App 用例    "app-42"

前缀的定义位置见 ``suite/models.py`` 里组装 ``planned_scenarios`` 的几处。
注意 ``"ui-"`` 与 ``"playwright-ui-"`` 不会互相误匹配（后者不以 ``ui-`` 开头），
而裸整数分支用 ``int()`` 解析，天然不会命中任何带前缀的 id。

**已知限制**：周统计（近 7 天 / 上周）是在同一个扫描窗口内统计的，
若窗口内的执行数超过 ``RUN_SCAN_LIMIT``，这两个值会偏低。
响应里的 ``run_scan_limit`` / ``scan_truncated`` 就是给前端提示这件事的。
数据量再上一个量级后，应改为落库的物化统计表。
"""
from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone

from project.access import project_access_q

# 每次请求最多扫描多少条执行记录。报告是 JSON，只能逐条解析，
# 所以必须限制范围，否则请求会随历史数据增长而变慢。
RUN_SCAN_LIMIT = 80
# 通过率和「最近执行」共用同一个窗口，避免页面展示条数与统计口径不一致。
RECENT_RUN_LIMIT = 10
CACHE_SECONDS = 30
CACHE_VERSION_KEY = "case_overview:tenant-{tenant_id}:version"
CACHE_SCHEMA_VERSION = 2

TERMINAL_STATUSES = ("passed", "failed", "skipped")


def invalidate_overview_cache(tenant_id):
    """使已缓存的用例概览立即失效。"""
    key = CACHE_VERSION_KEY.format(tenant_id=tenant_id)
    try:
        cache.incr(key)
    except ValueError:
        # 缓存后端不一定支持通配删除，用版本号切换命名空间。
        cache.set(key, 2, None)


def _overview_cache_version(tenant_id):
    key = CACHE_VERSION_KEY.format(tenant_id=tenant_id)
    return int(cache.get(key) or 1)


def parse_entry_key(entry, key_prefix):
    """把报告条目的 id 还原成用例主键；不属于本类型时返回 None。"""
    raw = str(entry.get("id") or "").strip()
    if key_prefix:
        if not raw.startswith(key_prefix):
            return None
        raw = raw[len(key_prefix):]
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def collect_run_facts(user, key_prefix, case_ids, *, tenant=None):
    """从最近的计划执行报告里抽出「用例 → 执行结果」事实。

    返回 ``{case_id: [{"passed", "run_id", "suite_name", "executor", "finished_at"}, ...]}``，
    每个列表按时间倒序（最近一次在最前）。

    注意：各用例的「即席试跑」（列表页上的执行按钮）是同步试跑且不落库，
    因此这里只反映用例被编排进测试计划后的执行情况。
    """
    from suite.models import RunResult

    facts = {}
    if not case_ids:
        return facts
    queryset = RunResult.objects.filter(
        status__in=(RunResult.RunStatus.Done, RunResult.RunStatus.Error),
    )
    if tenant is not None:
        queryset = queryset.filter(tenant=tenant)
    runs = list(
        queryset
        .filter(project_access_q(user, "project__"))
        .select_related("suite")
        # RunResult 主键是随机 10 位执行编号，不具备时间顺序。
        .order_by("-finished_at", "-create_datetime")
        .only("native_report", "started_at", "finished_at", "executor_name", "suite__name")
        [:RUN_SCAN_LIMIT]
    )
    for run in runs:
        report = run.native_report or {}
        finished_at = run.finished_at.isoformat() if run.finished_at else None
        origin = {
            "run_id": run.pk,
            "suite_name": run.suite.name if run.suite_id else "",
            "executor": run.executor_name or "系统",
            "finished_at": finished_at,
            "started_at": run.started_at,
        }
        for entry in report.get("scenarios") or []:
            if not isinstance(entry, dict):
                continue
            case_id = parse_entry_key(entry, key_prefix)
            if case_id is None or case_id not in case_ids:
                continue
            # 未出终态的条目（pending/running）不参与统计，否则通过率会被拉低。
            status = str(entry.get("status") or "").strip().lower()
            if status not in TERMINAL_STATUSES:
                continue
            facts.setdefault(case_id, []).append({"passed": status == "passed", **origin})
    return facts


def build_metrics(facts):
    """把执行事实折算成列表页需要的指标。"""
    metrics = {}
    for case_id, records in facts.items():
        sample = records[:RECENT_RUN_LIMIT]
        total = len(sample)
        passed = sum(1 for item in sample if item["passed"])
        # 连续失败次数用于「待处理异常」判定：从最近一次往前数，遇到通过就停。
        consecutive = 0
        for item in sample:
            if item["passed"]:
                break
            consecutive += 1
        metrics[case_id] = {
            "last_passed": sample[0]["passed"],
            "last_finished_at": sample[0]["finished_at"],
            "pass_rate": round(passed / total * 100, 1) if total else None,
            "passed_count": passed,
            "sample_size": total,
            "consecutive_failures": consecutive,
            "history": [
                {
                    "passed": item["passed"],
                    "finished_at": item["finished_at"],
                    "suite_name": item["suite_name"],
                    "executor": item["executor"],
                }
                for item in sample
            ],
        }
    return metrics


def week_run_stats(user, key_prefix, *, tenant=None):
    """统计近 7 天 / 上周「包含本类型用例」的计划执行次数。

    与 collect_run_facts 共用同一个扫描窗口，因此不额外付出解析成本；
    代价是窗口被截断时数值会偏低（见模块开头的已知限制）。
    """
    from suite.models import RunResult

    queryset = RunResult.objects.filter(
        status__in=(RunResult.RunStatus.Done, RunResult.RunStatus.Error),
    )
    if tenant is not None:
        queryset = queryset.filter(tenant=tenant)
    runs = list(
        queryset
        .filter(project_access_q(user, "project__"))
        .order_by("-finished_at", "-create_datetime")
        .only("native_report", "started_at", "finished_at", "create_datetime")
        [:RUN_SCAN_LIMIT]
    )
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)
    this_week = last_week = 0
    for run in runs:
        if not run.started_at:
            continue
        if run.started_at < two_weeks_ago:
            continue
        matched = any(
            isinstance(entry, dict) and parse_entry_key(entry, key_prefix) is not None
            for entry in (run.native_report or {}).get("scenarios") or []
        )
        if not matched:
            continue
        if run.started_at >= week_ago:
            this_week += 1
        else:
            last_week += 1
    # 窗口被扫描上限填满时，说明可能还有更早的执行没被统计到。
    truncated = len(runs) >= RUN_SCAN_LIMIT
    return this_week, last_week, truncated


def build_overview(user, tenant, *, cache_scope, key_prefix, case_rows):
    """组装列表页概览：平台 KPI + 每个用例的最近执行与通过率。

    :param cache_scope: 缓存键前缀，按用例类型区分，如 ``"ui_case_overview"``
    :param key_prefix: 报告 id 前缀，``""`` / ``"ui-"`` / ``"playwright-ui-"`` / ``"app-"``
    :param case_rows: 已按项目权限过滤的 ``[(case_id, project_id), ...]``
    """
    cache_key = (
        f"{cache_scope}:schema-{CACHE_SCHEMA_VERSION}:tenant-{tenant.pk}:"
        f"user-{user.pk}:v{_overview_cache_version(tenant.pk)}"
    )
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    case_ids = {case_id for case_id, _ in case_rows}
    project_ids = {project_id for _, project_id in case_rows}
    metrics = build_metrics(collect_run_facts(user, key_prefix, case_ids, tenant=tenant))
    sample_size = sum(item["sample_size"] for item in metrics.values())
    passed_count = sum(item["passed_count"] for item in metrics.values())
    this_week, last_week, truncated = week_run_stats(user, key_prefix, tenant=tenant)

    payload = {
        "stats": {
            "total": len(case_ids),
            "project_count": len(project_ids),
            # 只有跑过的用例才有指标，用来提示「通过率」的覆盖范围。
            "covered": len(metrics),
            "runs_this_week": this_week,
            "runs_last_week": last_week,
            "pass_rate": round(passed_count / sample_size * 100, 1) if sample_size else None,
            "abnormal": sum(1 for item in metrics.values() if item["consecutive_failures"] >= 2),
            "sample_size": sample_size,
            "run_scan_limit": RUN_SCAN_LIMIT,
            "scan_truncated": truncated,
        },
        "items": {str(key): value for key, value in metrics.items()},
    }
    cache.set(cache_key, payload, CACHE_SECONDS)
    return payload
