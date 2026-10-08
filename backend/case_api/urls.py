"""
@Filename:   urls
@Time:        2023/7/11 21:16
@Describe:    ...
"""
from rest_framework import routers

from .views import (
    EndpointViewSet, RecordingViewSet, ScenarioBranchViewSet,
    ScenarioFlowNodeViewSet, ScenarioStepViewSet, ScenarioViewSet,
)

router = routers.SimpleRouter()
router.register(
    "endpoint",
    EndpointViewSet,
)
router.register("recording", RecordingViewSet, basename="recording")
router.register("scenario", ScenarioViewSet)
router.register("scenario-step", ScenarioStepViewSet)
router.register("scenario-flow-node", ScenarioFlowNodeViewSet)
router.register("scenario-branch", ScenarioBranchViewSet)
urlpatterns = router.urls
