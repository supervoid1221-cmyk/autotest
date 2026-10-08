from rest_framework.routers import DefaultRouter

from .views import ExecutionTaskViewSet, ExecutionWorkerViewSet

router = DefaultRouter()
router.register("tasks", ExecutionTaskViewSet, basename="execution-task")
router.register("workers", ExecutionWorkerViewSet, basename="execution-worker")

urlpatterns = router.urls

