from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


def platform_token_expires_at(token):
    """返回平台登录令牌的服务端到期时间。"""
    ttl_seconds = int(getattr(settings, "PLATFORM_TOKEN_TTL_SECONDS", 3600))
    return token.created + timedelta(seconds=max(1, ttl_seconds))


class ExpiringTokenAuthentication(TokenAuthentication):
    """DRF Token 认证，并严格限制令牌自签发起只有效 1 小时。"""

    def authenticate_credentials(self, key):
        model = self.get_model()
        try:
            token = model.objects.select_related("user").get(key=key)
        except model.DoesNotExist:
            raise AuthenticationFailed("登录令牌无效，请重新登录。", code="invalid_token")

        if not token.user.is_active:
            raise AuthenticationFailed("用户已停用或已删除。", code="user_inactive")

        if platform_token_expires_at(token) <= timezone.now():
            raise AuthenticationFailed("登录令牌已过期，请重新登录。", code="token_expired")

        return token.user, token
