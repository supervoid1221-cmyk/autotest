from rest_framework import serializers
from account.tenancy import validate_tenant_relations

from .models import (
    AppApplication, AppArtifact, AppCase, AppDevice, AppElement, AppExecutionNode,
    AppRun, AppStep, AppStepResult, AppVersion,
)


class ProjectBoundSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)


class AppVersionSerializer(serializers.ModelSerializer):
    application_name = serializers.CharField(source="application.name", read_only=True)

    class Meta:
        model = AppVersion
        fields = "__all__"
        read_only_fields = ("file_path", "file_size", "original_name", "created_by", "created_at")


class AppApplicationSerializer(ProjectBoundSerializer):
    versions = AppVersionSerializer(many=True, read_only=True)
    version_count = serializers.IntegerField(source="versions.count", read_only=True)
    element_count = serializers.IntegerField(source="elements.count", read_only=True)

    class Meta:
        model = AppApplication
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at")


class AppExecutionNodeSerializer(ProjectBoundSerializer):
    device_count = serializers.IntegerField(source="devices.count", read_only=True)

    class Meta:
        model = AppExecutionNode
        fields = "__all__"
        read_only_fields = ("status", "last_message", "last_seen_at", "created_by", "created_at", "updated_at")


class AppDeviceSerializer(ProjectBoundSerializer):
    node_name = serializers.CharField(source="node.name", read_only=True)

    class Meta:
        model = AppDevice
        fields = "__all__"
        read_only_fields = ("state", "last_message", "last_seen_at", "created_by", "created_at", "updated_at")

    def validate(self, attrs):
        project = attrs.get("project", getattr(self.instance, "project", None))
        node = attrs.get("node", getattr(self.instance, "node", None))
        if project and node and node.project_id != project.id:
            raise serializers.ValidationError({"node": "执行节点必须属于当前项目。"})
        return attrs


class AppElementSerializer(ProjectBoundSerializer):
    application_name = serializers.CharField(source="application.name", read_only=True)
    module_name = serializers.CharField(source="module.name", read_only=True)

    class Meta:
        model = AppElement
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at")

    def validate(self, attrs):
        project = attrs.get("project", getattr(self.instance, "project", None))
        application = attrs.get("application", getattr(self.instance, "application", None))
        module = attrs.get("module", getattr(self.instance, "module", None))
        if application and project and application.project_id != project.id:
            raise serializers.ValidationError({"application": "元素所属应用必须属于当前项目。"})
        if module and not application:
            raise serializers.ValidationError({"module": "选择模块前必须先选择所属应用。"})
        if module and application and module.application_id != application.id:
            raise serializers.ValidationError({"module": "元素模块必须属于当前应用。"})
        if module and project and module.project_id != project.id:
            raise serializers.ValidationError({"module": "元素模块必须属于当前项目。"})
        return attrs


class AppStepSerializer(serializers.ModelSerializer):
    action_name = serializers.CharField(source="get_action_display", read_only=True)
    element_name = serializers.CharField(source="element.name", read_only=True)

    class Meta:
        model = AppStep
        fields = "__all__"

    def validate(self, attrs):
        instance = self.instance
        case = attrs.get("case", getattr(instance, "case", None))
        action = attrs.get("action", getattr(instance, "action", None))
        element = attrs.get("element", getattr(instance, "element", None))
        target = attrs.get("target", getattr(instance, "target", {})) or {}
        value = str(attrs.get("value", getattr(instance, "value", "")) or "")
        element_actions = {"click", "input", "clear", "wait_element", "get_text", "assert_exists", "assert_text", "assert_attribute"}
        if action in element_actions and not element and not target:
            raise serializers.ValidationError({"element": "该操作必须选择元素或填写定位配置。"})
        if action in {"input", "assert_text", "assert_attribute", "set_variable"} and not value:
            raise serializers.ValidationError({"value": "该操作必须填写操作值。"})
        if case and element and element.project_id != case.project_id:
            raise serializers.ValidationError({"element": "元素必须属于当前用例项目。"})
        if case and element and element.application_id and element.application_id != case.application_id:
            raise serializers.ValidationError({"element": "元素必须属于当前用例的测试应用。"})
        return attrs


class AppCaseSerializer(ProjectBoundSerializer):
    application_name = serializers.CharField(source="application.name", read_only=True)
    default_device_name = serializers.CharField(source="default_device.name", read_only=True)
    step_count = serializers.IntegerField(source="steps.count", read_only=True)
    steps = AppStepSerializer(many=True, read_only=True)

    class Meta:
        model = AppCase
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at")

    def validate(self, attrs):
        project = attrs.get("project", getattr(self.instance, "project", None))
        application = attrs.get("application", getattr(self.instance, "application", None))
        device = attrs.get("default_device", getattr(self.instance, "default_device", None))
        request = self.context.get("request")
        if request and project:
            validate_tenant_relations(request, project=project)
        if application and project and application.project_id != project.id:
            raise serializers.ValidationError({"application": "测试应用必须属于当前项目。"})
        if device and project and device.project_id != project.id:
            raise serializers.ValidationError({"default_device": "默认设备必须属于当前项目。"})
        timeout = attrs.get("default_timeout", getattr(self.instance, "default_timeout", 10000))
        if not 500 <= timeout <= 300000:
            raise serializers.ValidationError({"default_timeout": "默认超时必须在 500～300000 毫秒之间。"})
        return attrs


class AppArtifactSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = AppArtifact
        fields = "__all__"

    def get_download_url(self, obj):
        return f"/api/case_app/run/{obj.run_id}/artifact/{obj.id}/"


class AppStepResultSerializer(serializers.ModelSerializer):
    artifacts = AppArtifactSerializer(many=True, read_only=True)

    class Meta:
        model = AppStepResult
        fields = "__all__"


class AppRunSerializer(serializers.ModelSerializer):
    case_name = serializers.CharField(source="case.name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    application_name = serializers.CharField(source="application.name", read_only=True)
    version_name = serializers.CharField(source="version.version_name", read_only=True)
    device_name = serializers.CharField(source="device.name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    step_results = AppStepResultSerializer(many=True, read_only=True)
    artifacts = AppArtifactSerializer(many=True, read_only=True)

    class Meta:
        model = AppRun
        fields = "__all__"
        extra_kwargs = {"log_content": {"write_only": True}, "options": {"write_only": True}}
