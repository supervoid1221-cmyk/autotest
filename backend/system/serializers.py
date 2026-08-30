"""
@Filename:   serializers
@Time:        2023/8/3 20:23
@Describe:    ...
"""

from rest_framework import serializers

from .models import ServerConnection


class ServerConnectionSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    private_key_passphrase = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password_configured = serializers.SerializerMethodField()
    private_key_passphrase_configured = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source="created_by.username", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)

    class Meta:
        model = ServerConnection
        fields = "__all__"
        read_only_fields = ("created_by", "created_at", "updated_at", "last_tested_at", "last_test_status", "last_test_message")

    def get_password_configured(self, obj):
        return bool(obj.password)

    def get_private_key_passphrase_configured(self, obj):
        return bool(obj.private_key_passphrase)

    def validate(self, attrs):
        project = attrs.get("project", getattr(self.instance, "project", None))
        auth_type = attrs.get("auth_type", getattr(self.instance, "auth_type", ServerConnection.AuthType.PRIVATE_KEY))
        key_path = attrs.get("private_key_path", getattr(self.instance, "private_key_path", ""))
        password = attrs.get("password", "")
        if not project:
            raise serializers.ValidationError({"project": "请选择所属项目。"})
        if auth_type == ServerConnection.AuthType.PRIVATE_KEY and not str(key_path or "").strip():
            raise serializers.ValidationError({"private_key_path": "私钥认证必须填写后端服务器可访问的私钥路径。"})
        if auth_type == ServerConnection.AuthType.PASSWORD and not (password or getattr(self.instance, "password", "")):
            raise serializers.ValidationError({"password": "密码认证必须填写登录密码。"})
        return attrs

    def update(self, instance, validated_data):
        for field in ("password", "private_key_passphrase"):
            if not validated_data.get(field):
                validated_data.pop(field, None)
        return super().update(instance, validated_data)
