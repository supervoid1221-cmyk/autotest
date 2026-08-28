from rest_framework import serializers

from case_api.models import ScenarioStep
from .models import ExecutionTemplate


class ExecutionTemplateSerializer(serializers.ModelSerializer):
    # 归属项目由后端根据套件环境自动推导，前端无需传。
    project = serializers.PrimaryKeyRelatedField(read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    suite_name = serializers.CharField(source="suite.name", read_only=True)
    environment_name = serializers.CharField(source="suite.environment.name", read_only=True)
    environment_id = serializers.IntegerField(source="suite.environment.id", read_only=True, allow_null=True)
    template_type = serializers.SerializerMethodField()

    class Meta:
        model = ExecutionTemplate
        fields = "__all__"

    def get_template_type(self, obj):
        """按套件内容标识模板类型，供模板管理页筛选。"""
        api_count = obj.suite.case_api_count()
        ui_count = obj.suite.case_all_ui_count()
        if api_count and ui_count:
            return "mixed"
        if ui_count:
            return "ui"
        if api_count:
            return "api"
        return "empty"

    def validate_output_fields(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("输出字段必须是列表。")
        keys = set()
        for index, field in enumerate(value):
            if not isinstance(field, dict):
                raise serializers.ValidationError(f"第 {index + 1} 个输出字段格式不正确。")
            key = str(field.get("key") or "").strip()
            label = str(field.get("label") or "").strip()
            json_path = str(field.get("json_path") or "").strip()
            if not key or not label or not json_path:
                raise serializers.ValidationError(f"第 {index + 1} 个输出字段的字段标识、展示名称和提取路径不能为空。")
            if key in keys:
                raise serializers.ValidationError(f"输出字段标识「{key}」重复。")
            if not json_path.startswith("$"):
                raise serializers.ValidationError(f"输出字段「{label}」的提取路径必须以 $ 开头。")
            try:
                int(field.get("source_step_id"))
            except (TypeError, ValueError):
                raise serializers.ValidationError(f"输出字段「{label}」必须选择来源接口。")
            keys.add(key)
        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)
        output_fields = attrs.get("output_fields", getattr(self.instance, "output_fields", []))
        suite = attrs.get("suite", getattr(self.instance, "suite", None))
        if output_fields and suite:
            step_ids = {int(item["source_step_id"]) for item in output_fields}
            valid_step_ids = set(
                ScenarioStep.objects.filter(scenario__suitescenario__suite=suite, id__in=step_ids)
                .values_list("id", flat=True)
            )
            if valid_step_ids != step_ids:
                raise serializers.ValidationError({"output_fields": "存在不属于当前套件的来源接口。"})
        return attrs
