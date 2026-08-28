from rest_framework.permissions import BasePermission

from .access import is_system_admin


class IsPlatformAdmin(BasePermission):
    message = "仅管理员可以管理平台用户。"

    def has_permission(self, request, view):
        return is_system_admin(request.user)
