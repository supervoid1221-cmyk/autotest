"""
@Filename:   urls
@Time:        2023/7/11 21:16
@Describe:    ...
"""
from rest_framework import routers

from .views import DatabaseConnectionViewSet, DynamicFunctionViewSet, EnvironmentViewSet, ProjectVariableViewSet, ProjectViewSet

router = routers.SimpleRouter()
router.register(
    "project",
    ProjectViewSet,
)
router.register("environment", EnvironmentViewSet)
router.register("variable", ProjectVariableViewSet)
router.register("dynamic-function", DynamicFunctionViewSet)
router.register("database-connection", DatabaseConnectionViewSet)

urlpatterns = router.urls
