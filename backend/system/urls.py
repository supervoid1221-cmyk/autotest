"""
@Filename:   urls
@Time:        2023/7/11 21:16
@Describe:    ...
"""
from rest_framework.routers import DefaultRouter

from .views import ServerConnectionViewSet

router = DefaultRouter()
router.register("server-connection", ServerConnectionViewSet, basename="server-connection")
urlpatterns = router.urls
