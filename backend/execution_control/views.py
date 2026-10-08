from django.db.models import Case, Count, F, IntegerField, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Coalesce
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from account.access import is_system_admin
from account.permissions import IsPlatformAdmin
from account.tenancy import TenantScopedViewSetMixin
from project.access import project_access_q, require_project_access

from .models import ExecutionTask, ExecutionWorker
from .serializers import ExecutionTaskSerializer, ExecutionWorkerSerializer
from .services import delete_task, dependency_overview, diagnose_tasks, recover_task, refresh_worker_states, stop_task
from .sync import sync_all_existing


def _with_queue_positions(queryset):
    """在一条 SQL 中计算排队位置，避免序列化每个任务时各查一次 COUNT。"""
    shared_types = [ExecutionTask.SourceType.SUITE, ExecutionTask.SourceType.APP]
    queue_group = Case(
        When(source_type__in=shared_types, then=Value("regular")),
        default=F("source_type"),
    )
    earlier_tasks = (
        ExecutionTask.objects.filter(
            tenant_id=OuterRef("tenant_id"),
            status=ExecutionTask.Status.QUEUED,
        )
        .annotate(_candidate_queue_group=queue_group)
        .filter(_candidate_queue_group=OuterRef("_queue_group"))
        .filter(
            Q(queued_at__lt=OuterRef("queued_at"))
            | Q(queued_at=OuterRef("queued_at"), id__lte=OuterRef("id"))
        )
        .values("tenant_id")
        .annotate(total=Count("id"))
        .values("total")[:1]
    )
    return queryset.annotate(
        _queue_group=queue_group,
        queue_position=Case(
            When(
                status=ExecutionTask.Status.QUEUED,
                then=Subquery(earlier_tasks, output_field=IntegerField()),
            ),
            default=Value(None),
            output_field=IntegerField(),
        ),
    )


class ExecutionTaskViewSet(
    TenantScopedViewSetMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    queryset = ExecutionTask.objects.select_related("project")
    serializer_class = ExecutionTaskSerializer

    def get_queryset(self):
        queryset = self.tenant_scope(self.queryset).filter(project_access_q(self.request.user, "project__")).distinct()
        for key in ("project", "source_type", "status"):
            value = self.request.query_params.get(key)
            if value:
                queryset = queryset.filter(**{f"{key}_id" if key == "project" else key: value})
        keyword = str(self.request.query_params.get("keyword") or "").strip()
        if keyword:
            queryset = queryset.filter(Q(name__icontains=keyword) | Q(execution_no__icontains=keyword))
        # 与列表中展示的“开始时间”口径一致：已启动任务使用实际开始时间，
        # 尚在排队的任务使用入队时间，并以 ID 保证相同时间下排序稳定。
        if self.action in {"list", "retrieve"}:
            queryset = _with_queue_positions(queryset)
        return queryset.order_by(Coalesce("started_at", "queued_at").desc(), "-id")

    def perform_destroy(self, instance):
        require_project_access(self.request.user, instance.project)
        try:
            delete_task(instance)
        except ValueError as exc:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(str(exc)) from exc

    @action(detail=True, methods=["post"])
    def stop(self, request, pk=None):
        task = self.get_object()
        require_project_access(request.user, task.project)
        try:
            stop_task(task)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        task.refresh_from_db()
        return Response(self.get_serializer(task).data)

    @action(detail=True, methods=["post"])
    def recover(self, request, pk=None):
        task = self.get_object()
        require_project_access(request.user, task.project)
        try:
            recover_task(task)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        task.refresh_from_db()
        return Response(self.get_serializer(task).data)

    @action(detail=False, methods=["get"])
    def overview(self, request):
        queryset = self.get_queryset()
        diagnose_tasks(queryset)
        active_statuses = ["queued", "preparing", "running", "paused", "reporting"]
        counts = {item["status"]: item["total"] for item in queryset.values("status").annotate(total=Count("id"))}
        services = dependency_overview(
            tenant=self.current_tenant(),
            user=request.user,
        )
        abnormal_tasks = queryset.filter(status__in=active_statuses).exclude(diagnostic_code="").count()
        abnormal_services = sum(
            1 for service in services
            if service.get("status") in {"offline", "degraded"}
        )
        return Response({
            "total": queryset.count(),
            "active": queryset.filter(status__in=active_statuses).count(),
            # 需要处理 = 当前服务异常 + 活动任务诊断异常。
            # 历史执行失败仅保留在列表和报告中，不重复计入。
            "abnormal": abnormal_tasks + abnormal_services,
            "abnormal_tasks": abnormal_tasks,
            "abnormal_services": abnormal_services,
            "status_counts": counts,
            "services": services,
        })

    @action(detail=False, methods=["post"])
    def reconcile(self, request):
        if not is_system_admin(request.user):
            raise PermissionDenied("仅系统管理员可执行全局对账。")
        counts = sync_all_existing()
        diagnostics = diagnose_tasks()
        return Response({"synced": counts, "diagnostics": diagnostics})


class ExecutionWorkerViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = ExecutionWorker.objects.all()
    serializer_class = ExecutionWorkerSerializer
    permission_classes = [IsPlatformAdmin]

    def list(self, request, *args, **kwargs):
        refresh_worker_states()
        return super().list(request, *args, **kwargs)
