"""
@Filename:    urls
@Time:        2023/7/11 21:16
@Describe:    ...
"""
from rest_framework import routers

from .views import (
    ElementViewSet, PlaywrightCaseViewSet, PlaywrightScenarioFileViewSet,
    PlaywrightStepViewSet, UiCaseViewSet, UiStepViewSet, UiUploadedFileViewSet,
)

router = routers.SimpleRouter()
router.register(
    "element",
    ElementViewSet,
)
router.register("case", UiCaseViewSet)
router.register("step", UiStepViewSet)
router.register("uploaded-file", UiUploadedFileViewSet)
router.register("playwright-case", PlaywrightCaseViewSet)
router.register("playwright-scenario-file", PlaywrightScenarioFileViewSet)
router.register("playwright-step", PlaywrightStepViewSet)
urlpatterns = router.urls
