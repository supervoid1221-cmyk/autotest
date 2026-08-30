from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from account.access import is_system_admin
from project.access import project_access_q, require_project_manager
from .models import MonitorAlertEvent, MonitorCheckSettings, MonitorCluster, MonitorNotificationDelivery, MonitorNotificationRule, MonitorTarget, PrometheusInstance, ServiceMonitor, ServiceMonitorEvent
from .serializers import MonitorAlertEventSerializer, MonitorCheckSettingsSerializer, MonitorClusterSerializer, MonitorNotificationDeliverySerializer, MonitorNotificationRuleSerializer, MonitorTargetSerializer, PrometheusInstanceSerializer, ServiceMonitorEventSerializer, ServiceMonitorSerializer
from .services import PrometheusRequestError, evaluate_alerts, record_service_status, service_snapshot, snapshot, sync_cluster, test_instance


class MonitorClusterViewSet(viewsets.ModelViewSet):
    queryset = MonitorCluster.objects.select_related("project", "prometheus", "server").all(); serializer_class = MonitorClusterSerializer
    def get_queryset(self):
        queryset = self.queryset.all()
        if not is_system_admin(self.request.user): queryset = queryset.filter(project__pm=self.request.user)
        project = self.request.query_params.get("project")
        return queryset.filter(project_id=project) if project else queryset
    def perform_create(self, serializer): require_project_manager(self.request.user, serializer.validated_data["project"]); serializer.save(created_by=self.request.user)
    def perform_update(self, serializer):
        cluster = self.get_object(); require_project_manager(self.request.user, cluster.project); require_project_manager(self.request.user, serializer.validated_data.get("project", cluster.project)); serializer.save()
    def perform_destroy(self, instance): require_project_manager(self.request.user, instance.project); instance.delete()
    @action(detail=True, methods=["post"], url_path="sync")
    def sync(self, request, pk=None):
        cluster = self.get_object()
        require_project_manager(request.user, cluster.project)
        try: return Response(sync_cluster(cluster))
        except PrometheusRequestError as exc: return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class PrometheusInstanceViewSet(viewsets.ModelViewSet):
    queryset = PrometheusInstance.objects.select_related("project").all()
    serializer_class = PrometheusInstanceSerializer

    def get_queryset(self):
        queryset = self.queryset.all()
        if not is_system_admin(self.request.user):
            queryset = queryset.filter(project__pm=self.request.user)
        project = self.request.query_params.get("project")
        if project:
            queryset = queryset.filter(project_id=project)
        return queryset

    def perform_create(self, serializer):
        require_project_manager(self.request.user, serializer.validated_data["project"])
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        require_project_manager(self.request.user, instance.project)
        require_project_manager(self.request.user, serializer.validated_data.get("project", instance.project))
        serializer.save()

    def perform_destroy(self, instance):
        require_project_manager(self.request.user, instance.project)
        instance.delete()

    @action(detail=True, methods=["post"], url_path="test")
    def test(self, request, pk=None):
        instance = self.get_object()
        require_project_manager(request.user, instance.project)
        try:
            test_instance(instance)
        except PrometheusRequestError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"connected": True})


class MonitorTargetViewSet(viewsets.ModelViewSet):
    queryset = MonitorTarget.objects.select_related("prometheus", "project", "server", "cluster").all()
    serializer_class = MonitorTargetSerializer

    def get_queryset(self):
        # 不能直接返回类属性 QuerySet。列表被求值后会保留结果缓存，后续更新
        # 会出现详情已更新、列表仍返回旧项目的情况。
        queryset = self.queryset.all()
        if not is_system_admin(self.request.user):
            queryset = queryset.filter(project_access_q(self.request.user, "project__")).distinct()
        project = self.request.query_params.get("project")
        if project:
            queryset = queryset.filter(project_id=project)
        return queryset

    def perform_create(self, serializer):
        require_project_manager(self.request.user, serializer.validated_data["project"])
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        target = self.get_object()
        require_project_manager(self.request.user, target.project)
        require_project_manager(self.request.user, serializer.validated_data.get("project", target.project))
        serializer.save()

    def perform_destroy(self, instance):
        require_project_manager(self.request.user, instance.project)
        instance.delete()

    @action(detail=True, methods=["get"], url_path="metrics")
    def metrics(self, request, pk=None):
        target = self.get_object()
        try:
            range_seconds = max(300, min(604800, int(request.query_params.get("range_seconds", 3600))))
        except ValueError:
            range_seconds = 3600
        try:
            data = snapshot(target, include_series=True, range_seconds=range_seconds)
            evaluate_alerts(target, data["current"])
        except PrometheusRequestError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"target": self.get_serializer(target).data, **data})

    @action(detail=True, methods=["post"], url_path="test")
    def test(self, request, pk=None):
        target = self.get_object()
        require_project_manager(request.user, target.project)
        try:
            data = snapshot(target)
            evaluate_alerts(target, data["current"])
        except PrometheusRequestError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data)


class ServiceMonitorViewSet(viewsets.ModelViewSet):
    queryset = ServiceMonitor.objects.select_related("project", "server").all()
    serializer_class = ServiceMonitorSerializer

    def get_queryset(self):
        queryset = self.queryset.all()
        if not is_system_admin(self.request.user):
            queryset = queryset.filter(project_access_q(self.request.user, "project__")).distinct()
        project = self.request.query_params.get("project")
        if project:
            queryset = queryset.filter(project_id=project)
        return queryset

    def perform_create(self, serializer):
        require_project_manager(self.request.user, serializer.validated_data["project"])
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        service = self.get_object()
        require_project_manager(self.request.user, service.project)
        require_project_manager(self.request.user, serializer.validated_data.get("project", service.project))
        serializer.save()

    def perform_destroy(self, instance):
        require_project_manager(self.request.user, instance.project)
        instance.delete()

    @action(detail=True, methods=["post"], url_path="test")
    def test(self, request, pk=None):
        service = self.get_object()
        require_project_manager(request.user, service.project)
        data = service_snapshot(service)
        record_service_status(service, data)
        return Response(data, status=status.HTTP_200_OK if data["up"] else status.HTTP_400_BAD_REQUEST)


class ServiceMonitorEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ServiceMonitorEventSerializer

    def get_queryset(self):
        queryset = ServiceMonitorEvent.objects.select_related("service", "service__project").all()
        if not is_system_admin(self.request.user):
            queryset = queryset.filter(project_access_q(self.request.user, "service__project__")).distinct()
        project = self.request.query_params.get("project")
        if project:
            queryset = queryset.filter(service__project_id=project)
        return queryset


class MonitorNotificationRuleViewSet(viewsets.ModelViewSet):
    queryset = MonitorNotificationRule.objects.select_related("channel", "target", "target__project").prefetch_related("services__project", "channel__projects").all()
    serializer_class = MonitorNotificationRuleSerializer

    @staticmethod
    def _scope_projects(target, services, all_services, channel):
        if target:
            return [target.project]
        if all_services:
            return list(channel.projects.all()) if channel else []
        return [service.project for service in services]

    def _require_rule_manager(self, *, target, services, all_services, channel):
        projects = self._scope_projects(target, services, all_services, channel)
        if not projects:
            raise PermissionDenied("通知规则未关联可管理的项目。")
        for project in projects:
            require_project_manager(self.request.user, project)

    def _require_existing_rule_manager(self, rule):
        self._require_rule_manager(
            target=rule.target,
            services=list(rule.services.all()),
            all_services=rule.all_services,
            channel=rule.channel,
        )

    def get_queryset(self):
        queryset = self.queryset.all()
        if is_system_admin(self.request.user):
            return queryset
        managed_ids = set(self.request.user.project_pm_list.values_list("id", flat=True))
        if not managed_ids:
            return queryset.none()
        candidates = queryset.filter(
            Q(target__project_id__in=managed_ids)
            | Q(services__project_id__in=managed_ids)
            | Q(all_services=True, channel__projects__id__in=managed_ids)
        ).distinct()
        allowed_ids = []
        for rule in candidates:
            scope_ids = {project.id for project in self._scope_projects(rule.target, list(rule.services.all()), rule.all_services, rule.channel)}
            if scope_ids and scope_ids.issubset(managed_ids):
                allowed_ids.append(rule.id)
        return queryset.filter(id__in=allowed_ids)

    def perform_create(self, serializer):
        self._require_rule_manager(
            target=serializer.validated_data.get("target"),
            services=list(serializer.validated_data.get("services") or []),
            all_services=serializer.validated_data.get("all_services", False),
            channel=serializer.validated_data.get("channel"),
        )
        rule = serializer.save(created_by=self.request.user)
        from .notifications import backfill_active_alerts
        backfill_active_alerts(rule)

    def perform_update(self, serializer):
        existing = self.get_object()
        self._require_existing_rule_manager(existing)
        self._require_rule_manager(
            target=serializer.validated_data.get("target", existing.target),
            services=list(serializer.validated_data.get("services", existing.services.all())),
            all_services=serializer.validated_data.get("all_services", existing.all_services),
            channel=serializer.validated_data.get("channel", existing.channel),
        )
        rule = serializer.save()
        from .notifications import backfill_active_alerts
        backfill_active_alerts(rule)

    def perform_destroy(self, instance):
        self._require_existing_rule_manager(instance)
        instance.delete()


class MonitorNotificationDeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MonitorNotificationDeliverySerializer

    def get_queryset(self):
        queryset = MonitorNotificationDelivery.objects.select_related("channel", "target", "target__project", "service", "service__project").all()
        if is_system_admin(self.request.user):
            return queryset
        return queryset.filter(
            Q(target__project__pm=self.request.user) | Q(service__project__pm=self.request.user)
        ).distinct()


class MonitorCheckSettingsViewSet(viewsets.ViewSet):
    def _require_admin(self, request):
        if not is_system_admin(request.user):
            raise PermissionDenied("仅系统管理员可以维护监控检查频率。")

    def list(self, request):
        self._require_admin(request)
        return Response(MonitorCheckSettingsSerializer(MonitorCheckSettings.current()).data)

    @action(detail=False, methods=["put"], url_path="current")
    def update_current(self, request):
        self._require_admin(request)
        instance = MonitorCheckSettings.current()
        serializer = MonitorCheckSettingsSerializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="run-now")
    def run_now(self, request):
        self._require_admin(request)
        settings = MonitorCheckSettings.current()
        settings.last_target_check_at = None
        settings.last_service_check_at = None
        settings.save(update_fields=["last_target_check_at", "last_service_check_at", "updated_at"])
        from .tasks import run_scheduled_monitor_checks
        return Response(run_scheduled_monitor_checks())


class MonitorDashboardViewSet(viewsets.ViewSet):
    def list(self, request):
        return Response({"detail": "请使用 overview 接口。"})

    @action(detail=False, methods=["get"], url_path="overview")
    def overview(self, request):
        targets = MonitorTarget.objects.select_related("prometheus", "project").filter(enabled=True, prometheus__enabled=True)
        if not is_system_admin(request.user):
            targets = targets.filter(project_access_q(request.user, "project__")).distinct()
        project = request.query_params.get("project")
        if project:
            targets = targets.filter(project_id=project)
        items, errors = [], []
        for target in targets:
            try:
                data = snapshot(target)
                items.append({"target": MonitorTargetSerializer(target).data, **data})
            except PrometheusRequestError as exc:
                errors.append({"target_id": target.id, "target_name": target.name, "message": str(exc)})
        events = MonitorAlertEvent.objects.select_related("target", "target__project").filter(status="active")
        if not is_system_admin(request.user):
            events = events.filter(project_access_q(request.user, "target__project__")).distinct()
        if project:
            events = events.filter(target__project_id=project)
        services = ServiceMonitor.objects.select_related("project", "server").filter(enabled=True)
        if not is_system_admin(request.user):
            services = services.filter(project_access_q(request.user, "project__")).distinct()
        if project:
            services = services.filter(project_id=project)
        service_items, active_service_alerts, recovered_service_events = [], [], []
        for service in services:
            recent_events = list(service.events.all()[:20])
            latest = recent_events[0] if recent_events else None
            data = {
                "up": bool(latest and latest.status == "up"),
                "status_code": None,
                "response_time_ms": latest.response_time_ms if latest else None,
                "message": latest.message if latest else "等待后台首次检查",
            }
            service_items.append({"service": ServiceMonitorSerializer(service).data, **data})
            if latest and latest.status == "down":
                active_service_alerts.append(ServiceMonitorEventSerializer(latest).data)
            # 服务状态变化记录按时间倒序排列。只有一条 up 的下一条较早
            # 记录为 down 时，这条 up 才是一次真正的恢复，初始在线记录不展示。
            for index, event in enumerate(recent_events[:-1]):
                previous = recent_events[index + 1]
                if event.status != "up" or previous.status != "down":
                    continue
                serialized = dict(ServiceMonitorEventSerializer(event).data)
                serialized.update({
                    "alert_event_id": previous.id,
                    "started_at": ServiceMonitorEventSerializer(previous).data["occurred_at"],
                    "recovered_at": serialized["occurred_at"],
                })
                recovered_service_events.append(serialized)
        recovered_service_events.sort(key=lambda item: item["recovered_at"], reverse=True)
        return Response({
            "targets": items,
            "services": service_items,
            "service_alerts": active_service_alerts,
            "service_recoveries": recovered_service_events[:3],
            "errors": errors,
            "summary": {
                "total": targets.count(),
                "online": sum(1 for item in items if item["current"].get("up") and item["current"].get("up") >= 1),
                "services_total": services.count(),
                "services_online": sum(1 for item in service_items if item["up"]),
                "alerts": events.count() + len(active_service_alerts),
            },
        })


class MonitorAlertEventViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = MonitorAlertEventSerializer

    def get_queryset(self):
        queryset = MonitorAlertEvent.objects.select_related("target", "target__project").all()
        if not is_system_admin(self.request.user):
            queryset = queryset.filter(project_access_q(self.request.user, "target__project__")).distinct()
        return queryset
