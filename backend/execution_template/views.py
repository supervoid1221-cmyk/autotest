import json

import jsonpath
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from account.access import is_system_admin
from project.access import project_access_q, require_project_access
from project.models import Environment
from suite.models import RunResult
from suite.access import accessible_suites, filter_suite_access, require_suite_access

from .models import ExecutionTemplate
from .serializers import ExecutionTemplateSerializer


@extend_schema(tags=["ExecutionTemplate"])
class ExecutionTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = ExecutionTemplateSerializer
    permission_classes = [IsAuthenticated]
    queryset = ExecutionTemplate.objects.select_related("suite", "suite__environment", "project").all()

    def is_admin(self):
        return is_system_admin(self.request.user)

    def require_admin(self):
        if not self.is_admin():
            raise PermissionDenied("仅管理员可以编辑模板。")

    def get_queryset(self):
        queryset = self.queryset.filter(
            project_access_q(self.request.user, "project__"),
            suite_id__in=accessible_suites(self.request.user).values("pk"),
        ).distinct()
        return queryset if self.is_admin() else queryset.filter(enabled=True)

    def perform_create(self, serializer):
        self.require_admin()
        suite = serializer.validated_data["suite"]
        require_suite_access(self.request.user, suite)
        serializer.save(project=suite.environment.project)

    def perform_update(self, serializer):
        self.require_admin()
        suite = serializer.validated_data.get("suite", self.get_object().suite)
        require_suite_access(self.request.user, suite)
        serializer.save(project=suite.environment.project)

    def perform_destroy(self, instance):
        self.require_admin()
        instance.delete()

    @action(methods=["GET"], detail=True)
    def output(self, request, pk=None):
        """从本次运行的原生报告中按模板配置提取输出字段。"""
        template = self.get_object()
        result_id = request.query_params.get("result_id")
        try:
            result = filter_suite_access(
                RunResult.objects.filter(
                    project_access_q(request.user, "project__"),
                    pk=result_id,
                    suite_id=template.suite_id,
                ),
                request.user,
                "suite__",
            ).get()
        except (RunResult.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "执行记录不存在或不属于当前模板。"}, status=status.HTTP_404_NOT_FOUND)

        step_map = {}
        for scenario in (result.native_report or {}).get("scenarios", []):
            for step in scenario.get("steps", []):
                if step.get("source_step_id") is not None:
                    step_map[str(step["source_step_id"])] = step

        fields = []
        for config in sorted(template.output_fields or [], key=lambda item: item.get("sort", 0)):
            step = step_map.get(str(config.get("source_step_id")))
            value, error = None, None
            if not step:
                error = "来源接口尚未执行或历史执行记录不支持输出字段。"
            else:
                body = ((step.get("response") or {}).get("body"))
                try:
                    payload = json.loads(body) if isinstance(body, str) else body
                    values = jsonpath.jsonpath(payload, config.get("json_path", "")) or []
                    if not values:
                        error = "提取路径未匹配到结果。"
                    else:
                        value = values if len(values) > 1 else values[0]
                except (TypeError, ValueError, json.JSONDecodeError) as exc:
                    error = f"响应不是可解析 JSON：{exc}"
            fields.append({
                "key": config.get("key"), "label": config.get("label"),
                "display_type": config.get("display_type", "text"),
                "value": value, "error": error,
                "source_step_id": config.get("source_step_id"), "json_path": config.get("json_path"),
            })
        return Response({
            "result_id": result.id,
            "status": result.get_status_display(),
            "active": result.status in (result.RunStatus.Ready, result.RunStatus.Running, result.RunStatus.Reporting),
            "fields": fields,
        })

    @action(methods=["POST"], detail=True)
    def run(self, request, pk=None):
        """按模板执行套件：校验参数并注入初始变量，可选覆盖执行环境。"""
        template: ExecutionTemplate = self.get_object()
        if not template.enabled:
            return Response({"detail": "该模板已停用，无法执行。"}, status=status.HTTP_400_BAD_REQUEST)

        params = request.data.get("params") or {}
        if not isinstance(params, dict):
            return Response({"detail": "params 必须为对象。"}, status=status.HTTP_400_BAD_REQUEST)

        # 必填校验
        errors = {}
        for param in template.parameters or []:
            key = param.get("key")
            if param.get("required") and not str(params.get(key, "")).strip():
                errors[key] = f"「{param.get('label') or key}」为必填项"
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)

        # 环境选择：仅允许套件环境所在项目的环境，保证各接口能按环境名匹配。
        environment = None
        environment_id = request.data.get("environment_id")
        if environment_id:
            environment = Environment.objects.filter(
                pk=environment_id, project_id=template.suite.environment.project_id
            ).first()
            if environment is None:
                return Response({"environment_id": "所选环境无效或不属于套件所在项目。"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            executor_name = request.user.get_full_name().strip() or request.user.get_username() or "系统"
            result = template.suite.run(
                initial_variables=params,
                environment=environment,
                executor_name=executor_name,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response({"result_id": result.id})
