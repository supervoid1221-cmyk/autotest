from rest_framework.routers import DefaultRouter

from .views import PerformanceRunViewSet, PerformanceScenarioViewSet

router = DefaultRouter()
router.register("scenario", PerformanceScenarioViewSet, basename="performance-scenario")
router.register("run", PerformanceRunViewSet, basename="performance-run")

urlpatterns = router.urls

