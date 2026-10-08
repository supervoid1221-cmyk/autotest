"""
@Filename:   serializers
@Time:        2023/8/3 20:23
@Describe:    ...
"""

import re
from rest_framework import serializers

from account.models import Profile, TenantMembership
from account.tenancy import get_request_tenant, validate_tenant_relations

from .models import DatabaseConnection, DynamicFunction, Environment, Module, Project, ProjectVariable
from .dynamic_functions import function_names, validate_dynamic_code


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = "__all__"  # 使用全部字段


class ModuleSerializer(serializers.ModelSerializer):
    """项目下的共享目录。

    接口、UI 元素、App 元素三个页面读的是同一行数据，各自只关心自己那一类的
    关联数量，因此这里把三个计数一并返回，由前端按当前页面取用。
    """

    project_name = serializers.CharField(source="project.name", read_only=True)
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    endpoint_count = serializers.IntegerField(source="endpoints.count", read_only=True)
    ui_element_count = serializers.IntegerField(source="ui_elements.count", read_only=True)
    app_element_count = serializers.IntegerField(source="app_elements.count", read_only=True)

    class Meta:
        model = Module
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at")

    def validate(self, attrs):
        """重名要给出可读的 400。

        三个页面共用同一套目录后，在 UI 元素页新建的目录很可能与接口页已有的重名，
        而 DRF 不会从 Meta.constraints 自动生成校验器，不拦就会落到数据库唯一约束上
        变成 500。这里显式校验，与 unique_project_module_name 保持一致。
        """
        project = attrs.get("project", getattr(self.instance, "project", None))
        name = attrs.get("name", getattr(self.instance, "name", None))
        if project and name:
            duplicates = Module.objects.filter(project=project, name=name)
            if self.instance is not None:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise serializers.ValidationError({"name": "当前项目下已存在同名目录。"})
        return attrs


class ProjectSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    pm_name = serializers.CharField(source="pm.username", read_only=True)
    member_count = serializers.IntegerField(source="user_list.count", read_only=True)
    environment_count = serializers.IntegerField(source="environments.count", read_only=True)
    endpoint_count = serializers.IntegerField(source="endpoint_set.count", read_only=True)
    scenario_count = serializers.IntegerField(source="scenarios.count", read_only=True)

    class Meta:
        model = Project
        fields = "__all__"  # 使用全部字段
        read_only_fields = ("tenant",)

    def validate(self, attrs):
        pm = attrs.get("pm", getattr(self.instance, "pm", None))
        tenant = getattr(self.instance, "tenant", None)
        if tenant is None:
            request = self.context.get("request")
            tenant = get_request_tenant(request) if request else None
        if pm and not pm.is_active:
            raise serializers.ValidationError({"pm": "项目负责人必须是启用状态的用户。"})
        if pm and tenant and not TenantMembership.objects.filter(
            tenant=tenant, user=pm, status=TenantMembership.Status.ACTIVE,
        ).exists():
            raise serializers.ValidationError({"pm": "项目负责人必须属于当前租户。"})
        members = attrs.get("user_list")
        if members is not None:
            disabled = [user.username for user in members if not user.is_active]
            if disabled:
                raise serializers.ValidationError({"user_list": "不能添加已禁用用户：" + "、".join(disabled)})
            if tenant:
                member_ids = {user.id for user in members}
                tenant_member_ids = set(TenantMembership.objects.filter(
                    tenant=tenant,
                    user_id__in=member_ids,
                    status=TenantMembership.Status.ACTIVE,
                ).values_list("user_id", flat=True))
                if member_ids - tenant_member_ids:
                    raise serializers.ValidationError({"user_list": "项目成员必须全部属于当前租户。"})
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
        request = self.context.get("request")
        if request and project:
            validate_tenant_relations(request, project=project)
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
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    approved_by_name = serializers.CharField(source="approved_by.username", read_only=True)

    class Meta:
        model = DynamicFunction
        fields = (
            "id", "projects", "project_names", "function_names", "code", "enabled",
            "language", "version", "code_hash", "approval_status", "timeout_seconds", "memory_mb",
            "created_by", "created_by_name", "approved_by", "approved_by_name", "approved_at",
            "created_at", "updated_at",
        )
        read_only_fields = ("language", "version", "code_hash", "approval_status", "created_by", "approved_by", "approved_at", "created_at", "updated_at")

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
        request = self.context.get("request")
        if request:
            validate_tenant_relations(request, projects=projects)
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

    def validate_timeout_seconds(self, value):
        if not 1 <= int(value) <= 10:
            raise serializers.ValidationError("执行超时范围为 1 至 10 秒。")
        return value

    def validate_memory_mb(self, value):
        if not 64 <= int(value) <= 512:
            raise serializers.ValidationError("内存上限范围为 64 至 512 MB。")
        return value

    def update(self, instance, validated_data):
        incoming_projects = validated_data.get("projects")
        scope_changed = incoming_projects is not None and {item.pk for item in incoming_projects} != set(instance.projects.values_list("pk", flat=True))
        code_changed = "code" in validated_data and validated_data["code"] != instance.code
        execution_policy_changed = any(
            field in validated_data and validated_data[field] != getattr(instance, field)
            for field in ("timeout_seconds", "memory_mb")
        )
        if code_changed or scope_changed or execution_policy_changed:
            validated_data.update({"version": instance.version + 1, "approval_status": DynamicFunction.ApprovalStatus.DRAFT, "approved_by": None, "approved_at": None})
        return super().update(instance, validated_data)


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
        request = self.context.get("request")
        if request:
            validate_tenant_relations(request, projects=list(projects))

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
