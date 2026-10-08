from drf_spectacular.utils import extend_schema
from django.conf import settings
from django.db import models, transaction
from pathlib import Path
import hashlib
import shutil
import uuid
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from .models import Element, PlaywrightCase, PlaywrightScenarioFile, PlaywrightStep, UiCase, UiStep, UiUploadedFile
from .serializers import (
    ElementSerializer, PlaywrightCaseSerializer, PlaywrightScenarioFileSerializer,
    PlaywrightStepSerializer, UiCaseSerializer, UiStepSerializer,
    UiUploadedFileSerializer,
)
from .file_utils import UPLOAD_ROOT
from .recording import normalize_ui_recording
from .scenario_text import parse_ui_scenarios, validate_runnable_scenarios
from project.access import filter_project_cases, project_access_q, require_project_access, save_project_asset_update
from project.models import Environment, Project
from suite.run_metrics import build_overview
from account.tenancy import TenantScopedViewSetMixin, get_request_tenant, validate_tenant_relations
from account.tenant_runtime import ensure_tenant_storage_capacity, is_managed_storage_path, tenant_path


@extend_schema(tags=["Case_UI"])
class ElementViewSet(viewsets.ModelViewSet):
    queryset = Element.objects.select_related("project", "module", "created_by").all()
    serializer_class = ElementSerializer

    def get_queryset(self):
        queryset = self.queryset.filter(
            project__tenant=get_request_tenant(self.request),
        ).filter(project_access_q(self.request.user, "project__")).distinct()
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
        project = serializer.validated_data["project"]
        require_project_access(self.request.user, project)
        validate_tenant_relations(self.request, project=project)
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        save_project_asset_update(self.request.user, self.get_object(), serializer)


@extend_schema(tags=["Case_UI"])
class UiCaseViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = UiCase.objects.select_related("project", "created_by").prefetch_related("steps")
    serializer_class = UiCaseSerializer

    def get_queryset(self):
        return filter_project_cases(self.tenant_scope(self.queryset), self.request)

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        require_project_access(self.request.user, project)
        serializer.save(tenant=validate_tenant_relations(self.request, project=project), created_by=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        project = serializer.validated_data.get("project", instance.project)
        save_project_asset_update(self.request.user, instance, serializer, commit=False)
        serializer.save(tenant=validate_tenant_relations(self.request, case=instance, project=project))

    @extend_schema(tags=["Case_UI"])
    @action(detail=False, methods=["get"])
    def overview(self, request):
        """UI 用例列表页的聚合数据：平台 KPI + 每个用例的最近执行与通过率。

        用例级结果只能从测试计划的执行报告里取（即席试跑不落库），因此本接口
        反映的是「用例被编排进计划后的运行情况」。聚合逻辑见 suite/run_metrics.py。
        """
        tenant = get_request_tenant(request)
        rows = list(
            UiCase.objects
            .filter(tenant=tenant)
            .filter(project_access_q(request.user, "project__"))
            .values_list("id", "project_id")
        )
        return Response(build_overview(
            request.user, tenant,
            cache_scope="ui_case_overview",
            key_prefix="ui-",  # suite/models.py 组装计划时写成 f"ui-{id}"
            case_rows=rows,
        ))

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

    @action(methods=["POST"], detail=True, url_path="run")
    def run(self, request, pk=None):
        ui_case = self.get_object()
        if not ui_case.enabled:
            return Response({"detail": "UI 用例已停用。"}, status=status.HTTP_400_BAD_REQUEST)
        environment_id = request.data.get("environment")
        environment = (
            Environment.objects.filter(pk=environment_id, project=ui_case.project).first()
            if environment_id
            else Environment.objects.filter(
                project=ui_case.project, name=ui_case.environment_name,
            ).first()
        )
        if not environment:
            return Response(
                {"environment": "请先为 UI 用例选择当前项目可用的执行环境。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        steps = list(ui_case.steps.select_related("element").order_by("order", "id"))
        if not steps:
            return Response({"detail": "UI 用例没有可执行步骤。"}, status=status.HTTP_400_BAD_REQUEST)
        tabs = sorted(
            [item for item in (ui_case.tabs or []) if isinstance(item, dict)],
            key=lambda item: item.get("order", 0),
        )
        tab_names = {str(item.get("key")): str(item.get("name") or "") for item in tabs}
        case_data = {
            "id": ui_case.id,
            "name": ui_case.name,
            "browser": ui_case.browser,
            "run_mode": ui_case.run_mode,
            "tabs": tabs,
            "base_url": environment.base_url,
            "project_id": ui_case.project_id,
            "environment_name": environment.name,
            "steps": [
                {
                    "id": step.id,
                    "name": f"{step.get_action_display()} · {step.element.name if step.element else step.value or ''}".strip(" ·"),
                    "action": step.action,
                    "tab_key": step.tab_key,
                    "tab_name": tab_names.get(step.tab_key, ""),
                    "by": step.element.by if step.element else None,
                    "locator": step.element.value if step.element else None,
                    "element_name": step.element.name if step.element else "",
                    "value": step.value,
                    "options": step.options,
                    "continue_on_failure": step.continue_on_failure,
                }
                for step in steps
            ],
        }
        from fullstack_framework.commons.ui_executor import execute_ui_case
        try:
            execute_ui_case(case_data)
            return Response({"passed": True, "case_id": ui_case.id})
        except Exception as exc:
            return Response({"passed": False, "error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=["Case_UI"])
class UiStepViewSet(viewsets.ModelViewSet):
    queryset = UiStep.objects.select_related("ui_case", "ui_case__project", "element")
    serializer_class = UiStepSerializer

    def get_queryset(self):
        queryset = self.queryset.filter(
            project_access_q(self.request.user, "ui_case__project__"),
            ui_case__tenant=get_request_tenant(self.request),
        ).distinct()
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
        queryset = self.queryset.filter(
            project__tenant=get_request_tenant(self.request),
        ).filter(project_access_q(self.request.user, "project__")).distinct()
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
        project = Project.objects.filter(
            pk=project_id, tenant=get_request_tenant(request),
        ).first()
        if not project:
            return Response({"project": "所属项目不存在。"}, status=status.HTTP_400_BAD_REQUEST)
        require_project_access(request.user, project)
        try:
            ensure_tenant_storage_capacity(project.tenant, uploaded_file.size)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        tenant_upload_root = tenant_path(UPLOAD_ROOT, project.tenant_id)
        tenant_upload_root.mkdir(parents=True, exist_ok=True)
        original_name = Path(uploaded_file.name).name
        stored_path = tenant_upload_root / f"{uuid.uuid4().hex}_{original_name}"
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
        if is_managed_storage_path(path, "uploaded_ui_files", tenant=record.project.tenant_id):
            path.unlink(missing_ok=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Case_UI_Playwright"])
class PlaywrightCaseViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = PlaywrightCase.objects.select_related("project", "created_by").prefetch_related("steps")
    serializer_class = PlaywrightCaseSerializer

    def get_queryset(self):
        return filter_project_cases(self.tenant_scope(self.queryset), self.request)

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        require_project_access(self.request.user, project)
        serializer.save(tenant=validate_tenant_relations(self.request, project=project), created_by=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        project = serializer.validated_data.get("project", instance.project)
        save_project_asset_update(self.request.user, instance, serializer, commit=False)
        serializer.save(tenant=validate_tenant_relations(self.request, case=instance, project=project))

    @extend_schema(tags=["Case_UI"])
    @action(detail=False, methods=["get"])
    def overview(self, request):
        """智能用例列表页的聚合数据，结构与 UI 用例一致。

        注意报告里的 id 前缀是 ``playwright-ui-``，与普通 UI 用例的 ``ui-``
        不会互相误匹配（后者不以 ``ui-`` 开头）。
        """
        tenant = get_request_tenant(request)
        rows = list(
            PlaywrightCase.objects
            .filter(tenant=tenant)
            .filter(project_access_q(request.user, "project__"))
            .values_list("id", "project_id")
        )
        return Response(build_overview(
            request.user, tenant,
            cache_scope="playwright_case_overview",
            key_prefix="playwright-ui-",  # suite/models.py 组装计划时写成 f"playwright-ui-{id}"
            case_rows=rows,
        ))

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
        project = Project.objects.filter(
            pk=project_id, tenant=get_request_tenant(request),
        ).first()
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
                tenant=project.tenant,
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
        environment_id = request.data.get("environment")
        if environment_id:
            environment = Environment.objects.filter(pk=environment_id, project=case.project).first()
            if not environment:
                return Response({"environment": "请选择当前项目可用的执行环境。"}, status=status.HTTP_400_BAD_REQUEST)
            # 即席试跑只覆盖本次执行环境，不改写用例中保存的默认环境。
            case.environment_name = environment.name
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
class PlaywrightScenarioFileViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = PlaywrightScenarioFile.objects.select_related("project", "created_by")
    serializer_class = PlaywrightScenarioFileSerializer

    def get_queryset(self):
        queryset = self.tenant_scope(self.queryset).filter(
            project_access_q(self.request.user, "project__")
        ).distinct()
        project_id = self.request.query_params.get("project")
        return queryset.filter(project_id=project_id) if project_id else queryset

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        require_project_access(self.request.user, project)
        serializer.save(tenant=validate_tenant_relations(self.request, project=project), created_by=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        project = serializer.validated_data.get("project", instance.project)
        require_project_access(self.request.user, project)
        serializer.save(tenant=validate_tenant_relations(self.request, project=project))

    @action(methods=["POST"], detail=True, url_path="convert-to-smart-case")
    def convert_to_smart_case(self, request, pk=None):
        """按来源场景同步智能 UI 用例；重复转换更新原用例 ID。"""
        scenario_file = self.get_object()
        require_project_access(request.user, scenario_file.project)
        with transaction.atomic():
            scenario_file = PlaywrightScenarioFile.objects.select_for_update().get(pk=scenario_file.pk)
            try:
                scenarios = parse_ui_scenarios(scenario_file.content)
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            names = [scene["name"] for scene in scenarios]
            if len(names) != len(set(names)):
                return Response({"detail": "YAML 文件中存在同名场景，请先修改场景名称。"}, status=status.HTTP_400_BAD_REQUEST)
            scenario_ids = [scene["scenario_id"] for scene in scenarios if scene["scenario_id"]]
            if len(scenario_ids) != len(set(scenario_ids)):
                return Response({"detail": "YAML 文件中存在重复场景ID，请先修改场景ID。"}, status=status.HTTP_400_BAD_REQUEST)
            for scene in scenarios:
                if len(scene["name"]) > 64:
                    return Response({"detail": f"场景「{scene['name'][:30]}」名称超过智能用例的 64 字限制。"}, status=status.HTTP_400_BAD_REQUEST)
                if len(scene["description"]) > 250:
                    return Response({"detail": f"场景「{scene['name']}」描述超过智能用例的 250 字限制。"}, status=status.HTTP_400_BAD_REQUEST)
            linked = list(PlaywrightCase.objects.select_for_update().filter(
                tenant=scenario_file.tenant, project=scenario_file.project,
                source_yaml_file=scenario_file,
            ).prefetch_related("steps"))
            same_name_cases = list(PlaywrightCase.objects.select_for_update().filter(
                tenant=scenario_file.tenant, project=scenario_file.project, name__in=names,
            ).prefetch_related("steps"))
            used_ids = set()
            assignments = []
            legacy_names = set()
            for index, scene in enumerate(scenarios, start=1):
                identity = f"id:{scene['scenario_id']}" if scene["scenario_id"] else f"position:{index}"
                key = identity if len(identity) <= 128 else "hash:" + hashlib.sha256(identity.encode()).hexdigest()
                # 无 ID 的场景优先按名称匹配，重排文件时不会误更新另一场景。
                matches = (
                    [case for case in linked if case.name == scene["name"]]
                    if not scene["scenario_id"] else []
                )
                matches += [case for case in linked if case.source_yaml_scene_key == key and case not in matches]
                matches += [case for case in linked if case.name == scene["name"] and case not in matches]
                case = next((item for item in matches if item.pk not in used_ids), None)
                if case is None:
                    legacy = [item for item in same_name_cases if item.name == scene["name"]
                              and item.source_yaml_file_id is None and item.pk not in used_ids
                              and (not scenario_file.created_by_id
                                   or item.created_by_id == scenario_file.created_by_id)
                              and item.tabs == [{"key": "tab-1", "name": "场景步骤", "order": 1}]
                              and item.steps.all()
                              and all((step.options or {}).get("source_format") == "scenario_text"
                                      for step in item.steps.all())]
                    if len(legacy) == 1:
                        case = legacy[0]
                        legacy_names.add(scene["name"])
                if case:
                    used_ids.add(case.pk)
                assignments.append((scene, key, case))

            # 老版本没有来源字段：仅在当前项目其他 YAML 文件没有同名场景时认领。
            if legacy_names:
                for other in PlaywrightScenarioFile.objects.filter(
                    tenant=scenario_file.tenant, project=scenario_file.project,
                ).exclude(pk=scenario_file.pk).only("content"):
                    try:
                        other_names = {item["name"] for item in parse_ui_scenarios(other.content)}
                    except ValueError:
                        continue
                    if legacy_names & other_names:
                        return Response(
                            {"detail": "旧版同名智能用例的 YAML 来源不唯一，请先人工处理重名用例。"},
                            status=status.HTTP_409_CONFLICT,
                        )

            conflicts = sorted({item.name for item in same_name_cases if item.pk not in used_ids})
            if conflicts:
                return Response(
                    {"detail": f"当前项目已存在同名智能用例：{'、'.join(conflicts)}。请修改场景名称后再转换。"},
                    status=status.HTTP_409_CONFLICT,
                )
            for _, key, case in assignments:
                occupant = next((item for item in linked
                                 if item.source_yaml_scene_key == key and item.pk != getattr(case, "pk", None)), None)
                if occupant and occupant.pk not in used_ids:
                    return Response(
                        {"detail": "场景标识已被当前 YAML 的旧场景占用，请检查场景ID。"},
                        status=status.HTTP_409_CONFLICT,
                    )

            # 重排无 ID 场景时，先释放旧位置键，避免唯一约束在交换过程中误触发。
            for _, key, case in assignments:
                if case and case.source_yaml_file_id == scenario_file.pk and case.source_yaml_scene_key != key:
                    case.source_yaml_scene_key = f"temp:{uuid.uuid4().hex}"
                    case.save(update_fields=["source_yaml_scene_key"])

            converted = []
            created_count = 0
            updated_count = 0
            for scene, key, case in assignments:
                if case is None:
                    case = PlaywrightCase(
                        tenant=scenario_file.tenant, project=scenario_file.project,
                        created_by=request.user, tabs=[{"key": "tab-1", "name": "场景步骤", "order": 1}],
                    )
                    created_count += 1
                    change = "created"
                else:
                    updated_count += 1
                    change = "updated"
                case.name = scene["name"]
                case.description = scene["description"]
                case.browser = scenario_file.browser
                case.run_mode = scenario_file.run_mode
                case.environment_name = scenario_file.environment_name
                case.source_yaml_file = scenario_file
                case.source_yaml_scene_key = key
                case.save()
                if change == "updated":
                    case.steps.all().delete()
                for order, step in enumerate(scene["steps"], start=1):
                    serializer = PlaywrightStepSerializer(data={
                        "case": case.pk, "tab_key": "tab-1", "order": order,
                        "action": step["action"], "target": step["target"], "value": step["value"],
                        "options": {**step.get("options", {}), "source_format": "scenario_text"},
                    }, context=self.get_serializer_context())
                    serializer.is_valid(raise_exception=True)
                    serializer.save()
                converted.append({"id": case.pk, "name": case.name, "scenario_id": scene["scenario_id"],
                                  "step_count": len(scene["steps"]), "change": change})
        return Response({"count": len(converted), "created_count": created_count,
                         "updated_count": updated_count, "cases": converted},
                        status=status.HTTP_201_CREATED if created_count else status.HTTP_200_OK)

    @action(methods=["POST"], detail=False, url_path="preview")
    def preview(self, request):
        try:
            return Response({"scenarios": parse_ui_scenarios(request.data.get("content"))})
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

    @action(methods=["POST"], detail=True, url_path="run")
    def run(self, request, pk=None):
        scenario_file = self.get_object()
        if not scenario_file.environment_name:
            return Response({"environment_name": "请先选择执行环境。"}, status=status.HTTP_400_BAD_REQUEST)
        if not Environment.objects.filter(
            project_id=scenario_file.project_id, name=scenario_file.environment_name,
        ).exists():
            return Response({"environment_name": "执行环境不存在或不属于当前项目。"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            scenarios = parse_ui_scenarios(scenario_file.content)
            validate_runnable_scenarios(scenarios)
            from .file_utils import resolve_uploaded_file
            for scene in scenarios:
                for step in scene["steps"]:
                    if step["action"] == "upload_file":
                        for file_id in step["options"]["file_ids"]:
                            resolve_uploaded_file(file_id, scenario_file.project_id)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        from .playwright_executor import execute_playwright_scenario_group
        payloads = []
        for scene in scenarios:
            payloads.append({
                "id": None, "project_id": scenario_file.project_id,
                "name": scene["name"], "browser": scenario_file.browser,
                "run_mode": scenario_file.run_mode,
                "environment_name": scenario_file.environment_name,
                "steps": [{**step, "options": {**step.get("options", {}), "source_format": "scenario_text"}}
                          for step in scene["steps"]],
            })
        try:
            reports = execute_playwright_scenario_group(payloads, raise_on_failure=False)
            results = [
                {"scenario_id": scene["scenario_id"], "name": scene["name"],
                 "passed": bool(report.get("passed")), "report": report,
                 **({"error": report["error"]} if report.get("error") else {})}
                for scene, report in zip(scenarios, reports)
            ]
        except Exception as exc:
            results = [{"scenario_id": scene["scenario_id"], "name": scene["name"],
                        "passed": False, "error": str(exc)} for scene in scenarios]
        return Response({"passed": all(item["passed"] for item in results), "scenarios": results})


@extend_schema(tags=["Case_UI_Playwright"])
class PlaywrightStepViewSet(viewsets.ModelViewSet):
    queryset = PlaywrightStep.objects.select_related("case", "case__project")
    serializer_class = PlaywrightStepSerializer

    def get_queryset(self):
        queryset = self.queryset.filter(
            project_access_q(self.request.user, "case__project__"),
            case__tenant=get_request_tenant(self.request),
        ).distinct()
        case_id = self.request.query_params.get("case")
        return queryset.filter(case_id=case_id) if case_id else queryset

    def perform_create(self, serializer):
        require_project_access(self.request.user, serializer.validated_data["case"].project)
        serializer.save()

    def perform_update(self, serializer):
        require_project_access(self.request.user, self.get_object().case.project)
        serializer.save()
