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


# 无真人发起者时（定时任务、Webhook、迁移前历史数据）的归属名称。
SYSTEM_ACTOR_NAME = "系统"


def display_name(user, default=SYSTEM_ACTOR_NAME):
    """返回用户的显示名称，用于写入业务记录的「执行人 / 创建人」快照。

    平台把归属信息存成名称字符串而不是外键（见 RunResult.executor_name、
    Suite.creator_name、ExecutionTask.executor_name）：用户改名或注销后，
    历史记录仍要能显示当时是谁操作的。

    未登录（定时任务、Webhook）或用户不存在时返回 ``default``。需要区分
    「确实是系统发起」和「无从得知」的调用方，可显式传 ``default=""``，
    让空值落到前端显示为「-」。
    """
    if not user or not getattr(user, "is_authenticated", False):
        return default
    return (user.get_full_name() or "").strip() or user.get_username() or default
