from django.conf import settings
from django.db import models

from Tesla.model_fields import EncryptedTextField
from account.models import get_default_tenant_id


class PrometheusInstance(models.Model):
    """平台可查询的 Prometheus 服务。访问令牌仅用于服务端请求。"""

    tenant = models.ForeignKey(
        "account.Tenant", on_delete=models.PROTECT,
        related_name="prometheus_instances", default=get_default_tenant_id,
        editable=False, verbose_name="所属租户",
    )
    name = models.CharField("名称", max_length=64)
    project = models.ForeignKey(
        "project.Project",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="prometheus_instances",
        verbose_name="所属项目",
    )
    base_url = models.URLField("访问地址", max_length=256)
    access_token = EncryptedTextField("访问令牌", blank=True, default="")
    enabled = models.BooleanField("启用", default=True)
    description = models.CharField("备注", max_length=256, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_prometheus_instances")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "name"], name="unique_tenant_prometheus_name",
            ),
        ]
        indexes = [models.Index(fields=["tenant", "project"], name="prom_tenant_project_idx")]

    def __str__(self):
        return self.name


class MonitorCluster(models.Model):
    class DiscoveryType(models.TextChoices):
        PROMETHEUS = "prometheus", "Prometheus Targets"
        KUBERNETES = "kubernetes", "Kubernetes 服务发现"
        FILE_SD = "file_sd", "文件服务发现"
        CLOUD = "cloud", "云服务发现"
    tenant = models.ForeignKey(
        "account.Tenant", on_delete=models.PROTECT,
        related_name="monitor_clusters", default=get_default_tenant_id,
        editable=False, verbose_name="所属租户",
    )
    project = models.ForeignKey("project.Project", on_delete=models.CASCADE, related_name="monitor_clusters")
    prometheus = models.ForeignKey(PrometheusInstance, on_delete=models.CASCADE, related_name="clusters")
    server = models.ForeignKey("system.ServerConnection", null=True, blank=True, on_delete=models.SET_NULL, related_name="monitor_clusters")
    name = models.CharField("集群名称", max_length=96)
    discovery_type = models.CharField("服务发现方式", max_length=24, choices=DiscoveryType.choices, default=DiscoveryType.PROMETHEUS)
    job = models.CharField("Prometheus Job", max_length=128, default="node")
    label_rules = models.JSONField("标签规则", default=dict, blank=True)
    instance_label_key = models.CharField("实例标签名", max_length=128, default="instance")
    node_name_label = models.CharField("节点名称标签", max_length=128, default="instance")
    enabled = models.BooleanField("启用同步", default=True)
    cpu_warning_threshold = models.FloatField(default=80); cpu_critical_threshold = models.FloatField(default=90)
    memory_warning_threshold = models.FloatField(default=85); memory_critical_threshold = models.FloatField(default=95)
    disk_warning_threshold = models.FloatField(default=80); disk_critical_threshold = models.FloatField(default=90)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(max_length=16, blank=True, default="")
    last_sync_message = models.CharField(max_length=512, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_monitor_clusters")
    created_at = models.DateTimeField(auto_now_add=True); updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ["-id"]
        constraints = [models.UniqueConstraint(fields=["project", "name"], name="unique_project_monitor_cluster")]
        indexes = [models.Index(fields=["tenant", "project"], name="cluster_tenant_project_idx")]


class MonitorTarget(models.Model):
    """一个 node_exporter 实例及其项目、服务器和告警阈值配置。"""

    tenant = models.ForeignKey(
        "account.Tenant", on_delete=models.PROTECT,
        related_name="monitor_targets", default=get_default_tenant_id,
        editable=False, verbose_name="所属租户",
    )
    prometheus = models.ForeignKey(PrometheusInstance, on_delete=models.CASCADE, related_name="targets")
    cluster = models.ForeignKey(MonitorCluster, null=True, blank=True, on_delete=models.CASCADE, related_name="targets")
    mode = models.CharField("监控模式", max_length=16, choices=(("standalone", "单机模式"), ("cluster", "集群模式")), default="standalone")
    discovered = models.BooleanField("服务发现生成", default=False)
    discovery_active = models.BooleanField("服务发现在线", default=True)
    discovery_labels = models.JSONField("发现标签", default=dict, blank=True)
    last_discovered_at = models.DateTimeField(null=True, blank=True)
    project = models.ForeignKey("project.Project", null=True, blank=True, on_delete=models.CASCADE, related_name="monitor_targets")
    server = models.ForeignKey("system.ServerConnection", null=True, blank=True, on_delete=models.SET_NULL, related_name="monitor_targets")
    name = models.CharField("目标名称", max_length=96)
    job = models.CharField("Prometheus Job", max_length=128, default="node")
    instance_label = models.CharField("Instance 标签", max_length=256, help_text="如 10.0.0.12:9100")
    extra_labels = models.JSONField("附加标签", default=dict, blank=True)
    enabled = models.BooleanField("启用监控", default=True)
    cpu_warning_threshold = models.FloatField("CPU 预警阈值", default=80)
    cpu_critical_threshold = models.FloatField("CPU 告警阈值", default=90)
    memory_warning_threshold = models.FloatField("内存预警阈值", default=85)
    memory_critical_threshold = models.FloatField("内存告警阈值", default=95)
    disk_warning_threshold = models.FloatField("磁盘预警阈值", default=80)
    disk_critical_threshold = models.FloatField("磁盘告警阈值", default=90)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_monitor_targets")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        constraints = [models.UniqueConstraint(fields=["prometheus", "instance_label"], name="unique_prometheus_monitor_target")]
        indexes = [models.Index(fields=["tenant", "project"], name="target_tenant_project_idx")]

    def __str__(self):
        return self.name


class ServiceMonitor(models.Model):
    """可配置的业务服务可用性监控。"""

    class MonitorType(models.TextChoices):
        HTTP = "http", "HTTP"
        TCP = "tcp", "TCP"
        DOCKER = "docker", "Docker 容器"

    tenant = models.ForeignKey(
        "account.Tenant", on_delete=models.PROTECT,
        related_name="service_monitors", default=get_default_tenant_id,
        editable=False, verbose_name="所属租户",
    )
    project = models.ForeignKey("project.Project", null=True, blank=True, on_delete=models.CASCADE, related_name="service_monitors")
    server = models.ForeignKey("system.ServerConnection", null=True, blank=True, on_delete=models.SET_NULL, related_name="service_monitors")
    name = models.CharField("服务名称", max_length=96)
    monitor_type = models.CharField("监控类型", max_length=16, choices=MonitorType.choices, default=MonitorType.HTTP)
    address = models.CharField("服务地址", max_length=512, help_text="HTTP 使用完整 URL；TCP 使用主机名或 IP；Docker 使用容器名称")
    port = models.PositiveIntegerField("端口", null=True, blank=True, help_text="TCP 监控必填")
    expected_status_codes = models.JSONField("期望状态码", default=list, blank=True)
    timeout_seconds = models.PositiveIntegerField("超时秒数", default=5)
    enabled = models.BooleanField("启用监控", default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_service_monitors")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["tenant", "project"], name="service_tenant_project_idx")]

    def __str__(self):
        return self.name


class ServiceMonitorEvent(models.Model):
    """服务可用性状态变化记录，避免每次轮询生成冗余数据。"""

    service = models.ForeignKey(ServiceMonitor, on_delete=models.CASCADE, related_name="events")
    status = models.CharField("状态", max_length=16, choices=(("up", "在线"), ("down", "离线")))
    message = models.CharField("检测信息", max_length=512, blank=True)
    response_time_ms = models.PositiveIntegerField("响应耗时", null=True, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]


class MonitorNotificationRule(models.Model):
    """复用通知管理渠道的监控告警发送规则。"""

    class Event(models.TextChoices):
        ALERT = "alert", "异常告警"
        RECOVERED = "recovered", "恢复通知"
        ALL = "all", "异常和恢复"

    channel = models.ForeignKey("suite.NotificationChannel", on_delete=models.CASCADE, related_name="monitor_rules")
    target = models.ForeignKey(MonitorTarget, null=True, blank=True, on_delete=models.CASCADE, related_name="notification_rules")
    services = models.ManyToManyField(ServiceMonitor, blank=True, related_name="notification_rules")
    all_services = models.BooleanField("全部服务", default=False)
    event = models.CharField("触发事件", max_length=16, choices=Event.choices, default=Event.ALERT)
    enabled = models.BooleanField("启用", default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_monitor_notification_rules")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]


class MonitorNotificationDelivery(models.Model):
    class Status(models.TextChoices):
        SENT = "sent", "已发送"
        FAILED = "failed", "发送失败"

    channel = models.ForeignKey("suite.NotificationChannel", on_delete=models.CASCADE, related_name="monitor_deliveries")
    rule = models.ForeignKey(MonitorNotificationRule, null=True, on_delete=models.SET_NULL, related_name="deliveries")
    target = models.ForeignKey(MonitorTarget, null=True, blank=True, on_delete=models.CASCADE, related_name="notification_deliveries")
    service = models.ForeignKey(ServiceMonitor, null=True, blank=True, on_delete=models.CASCADE, related_name="notification_deliveries")
    alert_event = models.ForeignKey("MonitorAlertEvent", null=True, blank=True, on_delete=models.SET_NULL, related_name="notification_deliveries")
    service_event = models.ForeignKey(ServiceMonitorEvent, null=True, blank=True, on_delete=models.SET_NULL, related_name="notification_deliveries")
    event = models.CharField("触发事件", max_length=16)
    status = models.CharField("投递状态", max_length=16, choices=Status.choices)
    payload = models.JSONField("消息内容", default=dict, blank=True)
    response_code = models.IntegerField("响应码", null=True, blank=True)
    response_summary = models.CharField("响应摘要", max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]


class MonitorAlertEvent(models.Model):
    class Severity(models.TextChoices):
        WARNING = "warning", "预警"
        CRITICAL = "critical", "告警"

    class Status(models.TextChoices):
        ACTIVE = "active", "告警中"
        RECOVERED = "recovered", "已恢复"

    target = models.ForeignKey(MonitorTarget, on_delete=models.CASCADE, related_name="alert_events")
    alert_key = models.CharField("规则标识", max_length=32)
    severity = models.CharField("严重程度", max_length=16, choices=Severity.choices)
    status = models.CharField("状态", max_length=16, choices=Status.choices, default=Status.ACTIVE)
    metric_value = models.FloatField("指标值", null=True, blank=True)
    threshold = models.FloatField("阈值", null=True, blank=True)
    message = models.CharField("告警内容", max_length=256)
    started_at = models.DateTimeField(auto_now_add=True)
    recovered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-id"]


class MonitorCheckSettings(models.Model):
    """平台级监控检查频率；固定使用主键 1 作为唯一配置。"""

    target_check_interval_seconds = models.PositiveIntegerField("监控目标检查频率（秒）", default=60)
    service_check_interval_seconds = models.PositiveIntegerField("服务监控检查频率（秒）", default=60)
    last_target_check_at = models.DateTimeField("最近监控目标检查时间", null=True, blank=True)
    last_service_check_at = models.DateTimeField("最近服务监控检查时间", null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_monitor_check_settings",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "监控检查频率"
        verbose_name_plural = verbose_name

    @classmethod
    def current(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
