from drf_spectacular.utils import extend_schema
from django.conf import settings
from django.db import models, transaction
from pathlib import Path
import shutil
import uuid
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import Element, ElementModule, PlaywrightCase, PlaywrightStep, UiCase, UiStep, UiUploadedFile
from .serializers import (
    ElementModuleSerializer, ElementSerializer, PlaywrightCaseSerializer,
    PlaywrightStepSerializer, UiCaseSerializer, UiStepSerializer,
    UiUploadedFileSerializer,
)
from .file_utils import UPLOAD_ROOT
from .recording import normalize_ui_recording
from project.access import project_access_q, require_project_access


@extend_schema(tags=["Case_UI"])
class ElementViewSet(viewsets.ModelViewSet):
    queryset = Element.objects.select_related("project", "module", "created_by").all()
    serializer_class = ElementSerializer

    def get_queryset(self):
        queryset = self.queryset.filter(project_access_q(self.request.user, "project__")).distinct()
        project_id = self.request.query_params.get("project")
        module_id = self.request.query_params.get("module")
        by = (self.request.query_params.get("by") or "").strip()
        search = (self.request.query_params.get("search") or "").strip()
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if module_id:
            queryset = queryset.filter(module_id=module_id)
        elif self.request.query_params.get("unassigned") in {"true", "1"}:
            queryset = queryset.filter(module__isnull=True)
        if by:
            queryset = queryset.filter(by=by)
        if search:
            queryset = queryset.filter(
                models.Q(name__icontains=search) | models.Q(value__icontains=search)
            )
        return queryset

    def perform_create(self, serializer):
        require_project_access(self.request.user, serializer.validated_data["project"])
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        require_project_access(self.request.user, self.get_object().project)
        if "project" in serializer.validated_data:
            require_project_access(self.request.user, serializer.validated_data["project"])
        serializer.save()


@extend_schema(tags=["Case_UI"])
class ElementModuleViewSet(viewsets.ModelViewSet):
    queryset = ElementModule.objects.select_related("project").all()
    serializer_class = ElementModuleSerializer

    def get_queryset(self):
        queryset = self.queryset.filter(project_access_q(self.request.user, "project__")).distinct()
        project_id = self.request.query_params.get("project")
        return queryset.filter(project_id=project_id) if project_id else queryset

    def perform_create(self, serializer):
        require_project_access(self.request.user, serializer.validated_data["project"])
        serializer.save()

    def perform_update(self, serializer):
        module = self.get_object()
        project = serializer.validated_data.get("project", module.project)
        require_project_access(self.request.user, project)
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        module = self.get_object()
        require_project_access(request.user, module.project)
        delete_elements = str(request.query_params.get("delete_elements", "false")).lower() in {
            "1", "true", "yes",
        }
        element_count = module.elements.count()
        with transaction.atomic():
            if delete_elements:
                module.elements.all().delete()
            else:
                module.elements.update(module=None)
            module.delete()
        return Response({
            "detail": "模块及模块下元素已删除。" if delete_elements else "模块已删除，元素已移至未分组。",
            "deleted_element_count": element_count if delete_elements else 0,
            "unassigned_element_count": 0 if delete_elements else element_count,
        })

@extend_schema(tags=["Case_UI"])
class UiCaseViewSet(viewsets.ModelViewSet):
    queryset = UiCase.objects.select_related("project", "created_by").prefetch_related("steps")
    serializer_class = UiCaseSerializer

    def get_queryset(self):
        queryset = self.queryset.filter(project_access_q(self.request.user, "project__")).distinct()
        name = str(self.request.query_params.get("name") or "").strip()
        project_id = self.request.query_params.get("project")
        enabled = self.request.query_params.get("enabled")
        if name:
            queryset = queryset.filter(name__icontains=name)
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if enabled is not None:
            queryset = queryset.filter(enabled=str(enabled).lower() in {"1", "true", "yes"})
        return queryset

    def perform_create(self, serializer):
        require_project_access(self.request.user, serializer.validated_data["project"])
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        require_project_access(self.request.user, self.get_object().project)
        if "project" in serializer.validated_data:
            require_project_access(self.request.user, serializer.validated_data["project"])
        serializer.save()

    @action(methods=["POST"], detail=True, url_path="sync-steps")
    def sync_steps(self, request, pk=None):
        ui_case = self.get_object()
        items = request.data.get("steps", [])
        if not isinstance(items, list):
            return Response({"steps": "步骤列表格式不正确。"}, status=status.HTTP_400_BAD_REQUEST)
        item_ids = [item.get("id") for item in items if isinstance(item, dict) and item.get("id")]
        if len(item_ids) != len(set(item_ids)):
            return Response({"steps": "步骤列表不能包含重复项。"}, status=status.HTTP_400_BAD_REQUEST)
        if any(not isinstance(item, dict) for item in items):
            return Response({"steps": "步骤内容格式不正确。"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            UiCase.objects.select_for_update().get(pk=ui_case.pk)
            existing = {step.pk: step for step in UiStep.objects.select_for_update().filter(ui_case=ui_case)}
            invalid_ids = [step_id for step_id in item_ids if step_id not in existing]
            if invalid_ids:
                raise serializers.ValidationError({"steps": f"步骤不存在或不属于当前用例：{invalid_ids}"})

            UiStep.objects.filter(ui_case=ui_case).exclude(pk__in=item_ids).delete()
            kept = [existing[step_id] for step_id in item_ids]
            if kept:
                offset = max([step.order for step in existing.values()] + [len(items)]) + len(items) + 1
                UiStep.objects.filter(pk__in=[step.pk for step in kept]).update(order=models.F("order") + offset)

            for order, item in enumerate(items, start=1):
                payload = dict(item)
                step_id = payload.pop("id", None)
                for readonly in ("name", "element_name", "element_by", "element_value", "action_name"):
                    payload.pop(readonly, None)
                payload.update({"ui_case": ui_case.pk, "order": order})
                step_serializer = UiStepSerializer(
                    instance=existing.get(step_id), data=payload, context=self.get_serializer_context()
                )
                step_serializer.is_valid(raise_exception=True)
                step_serializer.save()

        return Response(UiStepSerializer(ui_case.steps.all(), many=True).data)


@extend_schema(tags=["Case_UI"])
class UiStepViewSet(viewsets.ModelViewSet):
    queryset = UiStep.objects.select_related("ui_case", "ui_case__project", "element")
    serializer_class = UiStepSerializer

    def get_queryset(self):
        queryset = self.queryset.filter(project_access_q(self.request.user, "ui_case__project__")).distinct()
        ui_case_id = self.request.query_params.get("ui_case")
        if ui_case_id:
            queryset = queryset.filter(ui_case_id=ui_case_id)
        return queryset

    def perform_create(self, serializer):
        require_project_access(self.request.user, serializer.validated_data["ui_case"].project)
        serializer.save()

    def perform_update(self, serializer):
        require_project_access(self.request.user, self.get_object().ui_case.project)
        if "ui_case" in serializer.validated_data:
            require_project_access(self.request.user, serializer.validated_data["ui_case"].project)
        serializer.save()


@extend_schema(tags=["Case_UI"])
class UiUploadedFileViewSet(viewsets.ModelViewSet):
    queryset = UiUploadedFile.objects.select_related("project", "created_by")
    serializer_class = UiUploadedFileSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        queryset = self.queryset.filter(project_access_q(self.request.user, "project__")).distinct()
        project_id = self.request.query_params.get("project")
        return queryset.filter(project_id=project_id) if project_id else queryset

    def create(self, request, *args, **kwargs):
        uploaded_file = request.FILES.get("file")
        project_id = request.data.get("project")
        if not uploaded_file or not project_id:
            return Response({"detail": "请选择所属项目和需要上传的文件。"}, status=status.HTTP_400_BAD_REQUEST)
        if uploaded_file.size > 100 * 1024 * 1024:
            return Response({"detail": "单个文件不能超过 100MB。"}, status=status.HTTP_400_BAD_REQUEST)
        from project.models import Project
        project = Project.objects.filter(pk=project_id).first()
        if not project:
            return Response({"project": "所属项目不存在。"}, status=status.HTTP_400_BAD_REQUEST)
        require_project_access(request.user, project)
        UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
        original_name = Path(uploaded_file.name).name
        stored_path = UPLOAD_ROOT / f"{uuid.uuid4().hex}_{original_name}"
        with stored_path.open("wb") as destination:
            shutil.copyfileobj(uploaded_file, destination)
        record = UiUploadedFile.objects.create(
            project=project, created_by=request.user, original_name=original_name,
            stored_path=str(stored_path.relative_to(settings.BASE_DIR)), size=uploaded_file.size,
        )
        return Response(self.get_serializer(record).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        record = self.get_object()
        require_project_access(request.user, record.project)
        path = (Path(settings.BASE_DIR) / record.stored_path).resolve()
        record.delete()
        if UPLOAD_ROOT in path.parents:
            path.unlink(missing_ok=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Case_UI_Playwright"])
class PlaywrightCaseViewSet(viewsets.ModelViewSet):
    queryset = PlaywrightCase.objects.select_related("project", "created_by").prefetch_related("steps")
    serializer_class = PlaywrightCaseSerializer

    def get_queryset(self):
        queryset = self.queryset.filter(project_access_q(self.request.user, "project__")).distinct()
        name = str(self.request.query_params.get("name") or "").strip()
        project_id = self.request.query_params.get("project")
        enabled = self.request.query_params.get("enabled")
        if name:
            queryset = queryset.filter(name__icontains=name)
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if enabled is not None:
            queryset = queryset.filter(enabled=str(enabled).lower() in {"1", "true", "yes"})
        return queryset

    def perform_create(self, serializer):
        require_project_access(self.request.user, serializer.validated_data["project"])
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        require_project_access(self.request.user, self.get_object().project)
        if "project" in serializer.validated_data:
            require_project_access(self.request.user, serializer.validated_data["project"])
        serializer.save()

    @action(methods=["POST"], detail=False, url_path="preview-recording")
    def preview_recording(self, request):
        try:
            return Response(normalize_ui_recording(request.data))
        except ValueError as exc:
            return Response({"events": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["POST"], detail=False, url_path="import-recording")
    def import_recording(self, request):
        project_id = request.data.get("project")
        if not project_id:
            return Response({"project": "请选择所属项目。"}, status=status.HTTP_400_BAD_REQUEST)
        from project.models import Project
        project = Project.objects.filter(pk=project_id).first()
        if not project:
            return Response({"project": "所选项目不存在。"}, status=status.HTTP_400_BAD_REQUEST)
        require_project_access(request.user, project)
        try:
            recording = normalize_ui_recording(request.data)
        except ValueError as exc:
            return Response({"events": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if not recording["steps"]:
            return Response({"events": "未识别到可保存的 UI 操作。"}, status=status.HTTP_400_BAD_REQUEST)

        browser = str(request.data.get("browser") or PlaywrightCase.Browser.CHROMIUM)
        run_mode = str(request.data.get("run_mode") or PlaywrightCase.RunMode.HEADED)
        if browser not in PlaywrightCase.Browser.values:
            return Response({"browser": "不支持的浏览器。"}, status=status.HTTP_400_BAD_REQUEST)
        if run_mode not in PlaywrightCase.RunMode.values:
            return Response({"run_mode": "不支持的运行模式。"}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            case = PlaywrightCase.objects.create(
                name=str(request.data.get("name") or "录制的智能 UI 用例")[:64],
                description=str(request.data.get("description") or "通过 UI 录制器生成")[:250],
                project=project,
                created_by=request.user,
                environment_name=str(request.data.get("environment_name") or "")[:64],
                browser=browser,
                run_mode=run_mode,
                tabs=recording["tabs"],
            )
            for item in recording["steps"]:
                PlaywrightStep.objects.create(case=case, **item)
        data = PlaywrightCaseSerializer(case, context=self.get_serializer_context()).data
        data.update({"steps": recording["steps"], "code": recording["code"]})
        return Response(data, status=status.HTTP_201_CREATED)

    @action(methods=["POST"], detail=True, url_path="sync-steps")
    def sync_steps(self, request, pk=None):
        case = self.get_object()
        items = request.data.get("steps", [])
        if not isinstance(items, list):
            return Response({"steps": "步骤列表格式不正确。"}, status=status.HTTP_400_BAD_REQUEST)
        ids = [item.get("id") for item in items if isinstance(item, dict) and item.get("id")]
        if len(ids) != len(set(ids)):
            return Response({"steps": "步骤列表不能包含重复项。"}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            existing = {step.pk: step for step in PlaywrightStep.objects.select_for_update().filter(case=case)}
            if any(step_id not in existing for step_id in ids):
                raise serializers.ValidationError({"steps": "步骤不存在或不属于当前用例。"})
            PlaywrightStep.objects.filter(case=case).exclude(pk__in=ids).delete()
            if ids:
                offset = max([step.order for step in existing.values()] + [len(items)]) + len(items) + 1
                PlaywrightStep.objects.filter(pk__in=ids).update(order=models.F("order") + offset)
            for order, item in enumerate(items, start=1):
                payload = dict(item)
                step_id = payload.pop("id", None)
                payload.pop("action_name", None)
                payload.update({"case": case.pk, "order": order})
                step_serializer = PlaywrightStepSerializer(
                    instance=existing.get(step_id), data=payload, context=self.get_serializer_context()
                )
                step_serializer.is_valid(raise_exception=True)
                step_serializer.save()
        return Response(PlaywrightStepSerializer(case.steps.all(), many=True).data)

    @action(methods=["POST"], detail=True, url_path="run")
    def run(self, request, pk=None):
        case = self.get_object()
        from .playwright_executor import execute_playwright_case
        try:
            return Response(execute_playwright_case(case))
        except Exception as exc:
            return Response({"passed": False, "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["POST"], detail=True, url_path="run-tab")
    def run_tab(self, request, pk=None):
        case = self.get_object()
        tab_key = str(request.data.get("tab_key") or "").strip()
        tabs = {
            str(item.get("key")): item
            for item in (case.tabs or [])
            if isinstance(item, dict) and item.get("key")
        }
        if not tab_key:
            return Response({"tab_key": "请选择要运行的 Tab。"}, status=status.HTTP_400_BAD_REQUEST)
        if tab_key not in tabs:
            return Response({"tab_key": "所选 Tab 不存在或已被删除。"}, status=status.HTTP_400_BAD_REQUEST)
        from .playwright_executor import execute_playwright_case
        try:
            result = execute_playwright_case(case, tab_key=tab_key)
            result["tab_name"] = str(tabs[tab_key].get("name") or "")
            return Response(result)
        except Exception as exc:
            return Response(
                {"passed": False, "tab_key": tab_key, "tab_name": tabs[tab_key].get("name", ""), "error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )


@extend_schema(tags=["Case_UI_Playwright"])
class PlaywrightStepViewSet(viewsets.ModelViewSet):
    queryset = PlaywrightStep.objects.select_related("case", "case__project")
    serializer_class = PlaywrightStepSerializer

    def get_queryset(self):
        queryset = self.queryset.filter(project_access_q(self.request.user, "case__project__")).distinct()
        case_id = self.request.query_params.get("case")
        return queryset.filter(case_id=case_id) if case_id else queryset

    def perform_create(self, serializer):
        require_project_access(self.request.user, serializer.validated_data["case"].project)
        serializer.save()

    def perform_update(self, serializer):
        require_project_access(self.request.user, self.get_object().case.project)
        serializer.save()

