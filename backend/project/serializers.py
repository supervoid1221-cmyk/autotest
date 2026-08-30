"""
@Filename:   serializers
@Time:        2023/8/3 20:23
@Describe:    ...
"""

import re
from rest_framework import serializers

from account.models import Profile

from .models import DatabaseConnection, DynamicFunction, Environment, Project, ProjectVariable
from .dynamic_functions import function_names, validate_dynamic_code


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = "__all__"  # 使用全部字段


class ProjectSerializer(serializers.ModelSerializer):
    pm_name = serializers.CharField(source="pm.username", read_only=True)
    member_count = serializers.IntegerField(source="user_list.count", read_only=True)
    environment_count = serializers.IntegerField(source="environments.count", read_only=True)
    endpoint_count = serializers.IntegerField(source="endpoint_set.count", read_only=True)
    scenario_count = serializers.IntegerField(source="scenarios.count", read_only=True)

    class Meta:
        model = Project
        fields = "__all__"  # 使用全部字段

    def validate(self, attrs):
        pm = attrs.get("pm", getattr(self.instance, "pm", None))
        if pm and not pm.is_active:
            raise serializers.ValidationError({"pm": "项目负责人必须是启用状态的用户。"})
        members = attrs.get("user_list")
        if members is not None:
            disabled = [user.username for user in members if not user.is_active]
            if disabled:
                raise serializers.ValidationError({"user_list": "不能添加已禁用用户：" + "、".join(disabled)})
        return attrs


class ProjectVariableSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = ProjectVariable
        fields = ("id", "project", "project_name", "name", "value", "description")

    def validate_name(self, value):
        name = str(value or "").strip()
        if not name:
            raise serializers.ValidationError("变量名不能为空。")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise serializers.ValidationError("变量名只能包含字母、数字和下划线，且不能以数字开头。")
        return name

    def validate(self, attrs):
        project = attrs.get("project", getattr(self.instance, "project", None))
        if self.instance and "project" in attrs and project.id != self.instance.project_id:
            raise serializers.ValidationError({"project": "项目变量不支持更换所属项目。"})
        return attrs


class EnvironmentSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    # `Bearer ` 这类前缀的尾随空格是协议内容，不应被 DRF 默认的 trim_whitespace 移除。
    token_prefix = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)

    class Meta:
        model = Environment
        fields = "__all__"

    def get_fields(self):
        fields = super().get_fields()
        # 缓存 Token 仅供执行器读取，任何环境配置接口都不返回或允许写入。
        for field_name in ("cached_token", "token_expires_at", "token_refreshed_at"):
            fields.pop(field_name, None)
        return fields

    def validate(self, attrs):
        # 基础信息支持在详情页直接调整；同一项目下同名环境保持唯一，
        # 避免环境切换页无法区分 Dev/Test/Pre/Prod 的配置。
        project = attrs.get("project", getattr(self.instance, "project", None))
        name = attrs.get("name", getattr(self.instance, "name", None))
        if project and name:
            duplicate = Environment.objects.filter(project=project, name=name)
            if self.instance:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise serializers.ValidationError({"name": "该项目下已存在同名环境。"})
        if attrs.get("auth_enabled", getattr(self.instance, "auth_enabled", False)):
            required = ("login_url", "token_jsonpath", "token_header")
            missing = [field for field in required if not attrs.get(field, getattr(self.instance, field, ""))]
            if missing:
                raise serializers.ValidationError({field: "启用自动登录时此项必填。" for field in missing})
        return attrs


class DynamicFunctionSerializer(serializers.ModelSerializer):
    project_names = serializers.SerializerMethodField()
    function_names = serializers.SerializerMethodField()

    class Meta:
        model = DynamicFunction
        fields = (
            "id", "projects", "project_names", "function_names", "code", "enabled",
            "created_at", "updated_at",
        )

    def get_project_names(self, obj):
        return list(obj.projects.values_list("name", flat=True))

    def get_function_names(self, obj):
        return function_names(obj.code)

    def validate_code(self, value):
        try:
            return validate_dynamic_code(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc

    def get_conflicts(self, projects, code, exclude_id=None):
        incoming_names = set(function_names(code))
        if not incoming_names or not projects:
            return []
        queryset = DynamicFunction.objects.filter(projects__in=projects).prefetch_related("projects").distinct()
        if exclude_id:
            queryset = queryset.exclude(pk=exclude_id)
        selected_project_ids = {project.id for project in projects}
        conflict_map = {}
        for item in queryset:
            duplicated_names = sorted(incoming_names.intersection(function_names(item.code)))
            if not duplicated_names:
                continue
            for project in item.projects.all():
                if project.id not in selected_project_ids:
                    continue
                conflict_map.setdefault(project.id, {
                    "project_id": project.id,
                    "project_name": project.name,
                    "functions": set(),
                })["functions"].update(duplicated_names)
        return [
            {**item, "functions": sorted(item["functions"])}
            for item in sorted(conflict_map.values(), key=lambda value: value["project_name"])
        ]

    def validate(self, attrs):
        projects = list(attrs.get("projects") or (self.instance.projects.all() if self.instance else []))
        if not projects:
            raise serializers.ValidationError({"projects": "请至少选择一个项目。"})
        code = attrs.get("code", getattr(self.instance, "code", ""))
        conflicts = self.get_conflicts(projects, code, getattr(self.instance, "pk", None))
        if conflicts:
            detail = "；".join(
                f"{item['project_name']}（{'、'.join(item['functions'])}）" for item in conflicts
            )
            raise serializers.ValidationError({
                "projects": f"所选项目中已存在同名动态函数：{detail}。",
                "conflicts": conflicts,
            })
        return attrs


class DatabaseConnectionSerializer(serializers.ModelSerializer):
    project_names = serializers.SerializerMethodField()
    database_type_display = serializers.CharField(source="get_database_type_display", read_only=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password_configured = serializers.SerializerMethodField()
    ssh_private_key_passphrase = serializers.CharField(write_only=True, required=False, allow_blank=True)
    ssh_private_key_passphrase_configured = serializers.SerializerMethodField()

    class Meta:
        model = DatabaseConnection
        fields = "__all__"

    def get_password_configured(self, obj):
        return bool(obj.password)

    def get_ssh_private_key_passphrase_configured(self, obj):
        return bool(obj.ssh_private_key_passphrase)

    def get_project_names(self, obj):
        return [project.name for project in obj.projects.all()]

    def validate_function_name(self, value):
        if not re.fullmatch(r"execute_sql_[A-Za-z_]\w*", value or ""):
            raise serializers.ValidationError("调用函数必须以 execute_sql_ 开头，且只能包含字母、数字和下划线。")
        return value

    def validate(self, attrs):
        projects = attrs.get("projects")
        if projects is None and self.instance:
            projects = list(self.instance.projects.all())
        if not projects:
            raise serializers.ValidationError({"projects": "请至少选择一个项目。"})

        environment_name = attrs.get("environment_name", getattr(self.instance, "environment_name", None))
        function_name = attrs.get("function_name", getattr(self.instance, "function_name", None))
        duplicates = DatabaseConnection.objects.filter(
            projects__in=projects,
            environment_name=environment_name,
            function_name=function_name,
        )
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError(
                {"projects": "所选项目中已存在相同环境和调用函数的数据库连接。"}
            )
        use_ssh_tunnel = attrs.get(
            "use_ssh_tunnel", getattr(self.instance, "use_ssh_tunnel", False)
        )
        if use_ssh_tunnel:
            required_fields = {
                "ssh_host": "请输入 SSH 主机。",
                "ssh_username": "请输入 SSH 用户名。",
                "ssh_private_key_path": "请输入后端服务器可访问的 SSH 私钥路径。",
            }
            errors = {}
            for field, message in required_fields.items():
                value = attrs.get(field, getattr(self.instance, field, "") if self.instance else "")
                if not str(value or "").strip():
                    errors[field] = message
            if errors:
                raise serializers.ValidationError(errors)
        return attrs

    def update(self, instance, validated_data):
        if not validated_data.get("password"):
            validated_data.pop("password", None)
        if not validated_data.get("ssh_private_key_passphrase"):
            validated_data.pop("ssh_private_key_passphrase", None)
        return super().update(instance, validated_data)
