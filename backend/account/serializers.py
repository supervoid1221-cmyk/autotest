"""
@Filename:   serializers
@Time:        2023/8/3 20:23
@Describe:    ...
"""

from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers
from rest_framework.authtoken.models import Token

from .access import is_system_admin
from .models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    token = serializers.SerializerMethodField()
    user = serializers.SerializerMethodField()
    is_admin = serializers.SerializerMethodField()
    username = serializers.CharField(source="user.username", read_only=True)
    class Meta:
        model = Profile
        fields = "__all__"  # 使用全部字段

    def get_token(self, obj):
        user = obj.user
        token, is_create = Token.objects.get_or_create(user=user)

        return token.key

    def get_user(self, obj):
        return obj.user_id

    def get_is_admin(self, obj):
        return is_system_admin(obj.user)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(required=True)
    password = serializers.CharField(required=True)

    def validate_username(self, data):  # 只校验当前字典
        return data

    def validate_password(self, data):  # 只校验当前字典
        return data

    def validate(self, attrs):  # 校验全部字段
        username = attrs["username"]
        password = attrs["password"]

        user = authenticate(username=username, password=password)

        if not user:
            raise serializers.ValidationError({"msg": "用户名或密码不正确"})
        else:
            Profile.objects.get_or_create(user=user)  # 为用户创建 个人资料
            Token.objects.get_or_create(user=user)  # 为用户创建 Token

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
