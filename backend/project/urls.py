"""
@Filename:   urls
@Time:        2023/7/11 21:16
@Describe:    ...
"""
from rest_framework import routers

from .views import (
    DatabaseConnectionViewSet, DynamicFunctionViewSet, EnvironmentViewSet, ModuleViewSet,
    ProjectVariableViewSet, ProjectViewSet,
)

router = routers.SimpleRouter()
router.register(
    "project",
    ProjectViewSet,
)
router.register("environment", EnvironmentViewSet)
router.register("variable", ProjectVariableViewSet)
router.register("dynamic-function", DynamicFunctionViewSet)
router.register("database-connection", DatabaseConnectionViewSet)
# 接口 / UI 元素 / App 元素三个页面共用的目录，见 project.models.Module。
router.register("module", ModuleViewSet)

urlpatterns = router.urls
