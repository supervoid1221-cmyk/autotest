from rest_framework.permissions import BasePermission

from .access import is_system_admin


class IsPlatformAdmin(BasePermission):
    message = "仅系统管理员可以维护平台级配置。"

    def has_permission(self, request, view):
        return is_system_admin(request.user)
