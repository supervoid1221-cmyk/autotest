from rest_framework.routers import SimpleRouter

from .views import ExecutionTemplateViewSet

router = SimpleRouter()
router.register("", ExecutionTemplateViewSet, basename="template")

urlpatterns = router.urls
