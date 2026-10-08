import os
import signal

from django.conf import settings
from django.http import Http404
from copy import deepcopy
from pathlib import Path
from django.utils import timezone
from django.views.static import serve
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from django.db.models import Count, F, IntegerField, OuterRef, Prefetch, Q, Subquery, Value, Window
from django.db.models.functions import Coalesce, RowNumber
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

# rest_framework.permissions.IsAuthenticated
from .models import (
    NotificationChannel,
    NotificationDelivery,
    NotificationRule,
    RunResult,
    Suite,
    SuiteAppCase,
    SuiteExecutionItem,
    SuitePlaywrightCase,
    SuiteScenario,
    SuiteUiCase,
)
from .serializers import (
    RECENT_RUN_LIMIT,
    NotificationChannelSerializer,
    NotificationDeliverySerializer,
    NotificationRuleSerializer,
    RunResultSerializer,
    SuiteScenarioSerializer,
    SuiteSerializer,
)
from project.access import project_access_q, require_project_access, require_projects_access
from case_api.models import Scenario
from case_app.models import AppCase
from case_ui.models import PlaywrightCase, PlaywrightScenarioFile, UiCase
from .reporting import merge_ui_runtime_results
from .access import accessible_suites, filter_suite_access, filter_suite_project, require_suite_access
from account.tenancy import TenantScopedViewSetMixin, get_request_tenant, validate_tenant_relations
from account.access import display_name
from account.tenant_runtime import is_managed_storage_path


def _request_actor_name(request):
    """返回适合写入业务记录的当前用户名称快照（执行人 / 创建人共用）。

    实现放在 account.access.display_name，供 execution_control.sync 等非请求
    上下文复用同一套取名规则（先姓名、后用户名、兜底「系统」）。
    """
    return display_name(getattr(request, "user", None))


def _execution_log_text(result):
    """读取执行器最近日志，不包含报告正文。"""
    path = Path(str(result.path))
    chunks = []
    from .execution_log import sanitize_log_text

    # 优先展示结构化业务日志。旧任务或启动前异常时，再回退到底层日志。
    execution_log = path / "logs/execution.log"
    log_filenames = (
        ("logs/execution.log",)
        if execution_log.exists()
        else ("logs/runner.log", "logs/pytest.log")
    )
    for filename in log_filenames:
        log_path = path / filename
        if log_path.exists():
            try:
                chunks.append(
                    sanitize_log_text(
                        log_path.read_text(encoding="utf-8", errors="replace")[-12000:]
                    )
                )
            except OSError:
                pass
    return "\n".join(chunks)


def _run_is_active(result):
    return result.status in (
        result.RunStatus.Ready,
        result.RunStatus.Running,
        result.RunStatus.Reporting,
        result.RunStatus.Paused,
    )


def _no_cache_response(data):
    response = Response(data)
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    return response


class NotificationChannelViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationChannelSerializer
    queryset = NotificationChannel.objects.prefetch_related("projects")
    def get_queryset(self):
        return self.queryset.filter(
            projects__tenant=get_request_tenant(self.request),
        ).filter(project_access_q(self.request.user, "projects__")).distinct()
    def perform_create(self, serializer):
        require_projects_access(self.request.user, serializer.validated_data["projects"])
        validate_tenant_relations(self.request, projects=list(serializer.validated_data["projects"]))
        serializer.save()
    def perform_update(self, serializer):
        require_projects_access(self.request.user, serializer.instance.projects.all())
        require_projects_access(
            self.request.user,
            serializer.validated_data.get("projects", serializer.instance.projects.all()),
        )
        validate_tenant_relations(
            self.request,
            projects=list(serializer.validated_data.get("projects", serializer.instance.projects.all())),
        )
        serializer.save()
    def perform_destroy(self, instance):
        require_projects_access(self.request.user, instance.projects.all())
        instance.delete()
    @action(detail=True, methods=["post"], url_path="test")
    def test(self, request, pk=None):
        channel = self.get_object()
        from .notifications import notification_response_summary, validate_notification_response
        import requests
        payload = {"msg_type": "text", "content": {"text": "测试平台 · 通知渠道测试发送成功"}} if channel.platform == "lark" else {"msgtype": "markdown", "markdown": {"content": "## 测试平台\n> 通知渠道测试发送成功"}}
        try:
            response = requests.post(channel.webhook_url, json=payload, timeout=8)
            sent, validation_error = validate_notification_response(channel.platform, response)
            return Response(
                {
                    "sent": sent,
                    "status_code": response.status_code,
                    "detail": notification_response_summary(response, validation_error),
                },
                status=200 if sent else 400,
            )
        except Exception as exc:
            return Response({"sent": False, "detail": str(exc)}, status=400)


class NotificationRuleViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationRuleSerializer
    queryset = NotificationRule.objects.select_related("channel", "suite")
    def get_queryset(self):
        suite_ids = accessible_suites(self.request.user).values("pk")
        return self.queryset.filter(
            channel__projects__tenant=get_request_tenant(self.request),
        ).filter(
            project_access_q(self.request.user, "channel__projects__")
        ).filter(
            Q(suite__isnull=True) | Q(suite_id__in=suite_ids)
        ).distinct()

    def _require_rule_targets(self, channel, suite=None):
        require_projects_access(self.request.user, channel.projects.all())
        validate_tenant_relations(
            self.request, channel_projects=list(channel.projects.all()), suite=suite,
        )
        if suite:
            require_suite_access(self.request.user, suite)

    def perform_create(self, serializer):
        self._require_rule_targets(
            serializer.validated_data["channel"], serializer.validated_data.get("suite"),
        )
        serializer.save()

    def perform_update(self, serializer):
        instance = self.get_object()
        self._require_rule_targets(instance.channel, instance.suite)
        self._require_rule_targets(
            serializer.validated_data.get("channel", instance.channel),
            serializer.validated_data.get("suite", instance.suite),
        )
        serializer.save()

    def perform_destroy(self, instance):
        self._require_rule_targets(instance.channel, instance.suite)
        instance.delete()


class NotificationDeliveryViewSet(viewsets.mixins.ListModelMixin, viewsets.mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationDeliverySerializer
    queryset = NotificationDelivery.objects.select_related("channel", "result")
    def get_queryset(self):
        # 投递记录同时包含执行报告摘要，必须拥有结果主项目及套件全部内容权限。
        queryset = self.queryset.filter(
            result__tenant=get_request_tenant(self.request),
        ).filter(project_access_q(self.request.user, "result__project__"))
        return filter_suite_access(queryset, self.request.user, "result__suite__")


@api_view()  # DRF的接口
def static_server(request, path, document_root=None, show_indexes=False):
    # 静态日志、截图和压缩包也属于执行结果数据。先按路径定位执行记录，
    # 再用项目权限过滤，避免知道运行目录名称即可读取其他项目报告。
    parts = Path(path).parts
    directory_name = parts[0] if parts else ""
    if not directory_name:
        raise Http404
    matched = filter_suite_access(
        RunResult.objects.filter(
            tenant=get_request_tenant(request),
        ).filter(project_access_q(request.user, "project__")),
        request.user,
        "suite__",
    ).filter(
        Q(path=directory_name) | Q(path__endswith=f"/{directory_name}")
    ).first()
    if matched is None:
        raise Http404
    # 以数据库中的真实运行目录定位，同时兼容新的租户根目录、
    # 第三阶段目录及更早的平铺目录。
    storage_base = Path(document_root).resolve().parent if document_root else Path(settings.BASE_DIR).resolve()
    stored_path = Path(str(matched.path))
    if not stored_path.is_absolute():
        stored_path = storage_base / stored_path
    stored_path = stored_path.resolve()
    if not is_managed_storage_path(stored_path, "upload_yaml", base_dir=storage_base):
        raise Http404
    tail = Path(*parts[1:]) if len(parts) > 1 else Path()
    serve_path = str(stored_path.relative_to(storage_base) / tail)
    resp = serve(request, serve_path, storage_base, show_indexes)

    # 修改响应头
    if resp.status_code == 200:
        if path.endswith(".yaml") or path.endswith(".log"):
            resp.headers["Content-Type"] = "text/css; charset=utf-8"

    return resp


def _step_count_subquery(link_model, case_lookup: str, case_filter: str):
    """构造「某套件下启用用例的步骤总数」的相关子查询。

    对应 model 上的 ui_step_count() / app_step_count() 里那几个 aggregate，
    只是把「每个套件查一次」改成随主查询一次算完。
    """
    return (
        link_model.objects.filter(suite=OuterRef("pk"), **{case_filter: True})
        .values("suite")
        .annotate(total=Count(case_lookup))
        .values("total")
    )


def _ui_step_count_sq():
    return _step_count_subquery(SuiteUiCase, "ui_case__steps", "ui_case__enabled")


def _playwright_step_count_sq():
    return _step_count_subquery(
        SuitePlaywrightCase, "playwright_case__steps", "playwright_case__enabled"
    )


def _app_step_count_sq():
    return _step_count_subquery(SuiteAppCase, "app_case__steps", "app_case__enabled")


def _suite_project_name_prefetches(prefix=""):
    """预取 suite_project_names() 所需的全部关联，可同时复用于套件和执行报告列表。"""
    return (
        Prefetch(
            f"{prefix}suitescenario_set",
            queryset=SuiteScenario.objects.select_related("scenario", "scenario__project")
            .prefetch_related("scenario__projects", "scenario__steps__endpoint__project")
            .order_by("order", "id"),
            to_attr="prefetched_scenario_links",
        ),
        Prefetch(
            f"{prefix}suiteuicase_set",
            queryset=SuiteUiCase.objects.select_related(
                "ui_case", "ui_case__project"
            ).order_by("order", "id"),
            to_attr="prefetched_ui_case_links",
        ),
        Prefetch(
            f"{prefix}suiteplaywrightcase_set",
            queryset=SuitePlaywrightCase.objects.select_related(
                "playwright_case", "playwright_case__project"
            ).order_by("order", "id"),
            to_attr="prefetched_playwright_links",
        ),
        Prefetch(
            f"{prefix}suiteappcase_set",
            queryset=SuiteAppCase.objects.select_related(
                "app_case", "app_case__project", "app_case__application",
                "app_case__default_device",
            ).order_by("order", "id"),
            to_attr="prefetched_app_case_links",
        ),
        Prefetch(
            f"{prefix}execution_items",
            queryset=SuiteExecutionItem.objects.select_related(
                "scenario", "scenario__project",
                "ui_case", "ui_case__project",
                "playwright_case", "playwright_case__project",
                "yaml_case", "yaml_case__project",
                "app_case", "app_case__project", "app_case__application", "app_case__default_device",
            ).order_by("order", "id"),
            to_attr="prefetched_execution_items",
        ),
    )


class SuiteViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    serializer_class = SuiteSerializer
    queryset = Suite.objects.all()

    def get_queryset(self):
        queryset = filter_suite_access(self.tenant_scope(self.queryset), self.request.user)
        project_id = self.request.query_params.get("project")
        if project_id:
            queryset = filter_suite_project(queryset, project_id)
        environment_id = self.request.query_params.get("environment")
        if environment_id:
            try:
                environment_id = int(environment_id)
            except (TypeError, ValueError):
                return queryset.none()
            if environment_id <= 0:
                return queryset.none()
            queryset = queryset.filter(environment_id=environment_id)
        return queryset

    def list(self, request, *args, **kwargs):
        """列表额外返回每个计划最近几次执行结果。

        先分页再取执行记录：只查当前页用到的套件，避免为整表付出代价。
        """
        queryset = self._with_list_prefetch(self.filter_queryset(self.get_queryset()))
        page = self.paginate_queryset(queryset)
        suites = list(page) if page is not None else list(queryset)
        self._recent_runs_cache = self._build_recent_runs(suites)
        serializer = self.get_serializer(suites, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    def _with_list_prefetch(self, queryset):
        """给列表页预取每行都要读的关联，消掉每行约 18 条的重复查询。

        只在 list() 里用：写接口和详情页只有一条记录，预取是白花钱。

        为什么用 to_attr 而不是覆盖默认 related manager：Suite 上的
        ordered_*_links() / ordered_execution_items() 返回的是 queryset，
        调用方（serializers、dispatcher、execution_template）会用
        .values_list() / .filter() / .count()，执行链路依赖这个类型。
        预取结果只挂到独立的 prefetched_* 属性上，序列化器有则用、没有就回落到原查询，
        这样 model 层和执行链路完全不受影响。
        """
        return (
            queryset.select_related(
                "environment",
                "environment__project",
                "schedule",
            )
            .annotate(
                # 步骤数在数据库端算好，每行省掉 3 次聚合查询，又不把步骤行拉进内存。
                # 用 Subquery 而不是 Count(...filter=...)：后者会在主查询上再挂多条多值 join，
                # 多个聚合互相放大行数，很容易算错；子查询之间互不影响。
                annotated_ui_step_count=(
                    Coalesce(Subquery(_ui_step_count_sq(), output_field=IntegerField()), Value(0))
                    + Coalesce(Subquery(_playwright_step_count_sq(), output_field=IntegerField()), Value(0))
                ),
                annotated_app_step_count=Coalesce(
                    Subquery(_app_step_count_sq(), output_field=IntegerField()), Value(0)
                ),
            )
            .prefetch_related(
                *_suite_project_name_prefetches(),
            )
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # 未经过 list() 的场景（详情、新建、编辑）为 None，
        # 序列化器会回退到单对象查询。
        context["recent_runs"] = getattr(self, "_recent_runs_cache", None)
        return context

    def _build_recent_runs(self, suites):
        """一次查询取回这批计划的最近执行记录，按 suite_id 分组。

        用窗口函数在数据库里按套件分区排名后只取前 N 条，
        而不是「每个套件查一次」，列表每页 10~50 条时差别很明显。
        """
        suite_ids = [suite.pk for suite in suites]
        if not suite_ids:
            return {}
        ranked = (
            self.tenant_scope(RunResult.objects.filter(suite_id__in=suite_ids))
            .annotate(
                row_number=Window(
                    expression=RowNumber(),
                    partition_by=[F("suite_id")],
                    order_by=[F("create_datetime").desc(), F("id").desc()],
                )
            )
            .filter(row_number__lte=RECENT_RUN_LIMIT)
            .order_by("suite_id", "-create_datetime", "-id")
            # 原生报告可能很大，列表页用不到，避免把整份报告读进内存。
            .defer("native_report")
        )
        bucket = {}
        for result in ranked:
            bucket.setdefault(result.suite_id, []).append(result)
        return bucket

    def perform_create(self, serializer):
        environment = serializer.validated_data["environment"]
        require_project_access(self.request.user, environment.project)
        serializer.save(
            tenant=validate_tenant_relations(self.request, environment=environment),
            # 创建人只在新建时写入一次。放到 perform_update 里会让「编辑计划」
            # 把创建人改成当前编辑者，那是执行人语义，不是创建人。
            creator_name=_request_actor_name(self.request),
        )

    def perform_update(self, serializer):
        suite = self.get_object()
        require_suite_access(self.request.user, suite)
        environment = serializer.validated_data.get("environment", suite.environment)
        require_project_access(self.request.user, environment.project)
        serializer.save(tenant=validate_tenant_relations(self.request, suite=suite, environment=environment))

    def destroy(self, request, *args, **kwargs):
        """删除操作幂等化：前端列表有短暂缓存时，重复删除不应报 404。"""
        try:
            return super().destroy(request, *args, **kwargs)
        except Http404:
            return Response(status=status.HTTP_204_NO_CONTENT)

    @action(methods=["POST"], detail=True, url_path="sync-scenarios")
    def sync_scenarios(self, request, pk=None):
        suite = self.get_object()
        scenario_ids = request.data.get("scenario_ids", [])
        if not isinstance(scenario_ids, list) or any(
            isinstance(item, bool) or not isinstance(item, int) for item in scenario_ids
        ):
            return Response(
                {"scenario_ids": "场景列表格式不正确。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(scenario_ids) != len(set(scenario_ids)):
            return Response(
                {"scenario_ids": "场景列表不能包含重复项。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        scenarios = Scenario.objects.filter(pk__in=scenario_ids, tenant=suite.tenant).prefetch_related("projects")
        scenario_map = {scenario.pk: scenario for scenario in scenarios}
        missing_ids = [scenario_id for scenario_id in scenario_ids if scenario_id not in scenario_map]
        if missing_ids:
            return Response(
                {"scenario_ids": f"场景不存在：{missing_ids}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for scenario_id in scenario_ids:
            scenario = scenario_map[scenario_id]
            require_project_access(self.request.user, scenario.project)
            for project in scenario.projects.all():
                require_project_access(self.request.user, project)

        suite.sync_scenarios(scenario_ids)
        return Response(self.get_serializer(suite).data)

    @action(methods=["POST"], detail=True, url_path="sync-ui-cases")
    def sync_ui_cases(self, request, pk=None):
        suite = self.get_object()
        ui_case_ids = request.data.get("ui_case_ids", [])
        if not isinstance(ui_case_ids, list) or any(
            isinstance(item, bool) or not isinstance(item, int) for item in ui_case_ids
        ):
            return Response({"ui_case_ids": "UI 用例列表格式不正确。"}, status=status.HTTP_400_BAD_REQUEST)
        if len(ui_case_ids) != len(set(ui_case_ids)):
            return Response({"ui_case_ids": "UI 用例列表不能包含重复项。"}, status=status.HTTP_400_BAD_REQUEST)

        ui_cases = UiCase.objects.filter(pk__in=ui_case_ids, tenant=suite.tenant).select_related("project")
        ui_case_map = {ui_case.pk: ui_case for ui_case in ui_cases}
        missing_ids = [ui_case_id for ui_case_id in ui_case_ids if ui_case_id not in ui_case_map]
        if missing_ids:
            return Response({"ui_case_ids": f"UI 用例不存在：{missing_ids}"}, status=status.HTTP_400_BAD_REQUEST)
        disabled = [ui_case.name for ui_case in ui_cases if not ui_case.enabled]
        if disabled:
            return Response({"ui_case_ids": f"UI 用例未启用：{disabled}"}, status=status.HTTP_400_BAD_REQUEST)
        for ui_case_id in ui_case_ids:
            require_project_access(self.request.user, ui_case_map[ui_case_id].project)

        suite.sync_ui_cases(ui_case_ids)
        return Response(self.get_serializer(suite).data)

    @action(methods=["POST"], detail=True, url_path="sync-execution-items")
    def sync_execution_items(self, request, pk=None):
        """保存接口场景、Web UI 与 App 用例的统一混合执行顺序。"""
        suite = self.get_object()
        items = request.data.get("items", [])
        if not isinstance(items, list):
            return Response({"items": "执行顺序格式不正确。"}, status=status.HTTP_400_BAD_REQUEST)

        normalized = []
        seen = set()
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                return Response({"items": f"第 {index} 项格式不正确。"}, status=status.HTTP_400_BAD_REQUEST)
            item_type = item.get("type")
            item_id = item.get("id")
            if item_type not in {"api", "ui", "playwright_ui", "yaml_ui", "app"} or isinstance(item_id, bool) or not isinstance(item_id, int):
                return Response({"items": f"第 {index} 项类型或 ID 不正确。"}, status=status.HTTP_400_BAD_REQUEST)
            key = (item_type, item_id)
            if key in seen:
                return Response({"items": f"执行顺序中存在重复项：{item_type}#{item_id}"}, status=status.HTTP_400_BAD_REQUEST)
            seen.add(key)
            normalized.append({"type": item_type, "id": item_id})

        scenario_ids = [item["id"] for item in normalized if item["type"] == "api"]
        ui_case_ids = [item["id"] for item in normalized if item["type"] == "ui"]
        playwright_case_ids = [item["id"] for item in normalized if item["type"] == "playwright_ui"]
        yaml_case_ids = [item["id"] for item in normalized if item["type"] == "yaml_ui"]
        app_case_ids = [item["id"] for item in normalized if item["type"] == "app"]
        scenarios = Scenario.objects.filter(pk__in=scenario_ids, tenant=suite.tenant).prefetch_related("projects")
        scenario_map = {scenario.pk: scenario for scenario in scenarios}
        ui_cases = UiCase.objects.filter(pk__in=ui_case_ids, tenant=suite.tenant).select_related("project")
        ui_case_map = {ui_case.pk: ui_case for ui_case in ui_cases}
        playwright_cases = PlaywrightCase.objects.filter(pk__in=playwright_case_ids, tenant=suite.tenant).select_related("project")
        playwright_case_map = {case.pk: case for case in playwright_cases}
        yaml_cases = PlaywrightScenarioFile.objects.filter(pk__in=yaml_case_ids, tenant=suite.tenant).select_related("project")
        yaml_case_map = {case.pk: case for case in yaml_cases}
        app_cases = AppCase.objects.filter(pk__in=app_case_ids, tenant=suite.tenant).select_related("project", "default_device")
        app_case_map = {case.pk: case for case in app_cases}
        missing_scenarios = [item_id for item_id in scenario_ids if item_id not in scenario_map]
        missing_ui_cases = [item_id for item_id in ui_case_ids if item_id not in ui_case_map]
        missing_playwright_cases = [item_id for item_id in playwright_case_ids if item_id not in playwright_case_map]
        missing_yaml_cases = [item_id for item_id in yaml_case_ids if item_id not in yaml_case_map]
        missing_app_cases = [item_id for item_id in app_case_ids if item_id not in app_case_map]
        if missing_scenarios or missing_ui_cases or missing_playwright_cases or missing_yaml_cases or missing_app_cases:
            return Response(
                {"items": f"内容不存在：接口场景 {missing_scenarios}，UI 用例 {missing_ui_cases}，Playwright 用例 {missing_playwright_cases}，YAML 用例 {missing_yaml_cases}，App 用例 {missing_app_cases}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        disabled = [ui_case.name for ui_case in ui_cases if not ui_case.enabled]
        if disabled:
            return Response({"items": f"UI 用例未启用：{disabled}"}, status=status.HTTP_400_BAD_REQUEST)
        for scenario in scenarios:
            require_project_access(self.request.user, scenario.project)
            for project in scenario.projects.all():
                require_project_access(self.request.user, project)
        for ui_case in ui_cases:
            require_project_access(self.request.user, ui_case.project)
        disabled_playwright = [case.name for case in playwright_cases if not case.enabled]
        if disabled_playwright:
            return Response({"items": f"Playwright 用例未启用：{disabled_playwright}"}, status=status.HTTP_400_BAD_REQUEST)
        for case in playwright_cases:
            require_project_access(self.request.user, case.project)
        for case in yaml_cases:
            require_project_access(self.request.user, case.project)
        disabled_app = [case.name for case in app_cases if not case.enabled]
        if disabled_app:
            return Response({"items": f"App 用例未启用：{disabled_app}"}, status=status.HTTP_400_BAD_REQUEST)
        invalid_devices = [case.name for case in app_cases if not case.default_device_id or not case.default_device.enabled]
        if invalid_devices:
            return Response(
                {"items": f"App 用例未配置可用默认设备：{invalid_devices}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for case in app_cases:
            require_project_access(self.request.user, case.project)

        suite.sync_execution_items(normalized)
        return Response(self.get_serializer(suite).data)

    @action(methods=["POST"], detail=True)
    def run(self, request, pk):
        """手动执行测试套件。

        run_type 只描述套件的自动触发方式（定时、Webhook 或纯手动），
        不应限制用户在页面上发起一次手动执行。
        """
        obj: Suite = self.get_object()  # queryset 查询数据

        if not obj.enabled:
            return Response({"detail": "套件已停用，请启用后再执行。"}, status=status.HTTP_409_CONFLICT)
        try:
            result = obj.run(executor_name=_request_actor_name(request))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response({"result_id": result.id})

    @action(methods=["POST"], detail=True, permission_classes=[permissions.AllowAny])
    def webhook(self, request, pk):
        """使用请求头中的 Hook Key、时间戳、Nonce 与 HMAC 签名触发套件。"""
        obj = Suite.objects.select_related("environment").filter(
            pk=pk,
            enabled=True,
            run_type=Suite.RunType.WebHook,
        ).first()
        if obj is None:
            return Response({"detail": "Webhook 验证失败。"}, status=status.HTTP_401_UNAUTHORIZED)

        from .webhook_security import verify_and_consume_webhook_request

        verified, reason = verify_and_consume_webhook_request(request, obj)
        if not verified:
            if reason == "replayed":
                return Response(
                    {"detail": "Webhook 请求已被使用。"}, status=status.HTTP_409_CONFLICT
                )
            return Response({"detail": "Webhook 验证失败。"}, status=status.HTTP_401_UNAUTHORIZED)
        try:
            result = obj.run(executor_name="Webhook")
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response({"result_id": result.id}, status=status.HTTP_202_ACCEPTED)


@extend_schema(tags=["Suite"])
class SuiteScenarioViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    tenant_lookup = "suite__tenant"
    queryset = SuiteScenario.objects.select_related("suite", "scenario").all()
    serializer_class = SuiteScenarioSerializer

    def get_queryset(self):
        return filter_suite_access(self.tenant_scope(self.queryset), self.request.user, "suite__")

    def perform_create(self, serializer):
        require_project_access(self.request.user, serializer.validated_data["suite"].environment.project)
        scenario = serializer.validated_data["scenario"]
        require_project_access(self.request.user, scenario.project)
        require_projects_access(self.request.user, scenario.projects.all())
        serializer.save()

    def perform_update(self, serializer):
        instance = self.get_object()
        require_project_access(self.request.user, instance.suite.environment.project)
        require_project_access(self.request.user, instance.scenario.project)
        require_projects_access(self.request.user, instance.scenario.projects.all())
        suite = serializer.validated_data.get("suite", instance.suite)
        scenario = serializer.validated_data.get("scenario", instance.scenario)
        require_project_access(self.request.user, suite.environment.project)
        require_project_access(self.request.user, scenario.project)
        require_projects_access(self.request.user, scenario.projects.all())
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        """关联同步可能遇到已被移除的旧记录，重复删除按成功处理。"""
        try:
            return super().destroy(request, *args, **kwargs)
        except Http404:
            return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Suite"])
class RunResultViewSet(
    TenantScopedViewSetMixin,
    viewsets.mixins.RetrieveModelMixin,
    viewsets.mixins.ListModelMixin,
    viewsets.mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    # 按实际创建时间倒序，供执行结果页和主控台展示最近执行记录。
    queryset = RunResult.objects.all().order_by("-create_datetime", "-id")
    serializer_class = RunResultSerializer

    def get_queryset(self):
        queryset = self.tenant_scope(self.queryset).filter(
            project_access_q(self.request.user, "project__")
        ).select_related(
            "project", "suite", "suite__environment", "suite__environment__project"
        ).prefetch_related(
            *_suite_project_name_prefetches("suite__")
        )
        queryset = filter_suite_access(queryset, self.request.user, "suite__")
        project_id = self.request.query_params.get("project")
        if project_id:
            queryset = filter_suite_project(queryset, project_id, "suite__")
        environment_name = str(self.request.query_params.get("environment") or "").strip()
        if environment_name:
            queryset = queryset.filter(
                Q(environment_name=environment_name)
                | Q(environment_name="", suite__environment__name=environment_name)
            )
        return queryset

    @action(methods=["POST"], detail=True)
    def retry(self, request, pk=None):
        """重新执行：复用当前记录与执行编号，覆盖本次报告内容。"""
        result = self.get_object()
        suite = result.suite
        try:
            rerun_result = suite.run(
                executor_name=_request_actor_name(request),
                reuse_result=result,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response({"result_id": rerun_result.id, "reused": True})

    @action(methods=["POST"], detail=True)
    def cancel(self, request, pk=None):
        result = self.get_object()
        if result.status in (result.RunStatus.Done, result.RunStatus.Error, result.RunStatus.Canceled):
            return Response({"detail": "该任务已结束，无法取消。"}, status=status.HTTP_400_BAD_REQUEST)
        result.cancel_requested = True
        # 队列中尚未开始的任务可以立即标记取消；工作线程取到任务时会直接跳过。
        if result.status == result.RunStatus.Ready:
            result.status = result.RunStatus.Canceled
            result.finished_at = timezone.now()
            result.save(update_fields=["cancel_requested", "status", "finished_at", "update_datetime"])
        else:
            if result.status == result.RunStatus.Paused and result.run_process_id:
                try:
                    os.kill(result.run_process_id, signal.SIGCONT)
                except OSError:
                    pass
            result.save(update_fields=["cancel_requested", "update_datetime"])
        return Response(self.get_serializer(result).data)

    @action(methods=["POST"], detail=True)
    def pause(self, request, pk=None):
        """暂停正在运行的本机 pytest 子进程。再次调用会恢复执行。"""
        result = self.get_object()
        if result.status == result.RunStatus.Paused:
            if not result.run_process_id:
                return Response({"detail": "执行进程不存在，无法恢复。"}, status=status.HTTP_409_CONFLICT)
            try:
                os.kill(result.run_process_id, signal.SIGCONT)
            except OSError:
                return Response({"detail": "执行进程已结束，无法恢复。"}, status=status.HTTP_409_CONFLICT)
            result.status = result.RunStatus.Running
            result.save(update_fields=["status", "update_datetime"])
            return Response(self.get_serializer(result).data)

        if result.status != result.RunStatus.Running:
            return Response({"detail": "仅运行中的任务可以暂停。"}, status=status.HTTP_400_BAD_REQUEST)
        if not result.run_process_id:
            return Response({"detail": "执行进程尚未就绪，请稍后重试。"}, status=status.HTTP_409_CONFLICT)
        try:
            os.kill(result.run_process_id, signal.SIGSTOP)
        except OSError:
            return Response({"detail": "执行进程已结束，无法暂停。"}, status=status.HTTP_409_CONFLICT)
        result.status = result.RunStatus.Paused
        result.save(update_fields=["status", "update_datetime"])
        return Response(self.get_serializer(result).data)

    @action(methods=["GET"], detail=True)
    def progress(self, request, pk=None):
        # 完整报告可能包含跨项目的用例、请求及提取数据，
        # 必须沿用 get_queryset() 的套件全项目权限校验。
        result = self.get_object()
        path = Path(str(result.path))
        serialized = dict(self.get_serializer(result).data)
        # UI 执行器逐步骤写入运行目录。轮询时合并快照即可实时返回状态，
        # 无需等待 pytest 全部结束，也不在 GET 请求中反写数据库。
        serialized["native_report"] = merge_ui_runtime_results(
            deepcopy(serialized.get("native_report") or {}), path,
        )
        return _no_cache_response({
            "result": serialized,
            "log": _execution_log_text(result),
            "active": _run_is_active(result),
        })

    @action(methods=["GET"], detail=True, url_path="execution-log")
    def execution_log(self, request, pk=None):
        """
        实时日志只校验租户和本次执行所属项目。

        返回值刻意不使用 RunResultSerializer，避免在放开日志权限时
        同时暴露 native_report 中的跨项目报告内容。
        """
        result = self.tenant_scope(self.queryset).filter(
            project_access_q(request.user, "project__"),
            pk=pk,
        ).select_related("suite", "suite__environment").distinct().first()
        if result is None:
            raise Http404

        can_view_report = self.get_queryset().filter(pk=result.pk).exists()
        return _no_cache_response({
            "result": {
                "id": result.id,
                "suite_name": result.suite.name,
                "environment_name": result.environment_name
                or (result.suite.environment.name if result.suite.environment_id else "-"),
                "executor_name": result.executor_name,
                "status": result.get_status_display(),
            },
            "log": _execution_log_text(result),
            "active": _run_is_active(result),
            "can_view_report": can_view_report,
        })
