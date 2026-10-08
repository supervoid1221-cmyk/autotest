"""
@Filename:   urls
@Time:        2023/7/11 21:16
@Describe:    ...
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import BrandingAssetView, BrandingConfigurationView, ServerConnectionViewSet, SystemConfigurationView

router = DefaultRouter()
router.register("server-connection", ServerConnectionViewSet, basename="server-connection")
urlpatterns = [
    path("configuration/", SystemConfigurationView.as_view(), name="system-configuration"),
    path("branding/", BrandingConfigurationView.as_view(), name="system-branding"),
    path("branding/<str:kind>/", BrandingAssetView.as_view(), name="system-branding-asset"),
    *router.urls,
]
