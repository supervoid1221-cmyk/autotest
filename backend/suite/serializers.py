"""
@Filename:   serializers
@Time:        2023/8/3 20:23
@Describe:    ...
"""

from pathlib import Path

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from account.tenancy import validate_tenant_relations
from case_ui.scenario_text import parse_ui_scenarios

from .models import NotificationChannel, NotificationDelivery, NotificationRule, RunResult, Suite, SuiteExecutionItem, SuiteScenario, SuiteUiCase
from .reporting import hydrate_api_flow_snapshots


# 列表页「最近执行」列只展示最近若干次执行，避免把整个执行历史塞进列表响应。
RECENT_RUN_LIMIT = 10

# 尚未产生最终结果的状态。这些状态在执行报告页显示为「执行中」。
RUNNING_RUN_STATUSES = frozenset({
    RunResult.RunStatus.Init,
    RunResult.RunStatus.Ready,
    RunResult.RunStatus.Running,
    RunResult.RunStatus.Reporting,
    RunResult.RunStatus.Paused,
})


def summarize_run_status(result: RunResult) -> str:
    """把 8 种执行状态收敛成列表页需要的 4 种展示态。

    执行报告页保留完整状态；列表页只需要回答「上次跑通了没有」，
    所以这里统一成 running / pass / fail / canceled。
    """
    if result.status in RUNNING_RUN_STATUSES:
        return "running"
    if result.status == RunResult.RunStatus.Canceled:
        return "canceled"
    if result.status == RunResult.RunStatus.Done and result.is_pass:
        return "pass"
    return "fail"


def run_duration_seconds(result: RunResult):
    """已结束的执行返回耗时秒数；排队中或缺少开始/结束时间的返回 None。"""
    if result.started_at is None or result.finished_at is None:
        return None
    return max(0, round((result.finished_at - result.started_at).total_seconds()))


def _suite_links(suite: Suite):
    """返回 (场景关联, UI 关联, Playwright 关联, App 关联) 四个列表。

    列表接口会用 Prefetch(to_attr=...) 预取好挂在 suite 上（见
    SuiteViewSet._with_list_prefetch），这里优先读缓存，避免每行重复查库。
    没有缓存时（详情页、执行记录序列化器）回落到原来的查询，行为完全一致。
    """
    attrs = (
        "prefetched_scenario_links",
        "prefetched_ui_case_links",
        "prefetched_playwright_links",
        "prefetched_app_case_links",
    )
    cached = tuple(getattr(suite, name, None) for name in attrs)
    if all(links is not None for links in cached):
        return cached
    return (
        list(
            suite.suitescenario_set.select_related("scenario__project").prefetch_related(
                "scenario__projects", "scenario__steps__endpoint__project"
            )
        ),
        list(suite.ordered_ui_case_links()),
        list(suite.ordered_playwright_case_links()),
        list(suite.ordered_app_case_links()),
    )


def _yaml_items(suite: Suite):
    cached = getattr(suite, "prefetched_execution_items", None)
    items = cached if cached is not None else suite.ordered_execution_items()
    return [item for item in items if item.item_type == SuiteExecutionItem.ItemType.YAML_UI]


def _yaml_step_count(suite: Suite):
    cached = getattr(suite, "_yaml_step_count_cache", None)
    if cached is not None:
        return cached
    total = 0
    for item in _yaml_items(suite):
        try:
            total += sum(len(scene["steps"]) for scene in parse_ui_scenarios(item.yaml_case.content))
        except (AttributeError, ValueError):
            continue
    suite._yaml_step_count_cache = total
    return total


def suite_project_names(suite: Suite):
    """返回套件实际执行内容所属项目；空套件才回退到执行环境项目。"""
    names = set()
    scenario_links, ui_links, playwright_links, app_links = _suite_links(suite)

    for suite_scenario in scenario_links:
        scenario = suite_scenario.scenario
        if not scenario:
            continue
        if scenario.project:
            names.add(scenario.project.name)
        names.update(project.name for project in scenario.projects.all())
        for step in scenario.steps.all():
            try:
                endpoint = step.endpoint
                endpoint_project = endpoint.project if endpoint else None
            except ObjectDoesNotExist:
                endpoint_project = None
            if endpoint_project:
                names.add(endpoint_project.name)

    names.update(
        link.ui_case.project.name for link in ui_links if link.ui_case and link.ui_case.project
    )
    names.update(
        link.playwright_case.project.name
        for link in playwright_links
        if link.playwright_case and link.playwright_case.project
    )
    names.update(
        item.yaml_case.project.name for item in _yaml_items(suite)
        if item.yaml_case and item.yaml_case.project
    )
    names.update(
        link.app_case.project.name for link in app_links if link.app_case and link.app_case.project
    )
    if not names and suite.environment_id and suite.environment.project:
        names.add(suite.environment.project.name)
    return sorted(names)


class NotificationChannelSerializer(serializers.ModelSerializer):
    project_names = serializers.SerializerMethodField()

    def get_project_names(self, obj):
        return [project.name for project in obj.projects.all()]

    class Meta:
        model = NotificationChannel
        fields = "__all__"

    def validate_projects(self, projects):
        if not projects:
            raise serializers.ValidationError("请至少选择一个项目。")
        return projects


class NotificationRuleSerializer(serializers.ModelSerializer):
    channel_name = serializers.CharField(source="channel.name", read_only=True)
    suite_name = serializers.CharField(source="suite.name", read_only=True)

    class Meta:
        model = NotificationRule
        fields = "__all__"

    def validate(self, attrs):
        channel = attrs.get("channel", getattr(self.instance, "channel", None))
        suite = attrs.get("suite", getattr(self.instance, "suite", None))
        if suite and not channel.projects.filter(pk=suite.environment.project_id).exists():
            raise serializers.ValidationError({"suite": "请选择该通知渠道关联项目下的套件。"})
        return attrs


class NotificationDeliverySerializer(serializers.ModelSerializer):
    # 外键 channel 默认只输出 id，列表里无法直接看出实际渠道；补名称与平台字段。
    channel_name = serializers.CharField(source="channel.name", read_only=True)
    channel_platform = serializers.CharField(source="channel.platform", read_only=True)

    class Meta:
        model = NotificationDelivery
        fields = "__all__"


class SuiteSerializer(serializers.ModelSerializer):
    # 这 6 个字段在 model 上都是方法。DRF 的 IntegerField(read_only=True) 会把
    # getattr 拿到的绑定方法直接调用（rest_framework.fields.get_attribute 里的
    # is_simple_callable 分支），所以每个字段都会按行查库。
    # 统一改成 SerializerMethodField：列表接口预取/注解过就用缓存，否则回落到原方法，
    # 详情页与编辑页行为完全不变。
    # API用例数量
    case_api_count = serializers.SerializerMethodField()
    # 保留用例数量语义；测试范围展示使用独立的步骤数字段。
    case_ui_count = serializers.SerializerMethodField()
    case_playwright_count = serializers.SerializerMethodField()
    case_app_count = serializers.SerializerMethodField()
    ui_step_count = serializers.SerializerMethodField()
    app_step_count = serializers.SerializerMethodField()

    # 用例执行模式
    run_type_display = serializers.CharField(
        read_only=True, source="get_run_type_display"
    )

    # schedule 是 django-q 的关联对象，使用主键字段输出其 ID，不能直接按 int 转换对象。
    schedule = serializers.PrimaryKeyRelatedField(read_only=True, allow_null=True)
    environment_name = serializers.CharField(source="environment.name", read_only=True)
    project = serializers.IntegerField(source="environment.project_id", read_only=True, allow_null=True)
    project_name = serializers.SerializerMethodField()
    next_run = serializers.SerializerMethodField()
    scenarios = serializers.SerializerMethodField()
    ui_cases = serializers.SerializerMethodField()
    app_cases = serializers.SerializerMethodField()
    execution_items = serializers.SerializerMethodField()

    # 列表页「最近执行」列。列表请求由 SuiteViewSet.list 一次性预取后经 context 传入，
    # 详情/新建/编辑等单对象场景回退到一次独立查询。
    last_run_id = serializers.SerializerMethodField()
    last_run_status = serializers.SerializerMethodField()
    last_run_at = serializers.SerializerMethodField()
    last_run_duration_seconds = serializers.SerializerMethodField()
    recent_run_results = serializers.SerializerMethodField()
    recent_pass_rate = serializers.SerializerMethodField()

    def get_scenarios(self, obj: Suite):
        cached = getattr(obj, "prefetched_scenario_links", None)
        if cached is not None:
            return [link.scenario_id for link in cached]
        return list(obj.ordered_scenario_links().values_list("scenario_id", flat=True))

    def get_ui_cases(self, obj: Suite):
        cached = getattr(obj, "prefetched_ui_case_links", None)
        if cached is not None:
            return [link.ui_case_id for link in cached]
        return list(obj.ordered_ui_case_links().values_list("ui_case_id", flat=True))

    def get_app_cases(self, obj: Suite):
        cached = getattr(obj, "prefetched_app_case_links", None)
        if cached is not None:
            return [link.app_case_id for link in cached]
        return list(obj.ordered_app_case_links().values_list("app_case_id", flat=True))

    def get_case_ui_count(self, obj: Suite):
        # case_all_ui_count() = 启用的传统 UI 用例数 + 启用的 Playwright 用例数。
        # 预取命中时直接在内存里数，避免每行两次 COUNT 查询。
        ui_links = getattr(obj, "prefetched_ui_case_links", None)
        playwright_links = getattr(obj, "prefetched_playwright_links", None)
        if ui_links is not None and playwright_links is not None:
            return sum(1 for link in ui_links if link.ui_case and link.ui_case.enabled) + sum(
                1 for link in playwright_links if link.playwright_case and link.playwright_case.enabled
            ) + len(_yaml_items(obj))
        return obj.case_all_ui_count()

    def get_case_api_count(self, obj: Suite):
        # 场景关联已预取（且带 scenario__steps），所以 steps.count() 走的是缓存，不再查库。
        cached = getattr(obj, "prefetched_scenario_links", None)
        if cached is not None:
            return sum(
                link.scenario.steps.count() for link in cached if link.scenario
            )
        return obj.case_api_count()

    def get_case_playwright_count(self, obj: Suite):
        cached = getattr(obj, "prefetched_playwright_links", None)
        if cached is not None:
            return sum(
                1 for link in cached if link.playwright_case and link.playwright_case.enabled
            ) + len(_yaml_items(obj))
        return obj.case_playwright_count()

    def get_case_app_count(self, obj: Suite):
        cached = getattr(obj, "prefetched_app_case_links", None)
        if cached is not None:
            return sum(1 for link in cached if link.app_case and link.app_case.enabled)
        return obj.case_app_count()

    def get_ui_step_count(self, obj: Suite):
        # 列表接口用 Subquery 注解在数据库端算好了（见 SuiteViewSet._with_list_prefetch），
        # 这样每行省掉 2 次聚合查询，又不用把步骤行拉进内存。
        cached = getattr(obj, "annotated_ui_step_count", None)
        if cached is not None:
            return cached + _yaml_step_count(obj)
        return obj.ui_step_count()

    def get_app_step_count(self, obj: Suite):
        cached = getattr(obj, "annotated_app_step_count", None)
        if cached is not None:
            return cached
        return obj.app_step_count()

    def validate_execution_timeout(self, value):
        maximum = settings.MAX_SUITE_EXECUTION_TIMEOUT_SECONDS
        if value < 30 or value > maximum:
            raise serializers.ValidationError(f"执行超时时间必须在 30 到 {maximum} 秒之间。")
        return value

    def get_execution_items(self, obj: Suite):
        # 预取为空时不能直接用：ordered_execution_items() 对「迁移前数据 / 直接写旧关联表」
        # 的套件会回退去拼旧关联表，直接返回空列表会丢掉那些执行项。
        cached = getattr(obj, "prefetched_execution_items", None)
        items = cached if cached else obj.ordered_execution_items()
        return [
            {
                "type": item.item_type,
                "id": (
                    item.scenario_id if item.item_type == "api"
                    else item.ui_case_id if item.item_type == "ui"
                    else item.playwright_case_id if item.item_type == "playwright_ui"
                    else item.yaml_case_id if item.item_type == "yaml_ui"
                    else item.app_case_id
                ),
                "order": item.order,
            }
            for item in items
        ]

    def get_project_name(self, obj: Suite):
        names = suite_project_names(obj)
        return "/".join(names) if names else "-"

    def get_next_run(self, obj: Suite):
        """返回真实的下一次执行时间，避免停用调度器时展示过期时间。"""
        if not obj.enabled or obj.run_type != Suite.RunType.CRON or not obj.schedule_id:
            return None
        next_run = obj.schedule.next_run
        now = timezone.now()
        if next_run and next_run > now:
            return next_run
        if obj.schedule_kind == Suite.ScheduleKind.ONCE or not obj.cron:
            return None
        return croniter(obj.cron, now).get_next(datetime)

    def _recent_runs(self, obj: Suite) -> list:
        """返回该套件最近几次执行记录。

        列表页由 SuiteViewSet 批量预取后写入 context["recent_runs"]，这里直接命中缓存，
        否则每行都会单独查一次数据库。
        """
        cache = self.context.get("recent_runs")
        if cache is not None:
            return cache.get(obj.pk) or []
        return list(
            obj.runresult_set.order_by("-create_datetime", "-id")[:RECENT_RUN_LIMIT]
        )

    def get_last_run_id(self, obj: Suite):
        runs = self._recent_runs(obj)
        return runs[0].id if runs else None

    def get_last_run_status(self, obj: Suite):
        runs = self._recent_runs(obj)
        return summarize_run_status(runs[0]) if runs else "idle"

    def get_last_run_at(self, obj: Suite):
        """使用创建时间而不是 started_at：排队中的任务还没有 started_at，
        用 started_at 会把「已提交、排队中」显示成从未执行。"""
        runs = self._recent_runs(obj)
        return runs[0].create_datetime if runs else None

    def get_last_run_duration_seconds(self, obj: Suite):
        runs = self._recent_runs(obj)
        return run_duration_seconds(runs[0]) if runs else None

    def get_recent_run_results(self, obj: Suite):
        return [
            {
                "id": run.id,
                "status": summarize_run_status(run),
                "at": run.create_datetime,
                "duration_seconds": run_duration_seconds(run),
            }
            for run in self._recent_runs(obj)
        ]

    def get_recent_pass_rate(self, obj: Suite):
        """近几次已结束执行的通过率（百分比整数）。执行中的记录不参与统计。"""
        settled = [
            summarize_run_status(run)
            for run in self._recent_runs(obj)
            if summarize_run_status(run) in ("pass", "fail")
        ]
        if not settled:
            return None
        return round(sum(1 for status in settled if status == "pass") / len(settled) * 100)

    class Meta:
        model = Suite
        fields = "__all__"  # 使用全部字段
        # 创建人是服务端在 perform_create 里写入的归属快照，不接受客户端提交，
        # 否则任何有编辑权限的人都能把「创建人」改成别人。
        read_only_fields = ["creator_name"]

    def validate(self, attrs):
        environment = attrs.get("environment", getattr(self.instance, "environment", None))
        if environment is None:
            raise serializers.ValidationError({"environment": "请为测试套件选择执行环境。"})
        request = self.context.get("request")
        if request:
            validate_tenant_relations(request, environment=environment)
        run_type = attrs.get("run_type", getattr(self.instance, "run_type", None))
        schedule_kind = attrs.get(
            "schedule_kind", getattr(self.instance, "schedule_kind", Suite.ScheduleKind.DAILY)
        )
        schedule_config = attrs.get(
            "schedule_config", getattr(self.instance, "schedule_config", {})
        ) or {}
        schedule_timezone = attrs.get(
            "schedule_timezone", getattr(self.instance, "schedule_timezone", "Asia/Shanghai")
        ) or "Asia/Shanghai"
        if run_type == Suite.RunType.CRON:
            try:
                zone = ZoneInfo(schedule_timezone)
            except ZoneInfoNotFoundError:
                raise serializers.ValidationError({"schedule_timezone": "时区无效。"})
            if schedule_kind == Suite.ScheduleKind.ONCE:
                run_at = parse_datetime(str(schedule_config.get("run_at") or ""))
                if run_at is None:
                    raise serializers.ValidationError({"schedule_config": "请选择一次性执行时间。"})
                if timezone.is_naive(run_at):
                    run_at = timezone.make_aware(run_at, zone)
                if run_at <= timezone.now():
                    raise serializers.ValidationError({"schedule_config": "一次性执行时间必须晚于当前时间。"})
                schedule_config = {**schedule_config, "run_at": run_at.astimezone(zone).isoformat()}
                attrs["cron"] = ""
            else:
                cron = self._build_cron(schedule_kind, schedule_config, attrs.get("cron", getattr(self.instance, "cron", "")))
                if not croniter.is_valid(cron):
                    raise serializers.ValidationError({"cron": "Cron 表达式格式不正确，请使用标准五段格式。"})
                attrs["cron"] = cron
            attrs["schedule_kind"] = schedule_kind
            attrs["schedule_config"] = schedule_config
            attrs["schedule_timezone"] = schedule_timezone
        return attrs

    @staticmethod
    def _build_cron(schedule_kind, config, custom_cron):
        """把可视化规则统一转换为 django-q 使用的五段 Cron。"""
        if schedule_kind == Suite.ScheduleKind.CUSTOM:
            cron = (custom_cron or "").strip()
            if not cron:
                raise serializers.ValidationError({"cron": "请填写自定义 Cron 表达式。"})
            return cron
        time_text = str(config.get("time") or "")
        try:
            parsed_time = datetime.strptime(time_text, "%H:%M")
        except ValueError:
            raise serializers.ValidationError({"schedule_config": "执行时间格式应为 HH:MM。"})
        minute, hour = parsed_time.minute, parsed_time.hour
        if schedule_kind == Suite.ScheduleKind.DAILY:
            return f"{minute} {hour} * * *"
        if schedule_kind == Suite.ScheduleKind.WEEKLY:
            try:
                weekdays = sorted({int(item) for item in config.get("weekdays", [])})
            except (TypeError, ValueError):
                raise serializers.ValidationError({"schedule_config": "星期必须为 1 至 7 的数字。"})
            if not weekdays or any(item < 1 or item > 7 for item in weekdays):
                raise serializers.ValidationError({"schedule_config": "请至少选择一个星期。"})
            return f"{minute} {hour} * * {','.join(map(str, weekdays))}"
        if schedule_kind == Suite.ScheduleKind.MONTHLY:
            try:
                days = sorted({int(item) for item in config.get("days", [])})
            except (TypeError, ValueError):
                raise serializers.ValidationError({"schedule_config": "执行日期必须为 1 至 31 的数字。"})
            if not days or any(item < 1 or item > 31 for item in days):
                raise serializers.ValidationError({"schedule_config": "请选择 1 至 31 之间的执行日期。"})
            return f"{minute} {hour} {','.join(map(str, days))} * *"
        raise serializers.ValidationError({"schedule_kind": "不支持的定时类型。"})


class RunResultSerializer(serializers.ModelSerializer):
    project_name = serializers.SerializerMethodField()
    project_names = serializers.SerializerMethodField()
    suite_name = serializers.SerializerMethodField()
    run_type = serializers.SerializerMethodField()
    environment_name = serializers.SerializerMethodField()
    status = serializers.CharField(source="get_status_display")

    log_url = serializers.SerializerMethodField()
    artifacts_url = serializers.SerializerMethodField()

    def _project_names_text(self, obj: RunResult):
        cached = getattr(obj, "_serialized_project_names", None)
        if cached is None:
            names = suite_project_names(obj.suite)
            cached = '/'.join(names) if names else (obj.project.name if obj.project else '-')
            obj._serialized_project_names = cached
        return cached

    def get_project_name(self, obj: RunResult):
        return self._project_names_text(obj)

    def get_project_names(self, obj: RunResult):
        return self._project_names_text(obj)

    def get_suite_name(self, obj: RunResult):
        return obj.suite.name

    def get_run_type(self, obj: RunResult):
        return obj.suite.get_run_type_display()

    def get_environment_name(self, obj: RunResult):
        """优先返回执行时快照；兼容迁移前生成的历史执行记录。"""
        if obj.environment_name:
            return obj.environment_name
        return obj.suite.environment.name if obj.suite.environment_id else "-"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["native_report"] = hydrate_api_flow_snapshots(data.get("native_report") or {})
        return data

    class Meta:
        model = RunResult
        # fields = '__all__'  # 使用全部字段
        exclude = ["path"]

    def get_log_url(self, obj):
        path = Path(str(obj.path))  # upload_yaml/1691496509.188677

        dir_name = path.name

        return f"/api/suite/static/{dir_name}/logs/pytest.log"

    def get_artifacts_url(self, obj):
        path = Path(str(obj.path))  # upload_yaml/1691496509.188677

        dir_name = path.name

        return f"/api/suite/static/{dir_name}/artifacts.zip"


class SuiteScenarioSerializer(serializers.ModelSerializer):
    scenario_name = serializers.CharField(source="scenario.name", read_only=True)

    class Meta:
        model = SuiteScenario
        fields = "__all__"

    def validate(self, attrs):
        suite = attrs.get("suite", getattr(self.instance, "suite", None))
        scenario = attrs.get("scenario", getattr(self.instance, "scenario", None))
        request = self.context.get("request")
        if request and suite and scenario:
            validate_tenant_relations(request, suite=suite, scenario=scenario)
        return attrs


class SuiteUiCaseSerializer(serializers.ModelSerializer):
    ui_case_name = serializers.CharField(source="ui_case.name", read_only=True)

    class Meta:
        model = SuiteUiCase
        fields = "__all__"
