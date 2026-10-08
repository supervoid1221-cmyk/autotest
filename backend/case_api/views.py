import shutil
import csv
import io
import json
import re
import tempfile
import uuid
from copy import deepcopy
from pathlib import Path

import yaml
from django.db import transaction
from django.db.models import F, Q
from django.conf import settings
from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework import status, viewsets

from project.models import Environment, Module, Project, ProjectVariable, response_indicates_expired_token
from project.runtime_token import RuntimeTokenState
from fullstack_framework.commons.ddt_util import ddt
from fullstack_framework.commons.api_executor import (
    execute_api_step,
    execute_api_step_with_failure_retry,
)
from fullstack_framework.commons.session import BeifanSession
from project.access import (
    save_project_asset_update,
    filter_all_project_access,
    project_access_q,
    require_project_access,
    require_projects_access,
)
from suite.run_metrics import build_overview
from account.tenancy import TenantScopedViewSetMixin, get_request_tenant, validate_tenant_relations
from account.tenant_runtime import ensure_tenant_storage_capacity, tenant_path

from .models import Endpoint, Scenario, ScenarioBranch, ScenarioFlowNode, ScenarioStep
from .recording import parse_recording_payload, sanitize_recorded_headers
from .file_utils import UPLOAD_ROOT
from .swagger_import import parse_swagger
from .swagger_links import selected_order, suggest_relations
from .serializers import (
    EndpointSerializer, ScenarioBranchSerializer, ScenarioFlowNodeSerializer,
    ScenarioSerializer, ScenarioStepSerializer,
)


def _environment_headers(environment, variables):
    """复用环境认证配置，并把登录获得的变量限制在本次调试运行中。"""
    with tempfile.TemporaryDirectory(prefix="scenario_debug_") as directory:
        headers = environment.prepare_auth(Path(directory), environment.name)
        extract_file = Path(directory) / "extract.yaml"
        if extract_file.exists():
            variables.update(yaml.safe_load(extract_file.read_text(encoding="utf-8")) or {})
    return headers


def _run_step(
    step, selected_environment, variables, case_data_override=None, http_session=None,
    runtime_token_state=None,
):
    if not step.endpoint:
        return {"step_id": step.id, "passed": False, "errors": ["未选择接口"], "response_body": ""}
    environment = Environment.objects.filter(project_id=step.endpoint.project_id, name=selected_environment.name).first()
    if not environment:
        return {"step_id": step.id, "passed": False, "errors": [f"项目「{step.endpoint.project.name}」未配置环境「{selected_environment.name}」"], "response_body": ""}
    http_session = http_session or BeifanSession()
    runtime_token_state = runtime_token_state or RuntimeTokenState(
        variables,
        ProjectVariable.values_by_project([step.endpoint.project_id]),
    )
    try:
        if case_data_override is None:
            headers = _environment_headers(environment, variables)
            case_data = step.endpoint.to_yaml_data(environment.base_url, headers, step.request_override)
            case_data = step.apply_request_target(case_data, environment.base_url)
            # 场景调试与套件执行保持相同的数据结构：先把步骤配置合并到
            # 接口用例，再统一展开 DDT。这样请求参数、数据提取、断言期望值
            # 和轮询配置中的 $ddt{字段名} 都会使用当前数据行的值。
            # 场景添加接口时已快照接口规则；此后始终使用场景步骤的
            # 独立配置。空对象表示场景明确删除全部规则，不再回退接口配置。
            case_data["extract"] = step.extract or {}
            case_data["post_sql"] = step.post_sql or []
            case_data["validate"] = step.validate or {}
            case_data["polling"] = step.polling or {}
            if case_data.get("parametrize"):
                # 场景编辑页直接运行单接口时，也按每行数据逐条执行。
                # 每行保留独立结果，便于页面和调用方展示实际执行次数。
                data_results = []
                for expanded_case in ddt(case_data):
                    item_result = _run_step(
                        step, selected_environment, variables, expanded_case, http_session,
                        runtime_token_state,
                    )
                    data_results.append({"name": expanded_case["test_name"], **item_result})
                last_result = data_results[-1]
                return {
                    **last_result,
                    "passed": all(item["passed"] for item in data_results),
                    "errors": [error for item in data_results for error in item.get("errors", [])],
                    "duration_ms": sum(item.get("duration_ms", 0) for item in data_results),
                    "data_driven_results": data_results,
                }
        else:
            case_data = case_data_override
        auth_refreshed = False

        def request_func(request_data, timeout, attempt):
            nonlocal auth_refreshed
            request_payload = dict(request_data)
            request_payload.setdefault("timeout", timeout)
            request_payload["interface_name"] = case_data.get("test_name") or step.endpoint.name
            runtime_token_state.apply(environment, request_payload)
            response = http_session.request(**request_payload)
            # 登录接口提取的 Token 失效后，先回退到运行开始时的
            # 项目 Token 并重试当前请求。不需要用例手工编写 ${token}。
            if response_indicates_expired_token(response) and runtime_token_state.discard_runtime_token(environment):
                runtime_token_state.apply(environment, request_payload)
                response = http_session.request(**request_payload)
            # 部分网关会用 HTTP 200 返回业务码 1023；此时缓存时间可能仍未到期，
            # 需要强制刷新认证并立即重试一次当前请求。
            if not auth_refreshed and response_indicates_expired_token(response):
                with tempfile.TemporaryDirectory(prefix="scenario_auth_refresh_") as refresh_directory:
                    refreshed_headers = environment.prepare_auth(
                        Path(refresh_directory), environment.name, force_refresh=True
                    )
                case_data["request"].setdefault("headers", {}).update(refreshed_headers)
                request_payload["headers"] = {**request_payload.get("headers", {}), **refreshed_headers}
                auth_refreshed = True
                response = http_session.request(**request_payload)
            return response

        execution = execute_api_step_with_failure_retry(
            lambda: execute_api_step(
                request_template=case_data["request"],
                extract=case_data.get("extract"),
                validate=case_data.get("validate"),
                polling=case_data.get("polling"),
                post_sql=case_data.get("post_sql"),
                variables=variables,
                project_id=step.endpoint.project_id,
                environment_name=environment.name,
                request_func=request_func,
                on_success=lambda values: runtime_token_state.observe_extracted(environment, values),
            ),
            enabled=step.retry_on_failure,
            retry_count=step.failure_retry_count,
        )
        return {
            "step_id": step.id,
            "passed": execution.passed,
            "status_code": getattr(execution.response, "status_code", None),
            "duration_ms": round(execution.duration_seconds * 1000, 2),
            "response_body": execution.response_body[:200000],
            # 仅用于场景编辑页的上下游变量推荐。不会写入数据库或测试报告。
            "response_json": execution.response_json,
            "response_headers": dict(getattr(execution.response, "headers", {}) or {}),
            "errors": execution.errors,
            "request": execution.request,
            "assertions": execution.assertions,
            "extracted": execution.extracted,
            "attempts": execution.attempts,
        }
    except Exception as exc:
        return {"step_id": step.id, "passed": False, "errors": [str(exc)], "response_body": ""}


def json_dumps(value):
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


@extend_schema(tags=["Case_API"])
class EndpointViewSet(viewsets.ModelViewSet):
    queryset = Endpoint.objects.select_related("project", "module", "created_by").all()
    serializer_class = EndpointSerializer

    def get_queryset(self):
        queryset = self.queryset.filter(
            project__tenant=get_request_tenant(self.request),
        ).filter(project_access_q(self.request.user, "project__")).distinct()
        project_id = self.request.query_params.get("project")
        module_id = self.request.query_params.get("module")
        method = self.request.query_params.get("method")
        search = (self.request.query_params.get("search") or "").strip()
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        if module_id:
            queryset = queryset.filter(module_id=module_id)
        elif self.request.query_params.get("unassigned") in {"true", "1"}:
            queryset = queryset.filter(module__isnull=True)
        if method:
            queryset = queryset.filter(method__iexact=method)
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(url__icontains=search))
        return queryset

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        require_project_access(self.request.user, project)
        validate_tenant_relations(self.request, project=project)
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        project = serializer.validated_data.get("project", instance.project)
        save_project_asset_update(self.request.user, instance, serializer, commit=False)
        validate_tenant_relations(self.request, project=project)
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        """删除接口幂等化，避免界面短暂缓存的重复删除显示 404。"""
        try:
            return super().destroy(request, *args, **kwargs)
        except Http404:
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="import-swagger")
    def import_swagger(self, request):
        """预览/导入 Swagger 内容；服务端不抓取 URL，避免 SSRF。"""
        try:
            project_id = int(request.data.get("project"))
        except (TypeError, ValueError):
            return Response({"detail": "请选择所属项目。"}, status=400)
        project = Project.objects.filter(pk=project_id, tenant=get_request_tenant(request)).first()
        if not project:
            return Response({"detail": "项目不存在。"}, status=400)
        require_project_access(request.user, project)
        module = None
        if request.data.get("module") not in (None, ""):
            try:
                module_id = int(request.data["module"])
            except (TypeError, ValueError):
                return Response({"detail": "所属模块无效。"}, status=400)
            module = Module.objects.filter(pk=module_id, project=project).first()
            if not module:
                return Response({"detail": "所选模块不属于当前项目。"}, status=400)
        try:
            entries = parse_swagger(request.data.get("content"))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        suggestions = suggest_relations(entries)
        existing = set(Endpoint.objects.filter(project=project).values_list("method", "url"))
        seen = set()
        for entry in entries:
            key = (entry["method"], entry["url"])
            entry["duplicate"] = key in existing or key in seen
            if module:
                entry["module_name"] = module.name
            seen.add(key)
        if not request.data.get("save"):
            return Response({"count": len(entries), "new": sum(not entry["duplicate"] for entry in entries), "modules": sorted({entry["module_name"] for entry in entries if not entry["duplicate"]}), "endpoints": entries, "relations": suggestions})
        create_scenario = request.data.get("create_scenario") is True
        relation_ids = request.data.get("relation_ids", [])
        if not isinstance(relation_ids, list) or any(not isinstance(item, str) for item in relation_ids):
            return Response({"detail": "接口关联选择无效。"}, status=400)
        selected = [item for item in suggestions if item["id"] in set(relation_ids)]
        if create_scenario and (not selected or len(selected) != len(set(relation_ids))):
            return Response({"detail": "请选择有效的接口关联后再生成场景。"}, status=400)
        scenario_name = str(request.data.get("scenario_name") or "Swagger 关联场景").strip()
        if create_scenario and (not scenario_name or len(scenario_name) > 64):
            return Response({"detail": "场景名称不能为空且不能超过 64 个字符。"}, status=400)
        scenario_order = []
        step_extract, step_overrides, step_urls = {}, {}, {}
        if create_scenario:
            try:
                scenario_order = selected_order(selected)
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=400)
            for item in selected:
                source, target = item["source"], item["target"]
                step_extract.setdefault(source, {})[item["variable"]] = {
                    "mode": "jsonpath", "source": "json", "expression": item["response_path"],
                    "index": 0, "processors": [{"type": "required"}],
                }
                reference = "${" + item["variable"] + "}"
                if item["target_field"] == "path":
                    step_urls[target] = step_urls.get(target, entries[target]["url"]).replace("{" + item["target_key"] + "}", reference)
                else:
                    step_overrides.setdefault(target, {}).setdefault(item["target_field"], {})[item["target_key"]] = reference
            for index in scenario_order:
                if re.search(r"(?<!\$)\{[^{}]+\}", step_urls.get(index, entries[index]["url"])):
                    return Response({"detail": f"接口「{entries[index]['name']}」仍有未关联的路径参数，请补充关联后再生成场景。"}, status=400)
        created = skipped = 0
        with transaction.atomic():
            # 并发导入同一项目时序列化写入，避免重复创建。
            Project.objects.select_for_update().get(pk=project.pk)
            if create_scenario and Scenario.objects.filter(tenant=project.tenant, project=project, name=scenario_name).exists():
                return Response({"detail": "当前项目已有同名场景，请修改场景名称。"}, status=409)
            existing = set(Endpoint.objects.filter(project=project).values_list("method", "url"))
            endpoint_map = {(method, url): endpoint_id for endpoint_id, method, url in Endpoint.objects.filter(project=project).values_list("id", "method", "url")}
            module_cache = {}
            for entry in entries:
                key = (entry["method"], entry["url"])
                if key in existing:
                    skipped += 1
                    continue
                entry.pop("duplicate", None)
                module_name = entry.pop("module_name")
                for metadata_key in ("operation_id", "response_fields", "response_links", "request_targets"):
                    entry.pop(metadata_key, None)
                if module is None:
                    if module_name not in module_cache:
                        module_cache[module_name], _ = Module.objects.get_or_create(
                            project=project, name=module_name,
                            defaults={"created_by": request.user},
                        )
                    target_module = module_cache[module_name]
                else:
                    target_module = module
                serializer = self.get_serializer(data={**entry, "project": project.pk, "module": target_module.pk})
                serializer.is_valid(raise_exception=True)
                endpoint = serializer.save(created_by=request.user)
                existing.add(key)
                endpoint_map[key] = endpoint.pk
                created += 1
            scenario_id = None
            if create_scenario:
                scenario = Scenario.objects.create(
                    tenant=project.tenant, project=project, created_by=request.user,
                    name=scenario_name, description="由 Swagger 接口关联生成，请确认参数与断言后运行。",
                )
                scenario.projects.add(project)
                for order, index in enumerate(scenario_order, start=1):
                    entry = entries[index]
                    endpoint = Endpoint.objects.get(pk=endpoint_map[(entry["method"], entry["url"])])
                    step = ScenarioStep.objects.create(
                        scenario=scenario, endpoint=endpoint, order=order,
                        request_url=step_urls.get(index, ""),
                        request_override=step_overrides.get(index, {}),
                        extract={**(endpoint.extract or {}), **step_extract.get(index, {})},
                        validate=deepcopy(endpoint.validate or {}),
                        continue_on_failure=False,
                    )
                    # ScenarioStep 的 post_save 信号会按创建顺序生成主流程节点。
                scenario_id = scenario.pk
        result = {"created": created, "skipped": skipped}
        if scenario_id is not None:
            result["scenario_id"] = scenario_id
        return Response(result)

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        """使用指定项目环境执行已保存的单个接口。"""
        endpoint = self.get_object()
        environment_id = request.data.get("environment")
        try:
            environment_id = int(environment_id)
        except (TypeError, ValueError):
            return Response({"detail": "请选择执行环境。"}, status=status.HTTP_400_BAD_REQUEST)

        environment = Environment.objects.filter(
            pk=environment_id,
            project_id=endpoint.project_id,
        ).first()
        if not environment:
            return Response(
                {"detail": "所选环境不存在或不属于接口项目。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        variables = ProjectVariable.values_for_projects([endpoint.project_id])
        if "data_row" in request.data:
            row_index = request.data["data_row"]
            if type(row_index) is not int or row_index < 0 or row_index >= len(endpoint.parametrize or []) - 1:
                return Response({"detail": "数据行不存在。"}, status=400)
            endpoint.parametrize = [endpoint.parametrize[0], endpoint.parametrize[row_index + 1]]
            endpoint.dataset_options = {"enabled": True}
        # 单接口调试不创建临时场景数据，使用未落库的步骤对象复用统一执行器。
        step = ScenarioStep(
            endpoint=endpoint,
            request_override={},
            extract=endpoint.extract or {},
            validate=endpoint.validate or {},
            post_sql=[],
            polling={},
        )
        result = _run_step(step, environment, variables)
        return Response({"environment": environment.name, **result})

    @action(detail=False, methods=["post"], url_path="import-dataset", parser_classes=[MultiPartParser, FormParser])
    def import_dataset(self, request):
        uploaded = request.FILES.get("file")
        if not uploaded or uploaded.size > 2 * 1024 * 1024:
            return Response({"detail": "请选择 2 MB 以内的 CSV 或 JSON 文件。"}, status=400)
        try:
            content = uploaded.read().decode("utf-8-sig")
            suffix = Path(uploaded.name).suffix.lower()
            if suffix == ".csv":
                table = list(csv.reader(io.StringIO(content)))
                fields, rows = table[0], table[1:]
            elif suffix == ".json":
                records = json.loads(content)
                if not isinstance(records, list) or not records or any(not isinstance(item, dict) for item in records):
                    raise ValueError("JSON 必须是对象数组。")
                fields = list(dict.fromkeys(key for item in records for key in item))
                rows = [[item.get(key) for key in fields] for item in records]
            else:
                raise ValueError("仅支持 CSV 和 JSON 文件。")
            fields = [str(field).strip() for field in fields]
            from fullstack_framework.commons.ddt_util import _validate_parametrize
            _validate_parametrize([fields, *rows])
            if len(rows) > 500 or len(fields) > 50:
                raise ValueError("数据集最多支持 500 行、50 列。")
            if any(not re.fullmatch(r'[A-Za-z_]\w*', field) for field in fields):
                raise ValueError("字段名须以英文字母或下划线开头，只包含字母、数字、下划线。")
            return Response({"fields": fields, "rows": rows, "filename": uploaded.name})
        except (ValueError, IndexError, UnicodeError, csv.Error) as exc:
            return Response({"detail": str(exc) or "数据文件为空或格式不正确。"}, status=400)

    @action(detail=False, methods=["post"], url_path="upload-file", parser_classes=[MultiPartParser, FormParser])
    def upload_file(self, request):
        """上传接口测试所需的附件，返回可写入 Endpoint.files 的安全文件描述。

        这个 action 原先挂在 EndpointModuleViewSet 上，而前端请求的是
        ``/case_api/endpoint/upload-file/``，两边对不上，附件上传一直是 404。
        目录共享改造删掉了那个 ViewSet，顺手把它挪回本类。
        """
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"detail": "请选择需要上传的文件。"}, status=400)
        if uploaded_file.size > 100 * 1024 * 1024:
            return Response({"detail": "单个文件不能超过 100MB。"}, status=400)

        tenant = get_request_tenant(request)
        try:
            ensure_tenant_storage_capacity(tenant, uploaded_file.size)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        tenant_upload_root = tenant_path(UPLOAD_ROOT, tenant.pk)
        tenant_upload_root.mkdir(parents=True, exist_ok=True)
        original_name = Path(uploaded_file.name).name
        saved_name = f"{uuid.uuid4().hex}_{original_name}"
        saved_path = tenant_upload_root / saved_name
        with saved_path.open("wb") as destination:
            shutil.copyfileobj(uploaded_file, destination)
        return Response({
            "name": original_name,
            "path": str(saved_path.relative_to(settings.BASE_DIR)),
            "size": uploaded_file.size,
        })


@extend_schema(tags=["Case_API"])
class RecordingViewSet(viewsets.ViewSet):
    """录制数据的解析与批量落库，不保存原始敏感请求内容。"""

    @action(detail=False, methods=["post"])
    def parse(self, request):
        records = parse_recording_payload(request.data)
        return Response({"records": records, "count": len(records)})

    @action(detail=False, methods=["post"])
    def import_records(self, request):
        project_id = request.data.get("project")
        module_id = request.data.get("module")
        conflict_mode = request.data.get("conflict_mode", "skip")
        create_scenario = bool(request.data.get("create_scenario", False))
        scenario_name = str(request.data.get("scenario_name") or "录制场景").strip()[:64]
        if conflict_mode not in {"skip", "overwrite", "copy"}:
            return Response({"detail": "重复处理方式不合法。"}, status=400)
        try:
            project = Project.objects.get(pk=project_id, tenant=get_request_tenant(request))
        except (Project.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "请选择有效项目。"}, status=400)
        require_project_access(request.user, project)
        module = Module.objects.filter(pk=module_id, project=project).first()
        if not module:
            return Response({"detail": "请选择当前项目下的模块。"}, status=400)
        records = [item for item in request.data.get("records", []) if isinstance(item, dict) and item.get("selected", True)]
        if not records:
            return Response({"detail": "请至少选择一条录制请求。"}, status=400)
        created, updated, skipped, endpoint_ids = 0, 0, 0, []
        with transaction.atomic():
            for index, record in enumerate(records, start=1):
                method, url = str(record.get("method") or "GET").upper(), str(record.get("url") or "").strip()
                if not url:
                    skipped += 1
                    continue
                existing = Endpoint.objects.filter(project=project, module=module, method=method, url=url).first()
                if existing and conflict_mode == "skip":
                    skipped += 1
                    continue
                name = str(record.get("name") or f"录制接口 {index}").strip()[:32]
                payload = {
                    "name": name or f"录制接口 {index}", "project": project, "module": module,
                    "method": method, "url": url,
                    "headers": sanitize_recorded_headers(record.get("headers")),
                    "params": record.get("params") or {}, "data": record.get("data") or {},
                    "json": record.get("json") or {}, "cookies": {}, "files": {},
                }
                if existing and conflict_mode == "overwrite":
                    for field, value in payload.items():
                        setattr(existing, field, value)
                    existing.save()
                    endpoint = existing
                    updated += 1
                else:
                    if existing and conflict_mode == "copy":
                        payload["name"] = f"{payload['name'][:27]}（录制）"
                    endpoint = Endpoint.objects.create(created_by=request.user, **payload)
                    created += 1
                endpoint_ids.append((endpoint.id, record.get("recommended_assertions") or {}))
            scenario_id = None
            if create_scenario and endpoint_ids:
                scenario = Scenario.objects.create(
                    tenant=project.tenant, project=project, created_by=request.user,
                    name=scenario_name or "录制场景", description="由接口录制自动生成",
                )
                scenario.projects.add(project)
                for order, (endpoint_id, assertions) in enumerate(endpoint_ids, start=1):
                    ScenarioStep.objects.create(scenario=scenario, endpoint_id=endpoint_id, order=order, validate=assertions)
                scenario_id = scenario.id
        return Response({"created": created, "updated": updated, "skipped": skipped, "scenario_id": scenario_id})



@extend_schema(tags=["Case_API"])
class ScenarioViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = Scenario.objects.select_related("project", "created_by").all()
    serializer_class = ScenarioSerializer

    def get_queryset(self):
        queryset = filter_all_project_access(
            self.tenant_scope(self.queryset),
            self.request.user,
            "project",
            "projects",
            ("steps__endpoint__project",),
        )
        name = str(self.request.query_params.get("name") or "").strip()
        if name:
            queryset = queryset.filter(name__icontains=name)
        project_id = self.request.query_params.get("project")
        if project_id:
            try:
                project_id = int(project_id)
            except (TypeError, ValueError):
                return queryset.none()
            if project_id <= 0:
                return queryset.none()
            queryset = queryset.filter(
                Q(project_id=project_id)
                | Q(projects__id=project_id)
                | Q(steps__endpoint__project_id=project_id)
            ).distinct()
        return queryset.order_by("-created_at", "-id")

    def perform_create(self, serializer):
        projects = serializer.validated_data.get("projects", [])
        require_projects_access(self.request.user, projects)
        tenant = validate_tenant_relations(self.request, projects=list(projects))
        serializer.save(tenant=tenant, created_by=self.request.user)

    def perform_update(self, serializer):
        scenario = self.get_object()
        require_project_access(self.request.user, scenario.project)
        require_projects_access(self.request.user, scenario.projects.all())
        require_projects_access(
            self.request.user,
            serializer.validated_data.get("projects", scenario.projects.all()),
        )
        projects = serializer.validated_data.get("projects", scenario.projects.all())
        validate_tenant_relations(self.request, scenario=scenario, projects=list(projects))
        serializer.save(tenant=self.current_tenant())

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        scenario = self.get_object()
        project_ids = [scenario.project_id, *scenario.projects.values_list("id", flat=True)]
        environment_id = request.data.get("environment")
        environment = Environment.objects.filter(
            pk=environment_id, project_id__in=project_ids,
        ).first()
        if not environment:
            return Response({"detail": "所选环境不存在或不属于场景关联项目。"}, status=400)
        variables = ProjectVariable.values_for_projects(project_ids)
        runtime_token_state = RuntimeTokenState(
            variables,
            ProjectVariable.values_by_project(project_ids),
        )
        http_session = BeifanSession()
        from .flow import execute_scenario_flow

        payload = execute_scenario_flow(
            scenario,
            variables,
            lambda step: _run_step(
                step, environment, variables, http_session=http_session,
                runtime_token_state=runtime_token_state,
            ),
        )
        return Response(payload)

    @extend_schema(tags=["Case_API"])
    @action(detail=False, methods=["get"])
    def overview(self, request):
        """场景列表页的聚合数据：平台 KPI + 每个场景的最近执行与通过率。

        场景级结果只能从测试计划的执行报告里取（即席执行不落库），因此本接口
        反映的是「场景被编排进计划后的运行情况」，不是列表页上试跑的结果。
        聚合逻辑与 UI / 智能 / App 用例共用，见 suite/run_metrics.py。
        """
        tenant = get_request_tenant(request)
        rows = list(
            filter_all_project_access(
                Scenario.objects.filter(tenant=tenant), request.user,
                "project", "projects", ("steps__endpoint__project",),
            ).values_list("id", "project_id")
        )
        return Response(build_overview(
            request.user, tenant,
            cache_scope="scenario_overview",
            key_prefix="",  # 场景在报告里的 id 是裸整数，没有前缀。
            case_rows=rows,
        ))


@extend_schema(tags=["Case_API"])
class ScenarioStepViewSet(viewsets.ModelViewSet):
    queryset = ScenarioStep.objects.select_related("scenario", "endpoint").all()
    serializer_class = ScenarioStepSerializer

    def get_queryset(self):
        return filter_all_project_access(
            self.queryset.filter(scenario__tenant=get_request_tenant(self.request)),
            self.request.user,
            "scenario__project",
            "scenario__projects",
            ("scenario__steps__endpoint__project",),
        )

    def _require_scenario_access(self, scenario):
        require_project_access(self.request.user, scenario.project)
        require_projects_access(self.request.user, scenario.projects.all())

    def perform_create(self, serializer):
        scenario = serializer.validated_data["scenario"]
        endpoint = serializer.validated_data["endpoint"]
        self._require_scenario_access(scenario)
        if not scenario.projects.filter(pk=endpoint.project_id).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"endpoint": "接口所属项目未关联到该场景。"})
        require_project_access(self.request.user, endpoint.project)
        # 首次添加时复制接口详情的规则，形成场景独立快照。
        # 后续接口详情变更不会影响已生成场景。
        serializer.save(
            extract=deepcopy(endpoint.extract or {}),
            validate=deepcopy(endpoint.validate or {}),
        )

    def perform_update(self, serializer):
        step = self.get_object()
        endpoint = serializer.validated_data.get("endpoint", step.endpoint)
        scenario = serializer.validated_data.get("scenario", step.scenario)
        self._require_scenario_access(step.scenario)
        self._require_scenario_access(scenario)
        if not scenario.projects.filter(pk=endpoint.project_id).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"endpoint": "接口所属项目未关联到该场景。"})
        require_project_access(self.request.user, endpoint.project)
        serializer.save()

    def update(self, request, *args, **kwargs):
        """步骤配置保存只更新提交字段，避免将旧 order 写回导致排序唯一约束冲突。"""
        kwargs["partial"] = True
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """已随旧接口删除的缓存步骤再次删除时视为已完成。"""
        try:
            return super().destroy(request, *args, **kwargs)
        except Http404:
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        step = self.get_object()
        project_ids = [step.scenario.project_id, *step.scenario.projects.values_list("id", flat=True)]
        environment_id = request.data.get("environment")
        environment = Environment.objects.filter(
            pk=environment_id, project_id__in=project_ids,
        ).first()
        if not environment:
            return Response({"detail": "所选环境不存在或不属于场景关联项目。"}, status=400)
        variables = ProjectVariable.values_for_projects(project_ids)
        return Response(_run_step(step, environment, variables))

    @action(detail=False, methods=["post"])
    def reorder(self, request):
        """事务化重排，避免交换顺序时触发 (scenario, order) 唯一约束。"""
        scenario_id = request.data.get("scenario")
        step_ids = request.data.get("step_ids", [])
        if not scenario_id or not isinstance(step_ids, list) or not step_ids:
            return Response({"detail": "请提供场景和步骤顺序。"}, status=400)

        scenario = filter_all_project_access(
            Scenario.objects.filter(tenant=get_request_tenant(request)),
            request.user,
            "project",
            "projects",
            ("steps__endpoint__project",),
        ).filter(pk=scenario_id).first()
        if not scenario:
            return Response({"detail": "场景不存在或无权访问。"}, status=status.HTTP_404_NOT_FOUND)

        steps = list(self.get_queryset().filter(scenario=scenario, id__in=step_ids))
        if len(steps) != len(step_ids) or len(set(step_ids)) != len(step_ids):
            return Response({"detail": "步骤列表不合法。"}, status=400)

        with transaction.atomic():
            # 先整体平移到不冲突的序号区间，再写入目标顺序。
            ScenarioStep.objects.filter(scenario_id=scenario_id, id__in=step_ids).update(order=F("order") + 1000000)
            for order, step_id in enumerate(step_ids, start=1):
                ScenarioStep.objects.filter(pk=step_id, scenario_id=scenario_id).update(order=order)
        return Response({"detail": "排序已更新。"})


@extend_schema(tags=["Case_API"])
class ScenarioFlowNodeViewSet(viewsets.ModelViewSet):
    serializer_class = ScenarioFlowNodeSerializer
    queryset = ScenarioFlowNode.objects.select_related("scenario", "step", "step__endpoint", "parent_branch").prefetch_related("branches", "branches__nodes", "branches__nodes__step", "branches__nodes__step__endpoint")

    def get_queryset(self):
        queryset = filter_all_project_access(
            self.queryset.filter(scenario__tenant=get_request_tenant(self.request)),
            self.request.user,
            "scenario__project",
            "scenario__projects",
            ("scenario__steps__endpoint__project",),
        )
        scenario_id = self.request.query_params.get("scenario")
        parent_branch_id = self.request.query_params.get("parent_branch")
        if scenario_id:
            queryset = queryset.filter(scenario_id=scenario_id)
        if parent_branch_id:
            queryset = queryset.filter(parent_branch_id=parent_branch_id)
        elif self.request.query_params.get("main") in {"true", "1"}:
            queryset = queryset.filter(parent_branch__isnull=True)
        return queryset.order_by("parent_branch_id", "order", "id")

    def perform_create(self, serializer):
        scenario = serializer.validated_data["scenario"]
        require_project_access(self.request.user, scenario.project)
        require_projects_access(self.request.user, scenario.projects.all())
        serializer.save()

    def perform_update(self, serializer):
        current_scenario = self.get_object().scenario
        scenario = serializer.validated_data.get("scenario", current_scenario)
        require_project_access(self.request.user, current_scenario.project)
        require_projects_access(self.request.user, current_scenario.projects.all())
        require_project_access(self.request.user, scenario.project)
        require_projects_access(self.request.user, scenario.projects.all())
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        try:
            node = self.get_object()
        except Http404:
            # 接口旧版本曾级联删除流程节点；前端缓存再次发起删除应保持幂等。
            return Response(status=status.HTTP_204_NO_CONTENT)
        require_project_access(request.user, node.scenario.project)
        step_ids = list(ScenarioFlowNode.objects.filter(
            Q(pk=node.pk) | Q(parent_branch__condition_node=node)
        ).exclude(step_id=None).values_list("step_id", flat=True))
        node.delete()
        if step_ids:
            ScenarioStep.objects.filter(pk__in=step_ids).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"])
    def reorder(self, request):
        scenario_id = request.data.get("scenario")
        node_ids = request.data.get("node_ids", [])
        parent_branch_id = request.data.get("parent_branch")
        if not scenario_id or not isinstance(node_ids, list) or len(node_ids) != len(set(node_ids)):
            return Response({"detail": "节点顺序格式不正确。"}, status=status.HTTP_400_BAD_REQUEST)
        scenario = filter_all_project_access(
            Scenario.objects.filter(tenant=get_request_tenant(request)),
            request.user,
            "project",
            "projects",
            ("steps__endpoint__project",),
        ).filter(pk=scenario_id).first()
        if not scenario:
            return Response({"detail": "场景不存在或无权访问。"}, status=status.HTTP_404_NOT_FOUND)
        nodes = list(self.get_queryset().filter(scenario=scenario, pk__in=node_ids))
        if len(nodes) != len(node_ids):
            return Response({"detail": "节点不存在或不属于当前场景。"}, status=status.HTTP_400_BAD_REQUEST)
        expected_branch = int(parent_branch_id) if parent_branch_id else None
        if any(node.parent_branch_id != expected_branch for node in nodes):
            return Response({"detail": "节点不属于同一流程层级。"}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            ScenarioFlowNode.objects.filter(pk__in=node_ids).update(order=F("order") + 1000000)
            for index, node_id in enumerate(node_ids, start=1):
                ScenarioFlowNode.objects.filter(pk=node_id).update(order=index)
        return Response({"detail": "节点顺序已更新。"})


@extend_schema(tags=["Case_API"])
class ScenarioBranchViewSet(viewsets.ModelViewSet):
    serializer_class = ScenarioBranchSerializer
    queryset = ScenarioBranch.objects.select_related("condition_node", "condition_node__scenario").prefetch_related("nodes", "nodes__step", "nodes__step__endpoint")

    def get_queryset(self):
        queryset = filter_all_project_access(
            self.queryset.filter(condition_node__scenario__tenant=get_request_tenant(self.request)),
            self.request.user,
            "condition_node__scenario__project",
            "condition_node__scenario__projects",
            ("condition_node__scenario__steps__endpoint__project",),
        )
        condition_node_id = self.request.query_params.get("condition_node")
        return queryset.filter(condition_node_id=condition_node_id) if condition_node_id else queryset

    def perform_create(self, serializer):
        scenario = serializer.validated_data["condition_node"].scenario
        require_project_access(self.request.user, scenario.project)
        require_projects_access(self.request.user, scenario.projects.all())
        serializer.save()

    def perform_update(self, serializer):
        current_scenario = self.get_object().condition_node.scenario
        condition_node = serializer.validated_data.get("condition_node", self.get_object().condition_node)
        scenario = condition_node.scenario
        require_project_access(self.request.user, current_scenario.project)
        require_projects_access(self.request.user, current_scenario.projects.all())
        require_project_access(self.request.user, scenario.project)
        require_projects_access(self.request.user, scenario.projects.all())
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        branch = self.get_object()
        require_project_access(request.user, branch.condition_node.scenario.project)
        step_ids = list(branch.nodes.exclude(step_id=None).values_list("step_id", flat=True))
        branch.delete()
        if step_ids:
            ScenarioStep.objects.filter(pk__in=step_ids).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
