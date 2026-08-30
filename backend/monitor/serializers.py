from rest_framework import serializers

from .models import MonitorAlertEvent, MonitorCheckSettings, MonitorCluster, MonitorNotificationDelivery, MonitorNotificationRule, MonitorTarget, PrometheusInstance, ServiceMonitor, ServiceMonitorEvent


class MonitorClusterSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    prometheus_name = serializers.CharField(source="prometheus.name", read_only=True)
    server_name = serializers.CharField(source="server.name", read_only=True)
    target_count = serializers.IntegerField(source="targets.count", read_only=True)
    class Meta:
        model = MonitorCluster; fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at", "last_synced_at", "last_sync_status", "last_sync_message")
    def validate(self, attrs):
        project = attrs.get("project", getattr(self.instance, "project", None)); prometheus = attrs.get("prometheus", getattr(self.instance, "prometheus", None)); server = attrs.get("server", getattr(self.instance, "server", None)); rules = attrs.get("label_rules", getattr(self.instance, "label_rules", {}))
        if prometheus and prometheus.project_id != project.id: raise serializers.ValidationError({"prometheus": "Prometheus 实例必须属于当前项目。"})
        if server and server.project_id != project.id: raise serializers.ValidationError({"server": "服务器连接必须属于当前项目。"})
        if not isinstance(rules, dict): raise serializers.ValidationError({"label_rules": "标签规则必须是对象。"})
        return attrs


class PrometheusInstanceSerializer(serializers.ModelSerializer):
    access_token = serializers.CharField(write_only=True, required=False, allow_blank=True)
    access_token_configured = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    cluster_name = serializers.CharField(source="cluster.name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = PrometheusInstance
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at")

    def get_access_token_configured(self, obj):
        return bool(obj.access_token)

    def validate(self, attrs):
        project = attrs.get("project", getattr(self.instance, "project", None))
        if not project:
            raise serializers.ValidationError({"project": "请选择所属项目。"})
        return attrs

    def update(self, instance, validated_data):
        if not validated_data.get("access_token"):
            validated_data.pop("access_token", None)
        return super().update(instance, validated_data)


class MonitorTargetSerializer(serializers.ModelSerializer):
    prometheus_name = serializers.CharField(source="prometheus.name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    server_name = serializers.CharField(source="server.name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = MonitorTarget
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at")

    def validate(self, attrs):
        prometheus = attrs.get("prometheus", getattr(self.instance, "prometheus", None))
        project = attrs.get("project", getattr(self.instance, "project", None))
        server = attrs.get("server", getattr(self.instance, "server", None))
        instance_label = attrs.get("instance_label", getattr(self.instance, "instance_label", ""))
        if not project:
            raise serializers.ValidationError({"project": "请选择所属项目。"})
        if prometheus and prometheus.project_id != project.id:
            raise serializers.ValidationError({"prometheus": "Prometheus 实例必须属于当前项目。"})
        if server and server.project_id != project.id:
            raise serializers.ValidationError({"server": "服务器连接必须属于当前项目。"})
        duplicate = MonitorTarget.objects.filter(
            prometheus=prometheus,
            instance_label=instance_label,
        )
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError(
                {"instance_label": "该 Prometheus 实例下已配置相同的 Instance 标签，请编辑已有监控目标。"}
            )
        for prefix in ("cpu", "memory", "disk"):
            warning = attrs.get(f"{prefix}_warning_threshold", getattr(self.instance, f"{prefix}_warning_threshold", 0))
            critical = attrs.get(f"{prefix}_critical_threshold", getattr(self.instance, f"{prefix}_critical_threshold", 0))
            if not 0 < warning < critical <= 100:
                raise serializers.ValidationError({f"{prefix}_critical_threshold": "阈值必须满足 0 < 预警阈值 < 告警阈值 ≤ 100。"})
        return attrs


class MonitorAlertEventSerializer(serializers.ModelSerializer):
    target_name = serializers.CharField(source="target.name", read_only=True)
    project_name = serializers.CharField(source="target.project.name", read_only=True)

    class Meta:
        model = MonitorAlertEvent
        fields = "__all__"


class ServiceMonitorSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    server_name = serializers.CharField(source="server.name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = ServiceMonitor
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at")

    def validate(self, attrs):
        monitor_type = attrs.get("monitor_type", getattr(self.instance, "monitor_type", ServiceMonitor.MonitorType.HTTP))
        project = attrs.get("project", getattr(self.instance, "project", None))
        server = attrs.get("server", getattr(self.instance, "server", None))
        address = str(attrs.get("address", getattr(self.instance, "address", ""))).strip()
        port = attrs.get("port", getattr(self.instance, "port", None))
        timeout = attrs.get("timeout_seconds", getattr(self.instance, "timeout_seconds", 5))
        codes = attrs.get("expected_status_codes", getattr(self.instance, "expected_status_codes", []))
        if not address:
            raise serializers.ValidationError({"address": "请填写服务地址。"})
        if not project:
            raise serializers.ValidationError({"project": "请选择所属项目。"})
        if server and server.project_id != project.id:
            raise serializers.ValidationError({"server": "服务器连接必须属于当前项目。"})
        if monitor_type == ServiceMonitor.MonitorType.HTTP and not address.startswith(("http://", "https://")):
            raise serializers.ValidationError({"address": "HTTP 服务地址必须以 http:// 或 https:// 开头。"})
        if monitor_type == ServiceMonitor.MonitorType.TCP and not port:
            raise serializers.ValidationError({"port": "TCP 监控必须填写端口。"})
        if monitor_type == ServiceMonitor.MonitorType.DOCKER and not attrs.get("server", getattr(self.instance, "server", None)):
            raise serializers.ValidationError({"server": "Docker 容器监控必须关联服务器。"})
        if not 1 <= int(timeout) <= 60:
            raise serializers.ValidationError({"timeout_seconds": "超时范围为 1 至 60 秒。"})
        if not isinstance(codes, list) or any(not isinstance(code, int) or not 100 <= code <= 599 for code in codes):
            raise serializers.ValidationError({"expected_status_codes": "期望状态码必须为有效 HTTP 状态码数组。"})
        return attrs


class ServiceMonitorEventSerializer(serializers.ModelSerializer):
    service_name = serializers.CharField(source="service.name", read_only=True)
    project_name = serializers.CharField(source="service.project.name", read_only=True)

    class Meta:
        model = ServiceMonitorEvent
        fields = "__all__"


class MonitorNotificationRuleSerializer(serializers.ModelSerializer):
    channel_name = serializers.CharField(source="channel.name", read_only=True)
    channel_platform = serializers.CharField(source="channel.platform", read_only=True)
    target_name = serializers.CharField(source="target.name", read_only=True)
    service_names = serializers.SerializerMethodField()

    class Meta:
        model = MonitorNotificationRule
        fields = "__all__"
        read_only_fields = ("created_by", "created_at")

    def get_service_names(self, obj):
        return [service.name for service in obj.services.all()]

    def validate(self, attrs):
        target = attrs.get("target", getattr(self.instance, "target", None))
        services = attrs.get("services")
        if services is None and self.instance:
            services = list(self.instance.services.all())
        services = list(services or [])
        all_services = attrs.get("all_services", getattr(self.instance, "all_services", False))
        channel = attrs.get("channel", getattr(self.instance, "channel", None))
        service_scope = bool(all_services or services)
        if bool(target) == service_scope:
            raise serializers.ValidationError("请选择一个监控主机，或选择一个及以上监控服务。")
        if all_services and services:
            raise serializers.ValidationError({"services": "选择全部服务时不能同时指定单个服务。"})
        monitored_projects = [target.project] if target else [service.project for service in services]
        for project in monitored_projects:
            if project and not channel.projects.filter(pk=project.pk).exists():
                raise serializers.ValidationError({"channel": f"通知渠道未关联项目「{project.name}」。"})
        return attrs


class MonitorNotificationDeliverySerializer(serializers.ModelSerializer):
    channel_name = serializers.CharField(source="channel.name", read_only=True)
    target_name = serializers.CharField(source="target.name", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)

    class Meta:
        model = MonitorNotificationDelivery
        fields = "__all__"


class MonitorCheckSettingsSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.CharField(source="updated_by.username", read_only=True)

    class Meta:
        model = MonitorCheckSettings
        fields = "__all__"
        read_only_fields = (
            "last_target_check_at",
            "last_service_check_at",
            "updated_by",
            "updated_at",
        )

    def validate_target_check_interval_seconds(self, value):
        if value != 0 and not 60 <= value <= 3600:
            raise serializers.ValidationError("监控目标检查频率请选择关闭，或设置在 60 至 3600 秒之间。")
        return value

    def validate_service_check_interval_seconds(self, value):
        if value != 0 and not 60 <= value <= 3600:
            raise serializers.ValidationError("服务监控检查频率请选择关闭，或设置在 60 至 3600 秒之间。")
        return value
