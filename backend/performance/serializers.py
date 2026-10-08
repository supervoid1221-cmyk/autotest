import re

from rest_framework import serializers
from account.tenancy import validate_tenant_relations

from case_api.models import Endpoint, Scenario
from monitor.models import MonitorTarget
from project.models import Environment
from suite.models import NotificationChannel
from .models import (
    PerformanceEndpointMetric,
    PerformanceMetricBucket,
    PerformanceNotificationDelivery,
    PerformanceRun,
    PerformanceScenario,
)
from .snapshots import build_mixed_snapshot


class PerformanceScenarioSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    environment_name = serializers.CharField(source="environment.name", read_only=True)
    source_endpoint_name = serializers.CharField(source="source_endpoint.name", read_only=True)
    source_scenario_name = serializers.CharField(source="source_scenario.name", read_only=True)
    monitor_target_name = serializers.CharField(source="monitor_target.name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = PerformanceScenario
        fields = "__all__"
        read_only_fields = ("scenario_snapshot", "created_by", "created_at", "updated_at")

    def validate(self, attrs):
        instance = self.instance
        project = attrs.get("project", getattr(instance, "project", None))
        environment = attrs.get("environment", getattr(instance, "environment", None))
        source_mode = attrs.get("source_mode", getattr(instance, "source_mode", PerformanceScenario.SourceMode.SINGLE))
        source_type = attrs.get("source_type", getattr(instance, "source_type", PerformanceScenario.SourceType.SCENARIO))
        source_endpoint = attrs.get("source_endpoint", getattr(instance, "source_endpoint", None))
        source_scenario = attrs.get("source_scenario", getattr(instance, "source_scenario", None))
        target = attrs.get("monitor_target", getattr(instance, "monitor_target", None))
        channels = attrs.get("notification_channels")
        request = self.context.get("request")
        if request and project:
            relations = {"project": project, "environment": environment}
            if source_scenario:
                relations["source_scenario"] = source_scenario
            validate_tenant_relations(request, **relations)
        load_mode = attrs.get("load_mode", getattr(instance, "load_mode", PerformanceScenario.LoadMode.STAGES))
        stages = attrs.get("stages", getattr(instance, "stages", []))
        thresholds = attrs.get("thresholds", getattr(instance, "thresholds", {}))
        business_mix = attrs.get("business_mix", getattr(instance, "business_mix", []))
        parameter_data = attrs.get("parameter_data", getattr(instance, "parameter_data", []))
        if load_mode == PerformanceScenario.LoadMode.THREAD_GROUP and source_mode != PerformanceScenario.SourceMode.MIXED:
            raise serializers.ValidationError({"source_mode": "线程组模式需要配置接口流量比例。"})
        if not environment or environment.project_id != project.id:
            raise serializers.ValidationError({"environment": "执行环境必须属于当前项目。"})
        if source_mode == PerformanceScenario.SourceMode.MIXED:
            normalized_mix = self._validate_business_mix(project, business_mix)
            if load_mode == PerformanceScenario.LoadMode.THREAD_GROUP:
                if any(item.get("source_type") != PerformanceScenario.SourceType.ENDPOINT for item in normalized_mix):
                    raise serializers.ValidationError({"business_mix": "线程组模式第一期仅支持分配单接口比例。"})
                if sum(item.get("weight", 0) for item in normalized_mix) != 100:
                    raise serializers.ValidationError({"business_mix": "线程组模式的接口比例合计必须等于 100%。"})
            attrs["business_mix"] = [
                {key: value for key, value in item.items() if not key.endswith("_object")}
                for item in normalized_mix
            ]
            attrs["source_endpoint"] = None
            attrs["source_scenario"] = None
            attrs["_resolved_business_mix"] = normalized_mix
        else:
            attrs["business_mix"] = []
            if source_type == PerformanceScenario.SourceType.ENDPOINT:
                if not source_endpoint or source_endpoint.project_id != project.id:
                    raise serializers.ValidationError({"source_endpoint": "请选择当前项目下的接口。"})
                attrs["source_scenario"] = None
            elif source_type == PerformanceScenario.SourceType.SCENARIO:
                if not source_scenario or not (source_scenario.project_id == project.id or source_scenario.projects.filter(pk=project.id).exists()):
                    raise serializers.ValidationError({"source_scenario": "请选择当前项目可用的接口场景。"})
                if source_scenario.steps.exclude(endpoint__project=project).exists():
                    raise serializers.ValidationError({"source_scenario": "性能测试暂不支持包含跨项目接口的场景。"})
                attrs["source_endpoint"] = None
            else:
                raise serializers.ValidationError({"source_type": "压测对象类型不正确。"})
        if not isinstance(parameter_data, list) or any(not isinstance(row, dict) for row in parameter_data):
            raise serializers.ValidationError({"parameter_data": "参数化数据必须是对象数组。"})
        if len(parameter_data) > 10000:
            raise serializers.ValidationError({"parameter_data": "参数化数据最多支持 10000 行。"})
        if target and target.project_id != project.id:
            raise serializers.ValidationError({"monitor_target": "监控目标必须属于当前项目。"})
        if channels is not None:
            invalid = [channel.name for channel in channels if not channel.projects.filter(pk=project.id).exists()]
            if invalid:
                raise serializers.ValidationError({"notification_channels": f"通知渠道未关联当前项目：{', '.join(invalid)}"})
        total_seconds = 0
        if load_mode == PerformanceScenario.LoadMode.THREAD_GROUP:
            thread_count = attrs.get("thread_count", getattr(instance, "thread_count", 10))
            duration_seconds = attrs.get("duration_seconds", getattr(instance, "duration_seconds", 60))
            ramp_up_seconds = attrs.get("ramp_up_seconds", getattr(instance, "ramp_up_seconds", 0))
            graceful_stop_seconds = attrs.get("graceful_stop_seconds", getattr(instance, "graceful_stop_seconds", 5))
            if not 1 <= thread_count <= 10000:
                raise serializers.ValidationError({"thread_count": "线程数必须在 1 至 10000 之间。"})
            if not 1 <= duration_seconds <= 86400:
                raise serializers.ValidationError({"duration_seconds": "持续时间必须在 1 至 86400 秒之间。"})
            if not 0 <= ramp_up_seconds <= 86400:
                raise serializers.ValidationError({"ramp_up_seconds": "启动时间必须在 0 至 86400 秒之间。"})
            if not 0 <= graceful_stop_seconds <= 3600:
                raise serializers.ValidationError({"graceful_stop_seconds": "停止等待时间必须在 0 至 3600 秒之间。"})
            total_seconds = duration_seconds + ramp_up_seconds
            attrs["stages"] = []
            attrs["load_type"] = PerformanceScenario.LoadType.CUSTOM
        else:
            if not isinstance(stages, list) or not stages:
                raise serializers.ValidationError({"stages": "至少配置一个负载阶段。"})
            for index, stage in enumerate(stages, start=1):
                duration = str(stage.get("duration") or "").strip() if isinstance(stage, dict) else ""
                match = re.fullmatch(r"(\d+(?:\.\d+)?)(ms|s|m|h)", duration, re.I)
                if not match:
                    raise serializers.ValidationError({"stages": f"第 {index} 个阶段缺少持续时间。"})
                total_seconds += float(match.group(1)) * {"ms": 0.001, "s": 1, "m": 60, "h": 3600}[match.group(2).lower()]
                try:
                    target_vus = int(stage.get("target", -1))
                except (TypeError, ValueError):
                    target_vus = -1
                if not 0 <= target_vus <= 10000:
                    raise serializers.ValidationError({"stages": f"第 {index} 个阶段并发数必须在 0 至 10000 之间。"})
            attrs["thread_count"] = 10
            attrs["duration_seconds"] = 60
            attrs["ramp_up_seconds"] = 0
            attrs["graceful_stop_seconds"] = 5
        if total_seconds > 86400:
            raise serializers.ValidationError({"stages": "第一期单次性能任务总时长不能超过 24 小时。"})
        if not isinstance(thresholds, dict):
            raise serializers.ValidationError({"thresholds": "性能阈值格式不正确。"})
        return attrs

    def _validate_business_mix(self, project, items):
        if not isinstance(items, list) or len(items) < 2:
            raise serializers.ValidationError({"business_mix": "多业务混合至少配置两个业务。"})
        if len(items) > 20:
            raise serializers.ValidationError({"business_mix": "最多混合 20 个业务。"})
        normalized = []
        seen = set()
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                raise serializers.ValidationError({"business_mix": f"第 {index} 个业务配置不正确。"})
            source_type = item.get("source_type")
            try:
                weight = int(item.get("weight", 0))
            except (TypeError, ValueError):
                weight = 0
            if not 1 <= weight <= 100:
                raise serializers.ValidationError({"business_mix": f"第 {index} 个业务权重必须在 1 至 100 之间。"})
            if source_type == PerformanceScenario.SourceType.ENDPOINT:
                endpoint = Endpoint.objects.filter(pk=item.get("source_endpoint"), project=project).first()
                if not endpoint:
                    raise serializers.ValidationError({"business_mix": f"第 {index} 个接口不存在或不属于当前项目。"})
                key = (source_type, endpoint.id)
                normalized.append({"source_type": source_type, "source_endpoint": endpoint.id, "source_scenario": None, "weight": weight, "name": endpoint.name, "source_endpoint_object": endpoint})
            elif source_type == PerformanceScenario.SourceType.SCENARIO:
                scenario = Scenario.objects.filter(
                    pk=item.get("source_scenario"), tenant_id=project.tenant_id,
                ).first()
                if not scenario or not (scenario.project_id == project.id or scenario.projects.filter(pk=project.id).exists()):
                    raise serializers.ValidationError({"business_mix": f"第 {index} 个接口场景不存在或不可用于当前项目。"})
                if scenario.steps.exclude(endpoint__project=project).exists():
                    raise serializers.ValidationError({"business_mix": f"第 {index} 个接口场景包含跨项目接口。"})
                key = (source_type, scenario.id)
                normalized.append({"source_type": source_type, "source_endpoint": None, "source_scenario": scenario.id, "weight": weight, "name": scenario.name, "source_scenario_object": scenario})
            else:
                raise serializers.ValidationError({"business_mix": f"第 {index} 个业务类型不正确。"})
            if key in seen:
                raise serializers.ValidationError({"business_mix": f"第 {index} 个业务重复配置。"})
            seen.add(key)
        return normalized

    def _build_snapshot(self, validated_data, instance=None):
        source_mode = validated_data.get("source_mode", getattr(instance, "source_mode", PerformanceScenario.SourceMode.SINGLE))
        if source_mode == PerformanceScenario.SourceMode.MIXED:
            resolved = validated_data.pop("_resolved_business_mix", None)
            if resolved is None:
                resolved = self._validate_business_mix(
                    validated_data.get("project", instance.project),
                    validated_data.get("business_mix", instance.business_mix),
                )
            return build_mixed_snapshot(resolved)
        source_type = validated_data.get("source_type", getattr(instance, "source_type", PerformanceScenario.SourceType.SCENARIO))
        source_endpoint = validated_data.get("source_endpoint", getattr(instance, "source_endpoint", None))
        source_scenario = validated_data.get("source_scenario", getattr(instance, "source_scenario", None))
        source_object = source_endpoint if source_type == PerformanceScenario.SourceType.ENDPOINT else source_scenario
        return build_mixed_snapshot([{
            "source_type": source_type,
            "source_endpoint_object": source_endpoint,
            "source_scenario_object": source_scenario,
            "weight": 100,
            "name": source_object.name,
        }])

    def create(self, validated_data):
        validated_data["scenario_snapshot"] = self._build_snapshot(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        source_changed = any(key in validated_data for key in ("source_mode", "source_type", "source_endpoint", "source_scenario", "business_mix"))
        if source_changed:
            validated_data["scenario_snapshot"] = self._build_snapshot(validated_data, instance)
        validated_data.pop("_resolved_business_mix", None)
        return super().update(instance, validated_data)


class PerformanceMetricBucketSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceMetricBucket
        fields = "__all__"


class PerformanceEndpointMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceEndpointMetric
        fields = "__all__"


class PerformanceNotificationDeliverySerializer(serializers.ModelSerializer):
    channel_name = serializers.CharField(source="channel.name", read_only=True)

    class Meta:
        model = PerformanceNotificationDelivery
        fields = "__all__"


class PerformanceRunSerializer(serializers.ModelSerializer):
    scenario_name = serializers.CharField(source="scenario.name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    environment_name = serializers.CharField(source="environment.name", read_only=True)
    monitor_target_name = serializers.CharField(source="monitor_target.name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    metric_buckets = PerformanceMetricBucketSerializer(many=True, read_only=True)
    endpoint_metrics = PerformanceEndpointMetricSerializer(many=True, read_only=True)
    notification_deliveries = PerformanceNotificationDeliverySerializer(many=True, read_only=True)

    class Meta:
        model = PerformanceRun
        fields = "__all__"
        extra_kwargs = {"execution_config": {"write_only": True}}
