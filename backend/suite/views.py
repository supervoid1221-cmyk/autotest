import os
import signal

from django.http import Http404
from copy import deepcopy
from pathlib import Path
from django.utils import timezone
from django.views.static import serve
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from django.db.models import Q
from rest_framework.decorators import action, api_view
from rest_framework.response import Response

# rest_framework.permissions.IsAuthenticated
from .models import NotificationChannel, NotificationDelivery, NotificationRule, RunResult, Suite, SuiteScenario
from .serializers import NotificationChannelSerializer, NotificationDeliverySerializer, NotificationRuleSerializer, RunResultSerializer, SuiteScenarioSerializer, SuiteSerializer
from project.access import project_access_q, require_project_access, require_projects_access
from case_api.models import Scenario
from case_ui.models import PlaywrightCase, UiCase
from .reporting import merge_ui_runtime_results
from .access import accessible_suites, filter_suite_access, require_suite_access


def _request_executor_name(request):
    """返回适合写入历史执行记录的当前用户名称快照。"""
    user = request.user
    if not user or not user.is_authenticated:
        return "系统"
    return user.get_full_name().strip() or user.get_username() or "系统"


class NotificationChannelViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationChannelSerializer
    queryset = NotificationChannel.objects.prefetch_related("projects")
    def get_queryset(self): return self.queryset.filter(project_access_q(self.request.user, "projects__")).distinct()
    def perform_create(self, serializer):
        require_projects_access(self.request.user, serializer.validated_data["projects"])
        serializer.save()
    def perform_update(self, serializer):
        require_projects_access(self.request.user, serializer.instance.projects.all())
        require_projects_access(
            self.request.user,
            serializer.validated_data.get("projects", serializer.instance.projects.all()),
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
            project_access_q(self.request.user, "channel__projects__")
        ).filter(
            Q(suite__isnull=True) | Q(suite_id__in=suite_ids)
        ).distinct()

    def _require_rule_targets(self, channel, suite=None):
        require_projects_access(self.request.user, channel.projects.all())
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
        queryset = self.queryset.filter(project_access_q(self.request.user, "result__project__"))
        return filter_suite_access(queryset, self.request.user, "result__suite__")


@api_view()  # DRF的接口
def static_server(request, path, document_root=None, show_indexes=False):
    # 静态日志、截图和压缩包也属于执行结果数据。先按路径定位执行记录，
    # 再用项目权限过滤，避免知道运行目录名称即可读取其他项目报告。
    directory_name = Path(path).parts[0] if Path(path).parts else ""
    if not directory_name:
        raise Http404
    accessible_result = filter_suite_access(
        RunResult.objects.filter(project_access_q(request.user, "project__")),
        request.user,
        "suite__",
    ).filter(
        Q(path=directory_name) | Q(path__endswith=f"/{directory_name}")
    )
    if not accessible_result.exists():
        raise Http404
    resp = serve(request, path, document_root, show_indexes)

    # 修改响应头
    if resp.status_code == 200:
        if path.endswith(".yaml") or path.endswith(".log"):
            resp.headers["Content-Type"] = "text/css; charset=utf-8"

    return resp


@extend_schema(tags=["Suite"])
class SuiteViewSet(viewsets.ModelViewSet):
    serializer_class = SuiteSerializer
    queryset = Suite.objects.all()

    def get_queryset(self):
        return filter_suite_access(self.queryset, self.request.user)

    def perform_create(self, serializer):
        require_project_access(self.request.user, serializer.validated_data["environment"].project)
        serializer.save()

    def perform_update(self, serializer):
        suite = self.get_object()
        require_suite_access(self.request.user, suite)
        environment = serializer.validated_data.get("environment", suite.environment)
        require_project_access(self.request.user, environment.project)
        serializer.save()

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

        scenarios = Scenario.objects.filter(pk__in=scenario_ids).prefetch_related("projects")
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

        ui_cases = UiCase.objects.filter(pk__in=ui_case_ids).select_related("project")
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
        """保存接口场景与 UI 用例的统一混合执行顺序。"""
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
            if item_type not in {"api", "ui", "playwright_ui"} or isinstance(item_id, bool) or not isinstance(item_id, int):
                return Response({"items": f"第 {index} 项类型或 ID 不正确。"}, status=status.HTTP_400_BAD_REQUEST)
            key = (item_type, item_id)
            if key in seen:
                return Response({"items": f"执行顺序中存在重复项：{item_type}#{item_id}"}, status=status.HTTP_400_BAD_REQUEST)
            seen.add(key)
            normalized.append({"type": item_type, "id": item_id})

        scenario_ids = [item["id"] for item in normalized if item["type"] == "api"]
        ui_case_ids = [item["id"] for item in normalized if item["type"] == "ui"]
        playwright_case_ids = [item["id"] for item in normalized if item["type"] == "playwright_ui"]
        scenarios = Scenario.objects.filter(pk__in=scenario_ids).prefetch_related("projects")
        scenario_map = {scenario.pk: scenario for scenario in scenarios}
        ui_cases = UiCase.objects.filter(pk__in=ui_case_ids).select_related("project")
        ui_case_map = {ui_case.pk: ui_case for ui_case in ui_cases}
        playwright_cases = PlaywrightCase.objects.filter(pk__in=playwright_case_ids).select_related("project")
        playwright_case_map = {case.pk: case for case in playwright_cases}
        missing_scenarios = [item_id for item_id in scenario_ids if item_id not in scenario_map]
        missing_ui_cases = [item_id for item_id in ui_case_ids if item_id not in ui_case_map]
        missing_playwright_cases = [item_id for item_id in playwright_case_ids if item_id not in playwright_case_map]
        if missing_scenarios or missing_ui_cases or missing_playwright_cases:
            return Response(
                {"items": f"内容不存在：接口场景 {missing_scenarios}，UI 用例 {missing_ui_cases}，Playwright 用例 {missing_playwright_cases}"},
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

        suite.sync_execution_items(normalized)
        return Response(self.get_serializer(suite).data)

    @action(methods=["POST"], detail=True)
    def run(self, request, pk):
        """执行测试套件"""
        obj: Suite = self.get_object()  # queryset 查询数据

        if not obj.enabled:
            return Response({"detail": "套件已停用，请启用后再执行。"}, status=status.HTTP_409_CONFLICT)
        if obj.run_type == obj.RunType.ONCE:
            try:
                result = obj.run(executor_name=_request_executor_name(request))
            except ValueError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
            return Response({"result_id": result.id})
        else:
            return Response({"detail": f"本套件不允许手动触发，运行类型= {obj.run_type}"}, status=400)

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
class SuiteScenarioViewSet(viewsets.ModelViewSet):
    queryset = SuiteScenario.objects.select_related("suite", "scenario").all()
    serializer_class = SuiteScenarioSerializer

    def get_queryset(self):
        return filter_suite_access(self.queryset, self.request.user, "suite__")

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
    viewsets.mixins.RetrieveModelMixin,
    viewsets.mixins.ListModelMixin,
    viewsets.mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    # 按实际创建时间倒序，供执行结果页和主控台展示最近执行记录。
    queryset = RunResult.objects.all().order_by("-create_datetime", "-id")
    serializer_class = RunResultSerializer

    def get_queryset(self):
        queryset = self.queryset.filter(project_access_q(self.request.user, "project__"))
        return filter_suite_access(queryset, self.request.user, "suite__")

    @action(methods=["POST"], detail=True)
    def retry(self, request, pk=None):
        """重新执行：复用当前记录与执行编号，覆盖本次报告内容。"""
        result = self.get_object()
        suite = result.suite
        if suite.run_type != suite.RunType.ONCE:
            return Response({"detail": "本套件不允许手动触发。"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            rerun_result = suite.run(
                executor_name=_request_executor_name(request),
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
        result = self.get_object()
        path = Path(str(result.path))
        serialized = dict(self.get_serializer(result).data)
        # UI 执行器逐步骤写入运行目录。轮询时合并快照即可实时返回状态，
        # 无需等待 pytest 全部结束，也不在 GET 请求中反写数据库。
        serialized["native_report"] = merge_ui_runtime_results(
            deepcopy(serialized.get("native_report") or {}), path,
        )
        chunks = []
        for filename in ("logs/runner.log", "logs/pytest.log"):
            log_path = path / filename
            if log_path.exists():
                try:
                    chunks.append(log_path.read_text(encoding="utf-8", errors="replace")[-12000:])
                except OSError:
                    pass
        return Response({
            "result": serialized,
            "log": "\n".join(chunks),
            "active": result.status in (result.RunStatus.Ready, result.RunStatus.Running, result.RunStatus.Reporting, result.RunStatus.Paused),
        })
