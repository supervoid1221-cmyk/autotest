"""
@Filename:   serializers
@Time:        2023/8/3 20:23
@Describe:    ...
"""

import re
from rest_framework import serializers
from django.core.exceptions import ObjectDoesNotExist

from .models import Endpoint, Scenario, ScenarioBranch, ScenarioFlowNode, ScenarioStep
from project.models import Project
from account.tenancy import validate_tenant_relations


class EndpointSerializer(serializers.ModelSerializer):
    project_name = serializers.SerializerMethodField()
    module_name = serializers.CharField(source="module.name", read_only=True)
    creator_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = Endpoint
        fields = "__all__"  # 使用全部字段
        extra_kwargs = {"created_by": {"read_only": True}}

    def get_project_name(self, obj: Endpoint):
        return obj.project.name

    def validate(self, attrs):
        project = attrs.get("project", getattr(self.instance, "project", None))
        module = attrs.get("module", getattr(self.instance, "module", None))
        if module and module.project_id != project.id:
            raise serializers.ValidationError({"module": "所选模块不属于当前项目。"})
        parametrize = attrs.get("parametrize", getattr(self.instance, "parametrize", []))
        if not isinstance(parametrize, list):
            raise serializers.ValidationError({"parametrize": "数据驱动参数必须为数组。"})
        options = attrs.get("dataset_options", getattr(self.instance, "dataset_options", {}))
        if not isinstance(options, dict):
            raise serializers.ValidationError({"dataset_options": "数据驱动配置必须为对象。"})
        disabled = options.get("disabled_rows", [])
        if not isinstance(disabled, list) or any(type(index) is not int or index < 0 or index >= max(0, len(parametrize) - 1) for index in disabled):
            raise serializers.ValidationError({"dataset_options": "禁用行索引无效。"})
        if "enabled" in options and type(options["enabled"]) is not bool:
            raise serializers.ValidationError({"dataset_options": "启用状态必须为布尔值。"})
        if options.get("enabled") and (not parametrize or len(set(disabled)) >= len(parametrize) - 1):
            raise serializers.ValidationError({"parametrize": "请至少启用一行数据。"})
        if parametrize:
            if not isinstance(parametrize, list) or len(parametrize) < 2:
                raise serializers.ValidationError({"parametrize": "数据驱动至少需要字段名行和一行数据。"})
            fields, rows = parametrize[0], parametrize[1:]
            if not isinstance(fields, list) or not fields or any(not isinstance(name, str) or not name.strip() for name in fields):
                raise serializers.ValidationError({"parametrize": "数据驱动第一行必须是非空字段名数组。"})
            if len(rows) > 500 or len(fields) > 50:
                raise serializers.ValidationError({"parametrize": "最多支持 500 行、50 列。"})
            if len(set(fields)) != len(fields):
                raise serializers.ValidationError({"parametrize": "数据驱动字段名不能重复。"})
            if any(not re.fullmatch(r"[A-Za-z_]\w*", field) for field in fields):
                raise serializers.ValidationError({"parametrize": "字段名须以英文字母或下划线开头，仅包含字母、数字及下划线。"})
            if any(not isinstance(row, list) or len(row) != len(fields) for row in rows):
                raise serializers.ValidationError({"parametrize": "每一行数据的列数必须与字段名数量一致。"})
        return attrs


class ScenarioStepSerializer(serializers.ModelSerializer):
    endpoint = serializers.PrimaryKeyRelatedField(
        queryset=Endpoint.objects.all(),
        error_messages={
            "does_not_exist": "所选接口不存在、已删除或无权访问，请刷新接口列表后重试。",
            "incorrect_type": "接口标识无效，请刷新接口列表后重新选择。",
        },
    )
    endpoint_name = serializers.CharField(source="endpoint.name", read_only=True)
    endpoint_info = EndpointSerializer(source="endpoint", read_only=True)

    class Meta:
        model = ScenarioStep
        fields = "__all__"

    def validate(self, attrs):
        endpoint = attrs.get("endpoint")
        if "endpoint" not in attrs and self.instance is not None:
            try:
                endpoint = self.instance.endpoint
            except ObjectDoesNotExist:
                endpoint = None
        if not endpoint:
            raise serializers.ValidationError({"endpoint": "请选择接口。"})
        request_method = str(attrs.get("request_method", getattr(self.instance, "request_method", "")) or "").upper()
        if request_method and request_method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
            raise serializers.ValidationError({"request_method": "请求方式不支持。"})
        if "request_method" in attrs:
            attrs["request_method"] = request_method
        post_sql = attrs.get("post_sql", getattr(self.instance, "post_sql", []))
        if not isinstance(post_sql, list) or not all(isinstance(item, str) and "${execute_sql_" in item for item in post_sql):
            raise serializers.ValidationError({"post_sql": "后置数据库操作必须是包含 ${execute_sql_xxx(\"SQL\")} 的字符串数组。"})
        retry_count = attrs.get(
            "failure_retry_count", getattr(self.instance, "failure_retry_count", 1)
        )
        if not isinstance(retry_count, int) or isinstance(retry_count, bool) or not 1 <= retry_count <= 5:
            raise serializers.ValidationError({"failure_retry_count": "失败重试次数必须为 1～5 次。"})
        return attrs


class ScenarioFlowNodeSerializer(serializers.ModelSerializer):
    step_info = ScenarioStepSerializer(source="step", read_only=True)
    branches = serializers.SerializerMethodField()

    class Meta:
        model = ScenarioFlowNode
        fields = "__all__"

    def get_branches(self, obj):
        if obj.node_type != ScenarioFlowNode.NodeType.CONDITION:
            return []
        return ScenarioBranchSerializer(obj.branches.all(), many=True, context=self.context).data

    def validate(self, attrs):
        instance = self.instance
        node_type = attrs.get("node_type", getattr(instance, "node_type", None))
        scenario = attrs.get("scenario", getattr(instance, "scenario", None))
        step = attrs.get("step", getattr(instance, "step", None))
        parent_branch = attrs.get("parent_branch", getattr(instance, "parent_branch", None))
        if node_type == ScenarioFlowNode.NodeType.ENDPOINT:
            if not step:
                raise serializers.ValidationError({"step": "接口节点必须关联接口步骤。"})
            if step.scenario_id != scenario.id:
                raise serializers.ValidationError({"step": "接口步骤不属于当前场景。"})
        elif node_type == ScenarioFlowNode.NodeType.CONDITION:
            if step:
                raise serializers.ValidationError({"step": "判断分支不能关联接口步骤。"})
            if parent_branch:
                raise serializers.ValidationError({"parent_branch": "第一版不支持嵌套判断分支。"})
            if not str(attrs.get("name", getattr(instance, "name", ""))).strip():
                raise serializers.ValidationError({"name": "请填写判断分支名称。"})
        else:
            raise serializers.ValidationError({"node_type": "节点类型不正确。"})
        if parent_branch and parent_branch.condition_node.scenario_id != scenario.id:
            raise serializers.ValidationError({"parent_branch": "分支不属于当前场景。"})
        return attrs


class ScenarioBranchSerializer(serializers.ModelSerializer):
    nodes = serializers.SerializerMethodField()
    condition_node_name = serializers.CharField(source="condition_node.name", read_only=True)

    class Meta:
        model = ScenarioBranch
        fields = "__all__"

    def get_nodes(self, obj):
        nodes = obj.nodes.select_related("step", "step__endpoint").order_by("order", "id")
        return ScenarioFlowNodeSerializer(nodes, many=True, context=self.context).data

    def validate(self, attrs):
        instance = self.instance
        condition_node = attrs.get("condition_node", getattr(instance, "condition_node", None))
        conditions = attrs.get("conditions", getattr(instance, "conditions", []))
        if not condition_node or condition_node.node_type != ScenarioFlowNode.NodeType.CONDITION:
            raise serializers.ValidationError({"condition_node": "请选择有效的判断节点。"})
        if not isinstance(conditions, list) or not conditions:
            raise serializers.ValidationError({"conditions": "每个分支至少需要一条条件。"})
        for index, item in enumerate(conditions, start=1):
            if not isinstance(item, dict):
                raise serializers.ValidationError({"conditions": f"第 {index} 条条件格式不正确。"})
            source = item.get("source")
            if source not in {"variable", "step"}:
                raise serializers.ValidationError({"conditions": f"第 {index} 条条件缺少数据来源。"})
            if source == "variable" and not str(item.get("variable") or "").strip():
                raise serializers.ValidationError({"conditions": f"第 {index} 条条件缺少变量名。"})
            if source == "step" and not item.get("step_id"):
                raise serializers.ValidationError({"conditions": f"第 {index} 条条件缺少上游接口。"})
        return attrs


class ScenarioSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    project_names = serializers.SerializerMethodField()
    step_count = serializers.IntegerField(source="steps.count", read_only=True)
    creator_name = serializers.CharField(source="created_by.username", read_only=True)
    projects = serializers.PrimaryKeyRelatedField(many=True, queryset=Project.objects.all(), required=True)

    class Meta:
        model = Scenario
        fields = "__all__"
        extra_kwargs = {"created_by": {"read_only": True}}

    def validate(self, attrs):
        projects = attrs.get("projects")
        if not projects:
            raise serializers.ValidationError({"projects": "请至少选择一个关联项目。"})
        # 保留 project 字段作为兼容旧数据的主项目；场景实际可编排所有关联项目的接口。
        attrs["project"] = projects[0]
        request = self.context.get("request")
        if request:
            validate_tenant_relations(request, projects=list(projects))
        return attrs

    def get_project_names(self, obj):
        return list(obj.projects.values_list("name", flat=True))
