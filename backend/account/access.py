"""平台身份判定工具。

系统管理员使用 Django 用户的 ``is_staff`` 标记维护；超级管理员同样属于
系统管理员。所有权限判断都应调用这里，避免不同模块各自判断造成权限不一致。
"""


def is_system_admin(user):
    """判断用户是否为拥有全平台数据权限的系统管理员。"""
    return bool(
        user
        and user.is_authenticated
        and (getattr(user, "is_superuser", False) or getattr(user, "is_staff", False))
    )
