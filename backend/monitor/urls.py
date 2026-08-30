from rest_framework.routers import DefaultRouter

from .views import MonitorAlertEventViewSet, MonitorCheckSettingsViewSet, MonitorClusterViewSet, MonitorDashboardViewSet, MonitorNotificationDeliveryViewSet, MonitorNotificationRuleViewSet, MonitorTargetViewSet, PrometheusInstanceViewSet, ServiceMonitorEventViewSet, ServiceMonitorViewSet

router = DefaultRouter()
router.register("prometheus", PrometheusInstanceViewSet, basename="monitor-prometheus")
router.register("cluster", MonitorClusterViewSet, basename="monitor-cluster")
router.register("target", MonitorTargetViewSet, basename="monitor-target")
router.register("service", ServiceMonitorViewSet, basename="monitor-service")
router.register("service-event", ServiceMonitorEventViewSet, basename="monitor-service-event")
router.register("notification-rule", MonitorNotificationRuleViewSet, basename="monitor-notification-rule")
router.register("notification-delivery", MonitorNotificationDeliveryViewSet, basename="monitor-notification-delivery")
router.register("check-settings", MonitorCheckSettingsViewSet, basename="monitor-check-settings")
router.register("dashboard", MonitorDashboardViewSet, basename="monitor-dashboard")
router.register("alert-event", MonitorAlertEventViewSet, basename="monitor-alert-event")

urlpatterns = router.urls
