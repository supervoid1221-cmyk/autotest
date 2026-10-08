import csv
import io
import json
import os
import shutil
import signal
from pathlib import Path

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import FileResponse, HttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from account.access import is_system_admin
from account.tenancy import TenantScopedViewSetMixin, get_request_tenant, validate_tenant_relations
from account.tenant_runtime import ensure_tenant_storage_capacity, is_managed_storage_path
from project.models import Project
from project.access import project_access_q, require_project_access
from .models import PerformanceRun, PerformanceScenario
from .serializers import PerformanceRunSerializer, PerformanceScenarioSerializer


class PerformanceScenarioViewSet(TenantScopedViewSetMixin, viewsets.ModelViewSet):
    queryset = PerformanceScenario.objects.select_related(
        "project", "environment", "source_endpoint", "source_scenario", "monitor_target", "created_by"
    ).prefetch_related("notification_channels")
    serializer_class = PerformanceScenarioSerializer

    def get_queryset(self):
        queryset = self.tenant_scope(self.queryset)
        if not is_system_admin(self.request.user):
            queryset = queryset.filter(project_access_q(self.request.user, "project__")).distinct()
        project = self.request.query_params.get("project")
        name = self.request.query_params.get("name")
        if project:
            queryset = queryset.filter(project_id=project)
        if name:
            queryset = queryset.filter(name__icontains=name)
        return queryset

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        require_project_access(self.request.user, project)
        serializer.save(tenant=validate_tenant_relations(self.request, project=project), created_by=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        require_project_access(self.request.user, instance.project)
        require_project_access(self.request.user, serializer.validated_data.get("project", instance.project))
        project = serializer.validated_data.get("project", instance.project)
        serializer.save(tenant=validate_tenant_relations(self.request, scenario=instance, project=project))

    def perform_destroy(self, instance):
        require_project_access(self.request.user, instance.project)
        if instance.runs.filter(status__in=[PerformanceRun.Status.QUEUED, PerformanceRun.Status.PREPARING, PerformanceRun.Status.RUNNING, PerformanceRun.Status.REPORTING]).exists():
            raise PermissionDenied("场景存在运行中的性能任务，暂时不能删除。")
        instance.delete()

    @action(detail=True, methods=["post"], url_path="refresh-snapshot")
    def refresh_snapshot(self, request, pk=None):
        instance = self.get_object()
        require_project_access(request.user, instance.project)
        serializer = self.get_serializer(instance)
        instance.scenario_snapshot = serializer._build_snapshot({}, instance)
        instance.save(update_fields=["scenario_snapshot", "updated_at"])
        return Response(self.get_serializer(instance).data)

    @action(detail=False, methods=["post"], url_path="parse-parameters", parser_classes=[MultiPartParser, FormParser])
    def parse_parameters(self, request):
        project = get_object_or_404(
            Project, pk=request.data.get("project"), tenant=get_request_tenant(request),
        )
        require_project_access(request.user, project)
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "请选择 CSV 或 JSON 文件。"}, status=status.HTTP_400_BAD_REQUEST)
        if upload.size > 5 * 1024 * 1024:
            return Response({"detail": "参数文件不能超过 5MB。"}, status=status.HTTP_400_BAD_REQUEST)
        suffix = Path(upload.name).suffix.lower()
        try:
            content = upload.read().decode("utf-8-sig")
            if suffix == ".csv":
                rows = list(csv.DictReader(io.StringIO(content)))
                file_format = "csv"
            elif suffix == ".json":
                payload = json.loads(content)
                rows = payload.get("data") if isinstance(payload, dict) else payload
                file_format = "json"
            else:
                raise ValueError("只支持 CSV 和 JSON 文件。")
            if not isinstance(rows, list) or not rows or any(not isinstance(row, dict) for row in rows):
                raise ValueError("参数文件必须至少包含一行对象数据。")
            if len(rows) > 10000:
                raise ValueError("参数文件最多支持 10000 行。")
            columns = list(dict.fromkeys(str(key) for row in rows for key in row.keys()))
            normalized = [{column: row.get(column) for column in columns} for row in rows]
        except (UnicodeDecodeError, csv.Error, json.JSONDecodeError, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"filename": upload.name, "format": file_format, "columns": columns, "row_count": len(normalized), "rows": normalized})

    @action(detail=True, methods=["post"], url_path="run")
    def run(self, request, pk=None):
        scenario = self.get_object()
        require_project_access(request.user, scenario.project)
        if not scenario.enabled:
            return Response({"detail": "性能场景已停用。"}, status=status.HTTP_400_BAD_REQUEST)
        if str(scenario.environment.name).lower() == "prod" and not request.data.get("confirm_production"):
            return Response({"detail": "生产环境性能测试必须明确确认后执行。", "confirmation_required": True}, status=status.HTTP_400_BAD_REQUEST)
        if not (scenario.scenario_snapshot.get("steps") or scenario.scenario_snapshot.get("groups")):
            return Response({"detail": "性能场景没有可执行的接口步骤。"}, status=status.HTTP_400_BAD_REQUEST)
        if scenario.load_mode == PerformanceScenario.LoadMode.THREAD_GROUP:
            configured_vus = scenario.thread_count
        else:
            configured_vus = max(
                (float(stage.get("target", 0)) for stage in scenario.stages if isinstance(stage, dict)),
                default=0,
            )
        snapshot = scenario.scenario_snapshot or {}
        groups = snapshot.get("groups") or [{
            "key": f"{snapshot.get('source_type', 'scenario')}-{snapshot.get('source_id', scenario.id)}",
            "name": snapshot.get("source_name") or scenario.name,
            "weight": 100,
            "steps": snapshot.get("steps", []),
        }]
        execution_config = {
            "load_mode": scenario.load_mode,
            "thresholds": scenario.thresholds,
            "groups": groups,
            "parameter_data": scenario.parameter_data,
            "parameter_strategy": scenario.parameter_strategy,
            "base_url": scenario.environment.base_url.rstrip("/"),
        }
        if scenario.load_mode == PerformanceScenario.LoadMode.THREAD_GROUP:
            execution_config.update({
                "thread_count": scenario.thread_count,
                "duration_seconds": scenario.duration_seconds,
                "ramp_up_seconds": scenario.ramp_up_seconds,
                "graceful_stop_seconds": scenario.graceful_stop_seconds,
            })
        else:
            execution_config["stages"] = scenario.stages
        try:
            ensure_tenant_storage_capacity(scenario.tenant)
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        run = PerformanceRun.objects.create(
            tenant=scenario.tenant, scenario=scenario, project=scenario.project, environment=scenario.environment,
            monitor_target=scenario.monitor_target, configured_vus=configured_vus,
            execution_config=execution_config, created_by=request.user,
        )
        return Response(PerformanceRunSerializer(run).data, status=status.HTTP_201_CREATED)


class PerformanceRunViewSet(TenantScopedViewSetMixin, mixins.DestroyModelMixin, viewsets.ReadOnlyModelViewSet):
    queryset = PerformanceRun.objects.select_related(
        "scenario", "project", "environment", "monitor_target", "created_by"
    ).prefetch_related("metric_buckets", "endpoint_metrics", "notification_deliveries__channel")
    serializer_class = PerformanceRunSerializer

    def get_queryset(self):
        queryset = self.tenant_scope(self.queryset)
        if not is_system_admin(self.request.user):
            queryset = queryset.filter(project_access_q(self.request.user, "project__")).distinct()
        for key in ("project", "environment", "status", "scenario"):
            value = self.request.query_params.get(key)
            if value:
                queryset = queryset.filter(**{f"{key}_id" if key != "status" else key: value})
        environment_name = str(self.request.query_params.get("environment_name") or "").strip()
        if environment_name:
            queryset = queryset.filter(environment__name__iexact=environment_name)
        return queryset

    def perform_destroy(self, instance):
        require_project_access(self.request.user, instance.project)
        active_statuses = {
            PerformanceRun.Status.QUEUED,
            PerformanceRun.Status.PREPARING,
            PerformanceRun.Status.RUNNING,
            PerformanceRun.Status.REPORTING,
        }
        if instance.status in active_statuses:
            raise ValidationError("执行中的性能任务不能删除，请先停止任务。")

        work_dir = Path(instance.work_dir).resolve() if instance.work_dir else None
        tenant_id = instance.tenant_id
        instance.delete()
        if work_dir and is_managed_storage_path(
            work_dir, "performance_runs", tenant=tenant_id
        ):
            shutil.rmtree(work_dir, ignore_errors=True)

    @action(detail=False, methods=["get"], url_path="compare")
    def compare(self, request):
        raw_ids = str(request.query_params.get("ids") or "")
        try:
            ids = list(dict.fromkeys(int(value) for value in raw_ids.split(",") if value.strip()))
        except ValueError:
            return Response({"detail": "报告编号格式不正确。"}, status=status.HTTP_400_BAD_REQUEST)
        if not 2 <= len(ids) <= 5:
            return Response({"detail": "请选择 2 至 5 份报告进行对比。"}, status=status.HTTP_400_BAD_REQUEST)
        runs = list(self.get_queryset().filter(id__in=ids))
        if len(runs) != len(ids):
            return Response({"detail": "部分报告不存在或无权访问。"}, status=status.HTTP_404_NOT_FOUND)
        if len({run.project_id for run in runs}) != 1:
            return Response({"detail": "只能对比同一项目的性能报告。"}, status=status.HTTP_400_BAD_REQUEST)
        ordered = sorted(runs, key=lambda run: ids.index(run.id))
        return Response(self.get_serializer(ordered, many=True).data)

    @action(detail=True, methods=["post"], url_path="stop")
    def stop(self, request, pk=None):
        run = self.get_object()
        require_project_access(request.user, run.project)
        if run.status not in {PerformanceRun.Status.QUEUED, PerformanceRun.Status.PREPARING, PerformanceRun.Status.RUNNING}:
            return Response({"detail": "当前任务状态不能停止。"}, status=status.HTTP_400_BAD_REQUEST)
        run.stop_requested = True
        update_fields = ["stop_requested", "updated_at"]
        if run.status == PerformanceRun.Status.QUEUED:
            run.status = PerformanceRun.Status.STOPPED
            run.finished_at = timezone.now()
            update_fields.extend(["status", "finished_at"])
        run.save(update_fields=update_fields)
        if run.process_id:
            try:
                os.kill(run.process_id, signal.SIGTERM)
            except OSError:
                pass
        return Response({"detail": "已发送停止指令。"})

    @action(detail=True, methods=["get"], url_path="log")
    def log(self, request, pk=None):
        run = self.get_object()
        path = Path(run.work_dir) / "runner.log" if run.work_dir else None
        content = path.read_text(encoding="utf-8", errors="replace")[-100000:] if path and path.exists() else ""
        return Response({"content": content})

    @action(detail=True, methods=["get"], url_path="artifacts")
    def artifacts(self, request, pk=None):
        run = self.get_object()
        path = Path(run.work_dir) / "summary.json" if run.work_dir else None
        if not path or not path.exists():
            return Response({"detail": "报告文件尚未生成。"}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(path.open("rb"), as_attachment=True, filename=f"performance-{run.execution_no}.json")

    @action(detail=True, methods=["get"], url_path="aggregate-csv")
    def aggregate_csv(self, request, pk=None):
        run = self.get_object()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["接口名称", "方法", "样本数", "平均值(ms)", "中位数(ms)", "P90(ms)", "P95(ms)", "P99(ms)", "最小值(ms)", "最大值(ms)", "错误率(%)", "吞吐量(req/s)", "配置比例(%)", "接收KB/s", "发送KB/s"])
        metrics = list(run.endpoint_metrics.all())
        for item in metrics:
            elapsed = item.request_count / item.throughput if item.throughput else 0
            writer.writerow([
                re.sub(r"^\[[^\]]+\]\s*", "", item.endpoint_name), item.method, item.request_count, item.duration_avg,
                item.duration_median, item.duration_p90, item.duration_p95, item.duration_p99,
                item.duration_min, item.duration_max, item.error_rate, item.throughput, item.configured_ratio,
                item.received_bytes / 1024 / elapsed if elapsed else 0,
                item.sent_bytes / 1024 / elapsed if elapsed else 0,
            ])
        if metrics:
            total_requests = sum(item.request_count for item in metrics)
            total_failed = sum(item.failed_count for item in metrics)
            elapsed = max(((item.request_count / item.throughput) for item in metrics if item.throughput), default=0)
            summary = run.summary or {}
            metric = (summary.get("metrics") or {}).get("http_req_duration") or {}
            values = metric.get("values") or metric
            http_reqs = (summary.get("metrics") or {}).get("http_reqs") or {}
            http_values = http_reqs.get("values") or http_reqs
            aggregate = summary.get("aggregate") or {}
            total_p99 = aggregate.get("duration_p99") or values.get("p(99)") or max((item.duration_p99 for item in metrics), default=0)
            writer.writerow([
                "合计", "-", total_requests, values.get("avg", 0), values.get("med", 0),
                values.get("p(90)", 0), values.get("p(95)", 0), total_p99,
                values.get("min", 0), values.get("max", 0), total_failed / total_requests * 100 if total_requests else 0,
                http_values.get("rate", 0), 100,
                sum(item.received_bytes for item in metrics) / 1024 / elapsed if elapsed else 0,
                sum(item.sent_bytes for item in metrics) / 1024 / elapsed if elapsed else 0,
            ])
        response = HttpResponse("\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="performance-{run.execution_no}-aggregate.csv"'
        return response
