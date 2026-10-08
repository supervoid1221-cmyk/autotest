"""
@Filename:   serializers
@Time:        2023/8/3 20:23
@Describe:    ...
"""

from pathlib import Path

from rest_framework import serializers

from account.tenancy import get_request_tenant
from .models import ServerConnection, SystemConfiguration


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
        read_only_fields = ("tenant", "created_by", "created_at", "updated_at", "last_tested_at", "last_test_status", "last_test_message")

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if request:
            fields["project"].queryset = fields["project"].queryset.filter(
                tenant=get_request_tenant(request),
            )
        return fields

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
        name = attrs.get("name", getattr(self.instance, "name", ""))
        request = self.context.get("request")
        tenant = get_request_tenant(request) if request else getattr(self.instance, "tenant", project.tenant)
        duplicate = ServerConnection.objects.filter(tenant=tenant, name=name)
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError({"name": "当前租户已存在同名服务器连接。"})
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


class SystemConfigurationSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.CharField(source="updated_by.username", read_only=True)
    platform_logo_light_url = serializers.SerializerMethodField()
    platform_logo_dark_url = serializers.SerializerMethodField()
    favicon_url = serializers.SerializerMethodField()
    remove_platform_icon = serializers.BooleanField(write_only=True, required=False, default=False)
    remove_platform_icon_dark = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = SystemConfiguration
        fields = (
            "id", "report_retention_days", "max_worker_count", "max_performance_worker_count",
            "platform_icon", "platform_icon_dark",
            "platform_logo_light_url", "platform_logo_dark_url",
            "favicon_url", "remove_platform_icon", "remove_platform_icon_dark",
            "updated_by", "updated_by_name", "created_at", "updated_at",
        )
        read_only_fields = ("id", "updated_by", "updated_by_name", "created_at", "updated_at")
        extra_kwargs = {
            "platform_icon": {"write_only": True, "required": False, "allow_null": True},
            "platform_icon_dark": {"write_only": True, "required": False, "allow_null": True},
        }

    def _asset_url(self, obj, kind):
        field = getattr(obj, kind, None)
        if not field:
            return ""
        version = int(obj.updated_at.timestamp()) if obj.updated_at else 0
        path = f"/api/system/branding/{kind}/?v={version}"
        return path

    def get_platform_logo_light_url(self, obj):
        return self._asset_url(obj, "platform_icon")

    def get_platform_logo_dark_url(self, obj):
        return self._asset_url(obj, "platform_icon_dark")

    def get_favicon_url(self, obj):
        return self._asset_url(obj, "platform_icon")

    def validate_report_retention_days(self, value):
        if not 1 <= value <= 3650:
            raise serializers.ValidationError("保留天数必须在 1 至 3650 天之间。")
        return value

    def validate_max_worker_count(self, value):
        if not 1 <= value <= 64:
            raise serializers.ValidationError("Worker 数必须在 1 至 64 之间。")
        return value

    def validate_max_performance_worker_count(self, value):
        if not 1 <= value <= 32:
            raise serializers.ValidationError("性能 Worker 数必须在 1 至 32 之间。")
        return value

    @staticmethod
    def _validate_brand_image(value):
        allowed_types = {"image/png", "image/jpeg", "image/webp", "image/gif"}
        allowed_extensions = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
        content_type = str(getattr(value, "content_type", "")).lower()
        extension = Path(value.name).suffix.lower()
        if content_type not in allowed_types or extension not in allowed_extensions:
            raise serializers.ValidationError("仅支持 PNG、JPG、JPEG、WebP 或 GIF 图片。")
        if value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("图片大小不能超过 2 MB。")
        header = value.read(16)
        value.seek(0)
        signatures = {
            ".png": header.startswith(b"\x89PNG\r\n\x1a\n"),
            ".jpg": header.startswith(b"\xff\xd8\xff"),
            ".jpeg": header.startswith(b"\xff\xd8\xff"),
            ".gif": header.startswith((b"GIF87a", b"GIF89a")),
            ".webp": header.startswith(b"RIFF") and header[8:12] == b"WEBP",
        }
        if not signatures.get(extension, False):
            raise serializers.ValidationError("图片内容与文件类型不匹配。")
        return value

    def validate_platform_icon(self, value):
        return self._validate_brand_image(value)

    def validate_platform_icon_dark(self, value):
        return self._validate_brand_image(value)

    def update(self, instance, validated_data):
        remove_platform_icon = validated_data.pop("remove_platform_icon", False)
        remove_platform_icon_dark = validated_data.pop("remove_platform_icon_dark", False)
        old_files = {}
        for field_name in ("platform_icon", "platform_icon_dark"):
            if field_name in validated_data and getattr(instance, field_name):
                old_files[field_name] = getattr(instance, field_name)
        if remove_platform_icon and instance.platform_icon:
            old_files["platform_icon"] = instance.platform_icon
            validated_data["platform_icon"] = None
        if remove_platform_icon_dark and instance.platform_icon_dark:
            old_files["platform_icon_dark"] = instance.platform_icon_dark
            validated_data["platform_icon_dark"] = None
        instance = super().update(instance, validated_data)
        for field_name, old_file in old_files.items():
            current = getattr(instance, field_name)
            if old_file.name and (not current or current.name != old_file.name):
                old_file.storage.delete(old_file.name)
        return instance
