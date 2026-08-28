from pathlib import Path

from django.contrib.auth.models import User
from django.db import models



# 仅供历史迁移文件加载使用；头像上传功能已移除。
def user_head_img_path(obj, filename):
    return f"account/static/user_{obj.user.id}/{filename}"

class Profile(models.Model):
    """账户扩展资料。昵称、头像等个人展示字段已移除。"""

    objects: models.QuerySet

    user = models.OneToOneField(User, on_delete=models.CASCADE)

