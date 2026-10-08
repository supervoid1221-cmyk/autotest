from rest_framework.routers import DefaultRouter

from .views import (
    AppApplicationViewSet, AppCaseViewSet, AppDeviceViewSet, AppElementViewSet,
    AppExecutionNodeViewSet, AppInspectionSessionViewSet, AppRunViewSet, AppStepViewSet, AppVersionViewSet,
)

router = DefaultRouter()
router.register("application", AppApplicationViewSet, basename="app-application")
router.register("version", AppVersionViewSet, basename="app-version")
router.register("node", AppExecutionNodeViewSet, basename="app-node")
router.register("device", AppDeviceViewSet, basename="app-device")
router.register("element", AppElementViewSet, basename="app-element")
router.register("inspector", AppInspectionSessionViewSet, basename="app-inspector")
router.register("case", AppCaseViewSet, basename="app-case")
router.register("step", AppStepViewSet, basename="app-step")
router.register("run", AppRunViewSet, basename="app-run")

urlpatterns = router.urls
