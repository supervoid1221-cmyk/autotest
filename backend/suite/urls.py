"""
@Filename:   case/urls
@Time:        2023/8/8 20:15
@Describe:    ...
"""
from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import NotificationChannelViewSet, NotificationDeliveryViewSet, NotificationRuleViewSet, RunResultViewSet, SuiteScenarioViewSet, SuiteViewSet, static_server

router = SimpleRouter()
router.register("run_result", RunResultViewSet)
router.register("suite", SuiteViewSet)
router.register("scenario", SuiteScenarioViewSet)
router.register("notification-channel", NotificationChannelViewSet)
router.register("notification-rule", NotificationRuleViewSet)
router.register("notification-delivery", NotificationDeliveryViewSet)

urlpatterns = [
    path("static/<path:path>", static_server, {"document_root": "upload_yaml"})
    # 传参成功
]


urlpatterns += router.urls
