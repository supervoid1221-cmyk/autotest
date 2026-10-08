"""
@Filename:   serializers
@Time:        2023/8/3 20:23
@Describe:    ...
"""

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework import serializers
from rest_framework.authtoken.models import Token

from .access import is_system_admin
from .authentication import platform_token_expires_at
from .models import Profile, Tenant, TenantMembership


class TenantSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    role_name = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    project_count = serializers.IntegerField(source="projects.count", read_only=True)
    storage_used_bytes = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
        fields = (
            "id", "name", "slug", "status", "role", "role_name",
            "member_count", "project_count", "max_regular_concurrent_executions",
            "max_performance_concurrent_executions", "storage_quota_bytes", "storage_used_bytes",
            "created_at", "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def _membership(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None
        return obj.memberships.filter(
            user=user, status=TenantMembership.Status.ACTIVE,
        ).first()

    def get_role(self, obj):
        request = self.context.get("request")
        if is_system_admin(getattr(request, "user", None)):
            return "platform_admin"
        membership = self._membership(obj)
        return membership.role if membership else ""

    def get_role_name(self, obj):
        request = self.context.get("request")
        if is_system_admin(getattr(request, "user", None)):
            return "平台管理员"
        membership = self._membership(obj)
        return membership.get_role_display() if membership else ""

    def get_member_count(self, obj):
        return obj.memberships.filter(status=TenantMembership.Status.ACTIVE).count()

    def get_storage_used_bytes(self, obj):
        from .tenant_runtime import tenant_storage_usage
        return tenant_storage_usage(obj.pk)

    def validate_max_regular_concurrent_executions(self, value):
        if int(value) < 1:
            raise serializers.ValidationError("普通任务最大并发数至少为 1。")
        return value

    def validate_max_performance_concurrent_executions(self, value):
        if not 1 <= int(value) <= 32:
            raise serializers.ValidationError("性能任务最大并发数必须在 1 至 32 之间。")
        return value

    def validate_storage_quota_bytes(self, value):
        if int(value) < 1:
            raise serializers.ValidationError("存储配额必须大于 0。")
        return value


class TenantMembershipSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    role_name = serializers.CharField(source="get_role_display", read_only=True)
    status_name = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = TenantMembership
        fields = (
            "id", "user", "username", "is_active", "role", "role_name",
            "status", "status_name", "created_at", "updated_at",
        )
        read_only_fields = ("id", "user", "username", "is_active", "created_at", "updated_at")


class ProfileSerializer(serializers.ModelSerializer):
    token = serializers.SerializerMethodField()
    token_expires_at = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()
    username = serializers.CharField(source="user.username", read_only=True)
    class Meta:
        model = Profile
        fields = "__all__"  # 使用全部字段

    def get_token(self, obj):
        token = self.context.get("login_token")
        if token is None:
            token, _ = Token.objects.get_or_create(user=obj.user)
        return token.key

    def get_token_expires_at(self, obj):
        token = self.context.get("login_token")
        if token is None:
            token, _ = Token.objects.get_or_create(user=obj.user)
        expires_at = platform_token_expires_at(token)
        if timezone.is_naive(expires_at):
            expires_at = timezone.make_aware(expires_at, timezone.get_current_timezone())
        return expires_at.isoformat()

    def get_user(self, obj):
        return obj.user_id

    def get_is_admin(self, obj):
        return is_system_admin(obj.user)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True)

    def validate(self, attrs):  # 校验全部字段
        username = attrs["username"]
        password = attrs["password"]

        user = authenticate(username=username, password=password)

        if not user:
            raise serializers.ValidationError({"msg": "用户名或密码不正确"})
        if not is_system_admin(user) and not TenantMembership.objects.filter(
            user=user,
            status=TenantMembership.Status.ACTIVE,
            tenant__status=Tenant.Status.ACTIVE,
        ).exists():
            raise serializers.ValidationError({"msg": "当前账号未加入可用租户，请联系平台管理员"})

        Profile.objects.get_or_create(user=user)  # 为用户创建 个人资料
        attrs["user"] = user
        return attrs


class ResetPassSerializer(serializers.Serializer):
    new_password = serializers.CharField(required=True, min_length=6)
    confirm_password = serializers.CharField(required=True, min_length=6)

    def validate(self, attrs):  # 校验全部字段
        new_password = attrs["new_password"]
        confirm_password = attrs["confirm_password"]

        if new_password != confirm_password:
            raise serializers.ValidationError({"message": "密码和确认密码不一致"})

        return attrs


class UserListSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    class Meta:
        model = Profile
        fields = "__all__"  # 使用全部字段


class UserManageSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=6)
    projects = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "password", "is_active", "is_staff", "date_joined", "last_login", "projects")
        read_only_fields = ("id", "date_joined", "last_login", "projects")

    def get_projects(self, obj):
        # 平台管理员视为可见全部项目；普通用户返回其实际关联的项目
        # （含 M2M 成员 project_set 与 项目负责人 project_pm_list，去重）。
        if is_system_admin(obj):
            return "ALL"
        projects = {p.id: p.name for p in obj.project_set.all()}
        projects.update({p.id: p.name for p in obj.project_pm_list.all()})
        return [{"id": pid, "name": name} for pid, name in projects.items()]

    def validate_username(self, value):
        queryset = User.objects.filter(username=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("用户名已存在。")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        if not password:
            raise serializers.ValidationError({"password": "新增用户必须设置密码。"})
        user = User.objects.create_user(password=password, **validated_data)
        Profile.objects.get_or_create(user=user)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
