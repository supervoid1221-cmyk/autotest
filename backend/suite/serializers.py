"""
@Filename:   serializers
@Time:        2023/8/3 20:23
@Describe:    ...
"""

from pathlib import Path

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from .models import NotificationChannel, NotificationDelivery, NotificationRule, RunResult, Suite, SuiteScenario, SuiteUiCase
from .reporting import hydrate_api_flow_snapshots


def suite_project_names(suite: Suite):
    """返回套件实际执行内容所属项目；空套件才回退到执行环境项目。"""
    names = set()
    suite_scenarios = suite.suitescenario_set.select_related(
        "scenario__project"
    ).prefetch_related("scenario__projects", "scenario__steps__endpoint__project")
    for suite_scenario in suite_scenarios:
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
        link.ui_case.project.name
        for link in suite.ordered_ui_case_links()
        if link.ui_case and link.ui_case.project
    )
    names.update(
        link.playwright_case.project.name
        for link in suite.ordered_playwright_case_links()
        if link.playwright_case and link.playwright_case.project
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
    # API用例数量
    case_api_count = serializers.IntegerField(read_only=True)
    # 列表中的“UI 用例数”表示所有 UI 执行项，包含传统 UI 和 Playwright 智能 UI。
    case_ui_count = serializers.SerializerMethodField()
    case_playwright_count = serializers.IntegerField(read_only=True)

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
    execution_items = serializers.SerializerMethodField()

    def get_scenarios(self, obj: Suite):
        return list(obj.ordered_scenario_links().values_list("scenario_id", flat=True))

    def get_ui_cases(self, obj: Suite):
        return list(obj.ordered_ui_case_links().values_list("ui_case_id", flat=True))

    def get_case_ui_count(self, obj: Suite):
        return obj.case_all_ui_count()

    def get_execution_items(self, obj: Suite):
        return [
            {
                "type": item.item_type,
                "id": item.scenario_id if item.item_type == "api" else item.ui_case_id if item.item_type == "ui" else item.playwright_case_id,
                "order": item.order,
            }
            for item in obj.ordered_execution_items()
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

    class Meta:
        model = Suite
        fields = "__all__"  # 使用全部字段

    def validate(self, attrs):
        environment = attrs.get("environment", getattr(self.instance, "environment", None))
        if environment is None:
            raise serializers.ValidationError({"environment": "请为测试套件选择执行环境。"})
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

    def get_project_name(self, obj: RunResult):
        names = suite_project_names(obj.suite)
        return '/'.join(names) if names else (obj.project.name if obj.project else '-')

    def get_project_names(self, obj: RunResult):
        names = suite_project_names(obj.suite)
        return '/'.join(names) if names else (obj.project.name if obj.project else '-')

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
        return attrs


class SuiteUiCaseSerializer(serializers.ModelSerializer):
    ui_case_name = serializers.CharField(source="ui_case.name", read_only=True)

    class Meta:
        model = SuiteUiCase
        fields = "__all__"
