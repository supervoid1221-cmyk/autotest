"""
@Filename:   urls
@Time:        2023/7/11 21:16
@Describe:    ...
"""
from rest_framework import routers

from .views import ProfileViewSet, TenantViewSet, UserManageViewSet

router = routers.SimpleRouter()
router.register("profile", ProfileViewSet, "profile")
router.register("user", UserManageViewSet, "user")
router.register("tenant", TenantViewSet, "tenant")

urlpatterns = router.urls
