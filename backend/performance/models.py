import secrets

from django.conf import settings
from django.db import models

from Tesla.model_fields import EncryptedJSONField
from account.models import get_default_tenant_id


def generate_execution_no():
    return 1_000_000_000 + secrets.randbelow(9_000_000_000)


class PerformanceScenario(models.Model):
    class LoadMode(models.TextChoices):
        STAGES = "stages", "阶段模式"
        THREAD_GROUP = "thread_group", "线程组模式"

    class SourceMode(models.TextChoices):
        SINGLE = "single", "单一业务"
        MIXED = "mixed", "多业务混合"

    class SourceType(models.TextChoices):
        ENDPOINT = "endpoint", "单接口"
        SCENARIO = "scenario", "接口场景"

    class LoadType(models.TextChoices):
        SMOKE = "smoke", "冒烟测试"
        LOAD = "load", "负载测试"
        STRESS = "stress", "压力测试"
        SPIKE = "spike", "峰值测试"
        SOAK = "soak", "稳定性测试"
        CUSTOM = "custom", "自定义"

    class ParameterStrategy(models.TextChoices):
        SEQUENTIAL = "sequential", "顺序循环"
        RANDOM = "random", "随机取值"
        UNIQUE = "unique", "全局唯一"

    tenant = models.ForeignKey(
        "account.Tenant", on_delete=models.PROTECT, related_name="performance_scenarios",
        default=get_default_tenant_id, editable=False,
    )
    project = models.ForeignKey("project.Project", on_delete=models.CASCADE, related_name="performance_scenarios")
    environment = models.ForeignKey("project.Environment", on_delete=models.PROTECT, related_name="performance_scenarios")
    source_mode = models.CharField("业务模式", max_length=16, choices=SourceMode.choices, default=SourceMode.SINGLE)
    source_type = models.CharField("压测对象", max_length=16, choices=SourceType.choices, default=SourceType.SCENARIO)
    source_endpoint = models.ForeignKey("case_api.Endpoint", null=True, blank=True, on_delete=models.SET_NULL, related_name="performance_scenarios")
    source_scenario = models.ForeignKey("case_api.Scenario", null=True, blank=True, on_delete=models.SET_NULL, related_name="performance_scenarios")
    monitor_target = models.ForeignKey("monitor.MonitorTarget", null=True, blank=True, on_delete=models.SET_NULL, related_name="performance_scenarios")
    notification_channels = models.ManyToManyField("suite.NotificationChannel", blank=True, related_name="performance_scenarios")
    name = models.CharField("场景名称", max_length=96)
    description = models.CharField("描述", max_length=500, blank=True, default="")
    load_type = models.CharField("负载模板", max_length=16, choices=LoadType.choices, default=LoadType.LOAD)
    load_mode = models.CharField("负载模式", max_length=16, choices=LoadMode.choices, default=LoadMode.STAGES)
    thread_count = models.PositiveIntegerField("线程数", default=10)
    duration_seconds = models.PositiveIntegerField("持续时间（秒）", default=60)
    ramp_up_seconds = models.PositiveIntegerField("启动时间（秒）", default=0)
    graceful_stop_seconds = models.PositiveIntegerField("停止等待时间（秒）", default=5)
    stages = models.JSONField("负载阶段", default=list)
    thresholds = models.JSONField("性能阈值", default=dict, blank=True)
    business_mix = EncryptedJSONField("混合业务配置", default=list, blank=True)
    parameter_filename = models.CharField("参数文件名", max_length=255, blank=True, default="")
    parameter_strategy = models.CharField("参数取值策略", max_length=16, choices=ParameterStrategy.choices, default=ParameterStrategy.SEQUENTIAL)
    parameter_data = EncryptedJSONField("参数化数据", default=list, blank=True)
    scenario_snapshot = EncryptedJSONField("接口场景快照", default=dict, blank=True)
    enabled = models.BooleanField("启用", default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_performance_scenarios")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["tenant", "project", "name"], name="unique_tenant_performance_scenario")]
        indexes = [models.Index(fields=["tenant", "project", "updated_at"], name="perf_scn_tenant_proj_idx")]


class PerformanceRun(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "等待执行"
        PREPARING = "preparing", "准备环境"
        RUNNING = "running", "执行中"
        REPORTING = "reporting", "汇总报告"
        PASSED = "passed", "通过"
        FAILED = "failed", "未通过"
        ERROR = "error", "执行异常"
        STOPPED = "stopped", "已停止"

    tenant = models.ForeignKey(
        "account.Tenant", on_delete=models.PROTECT, related_name="performance_runs",
        default=get_default_tenant_id, editable=False,
    )
    scenario = models.ForeignKey(PerformanceScenario, on_delete=models.PROTECT, related_name="runs")
    project = models.ForeignKey("project.Project", on_delete=models.CASCADE, related_name="performance_runs")
    environment = models.ForeignKey("project.Environment", on_delete=models.PROTECT, related_name="performance_runs")
    monitor_target = models.ForeignKey("monitor.MonitorTarget", null=True, blank=True, on_delete=models.SET_NULL, related_name="performance_runs")
    execution_no = models.BigIntegerField(default=generate_execution_no, unique=True, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED, db_index=True)
    progress = models.PositiveSmallIntegerField(default=0)
    configured_vus = models.FloatField("配置峰值并发", default=0)
    execution_config = EncryptedJSONField("执行配置快照", default=dict, blank=True)
    current_vus = models.FloatField(default=0)
    current_rps = models.FloatField(default=0)
    current_tps = models.FloatField(default=0)
    summary = models.JSONField(default=dict, blank=True)
    threshold_results = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")
    work_dir = models.CharField(max_length=512, blank=True, default="")
    process_id = models.PositiveIntegerField(null=True, blank=True)
    stop_requested = models.BooleanField(default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    load_started_at = models.DateTimeField("实际压测开始时间", null=True, blank=True)
    load_finished_at = models.DateTimeField("实际压测结束时间", null=True, blank=True)
    load_duration_ms = models.PositiveBigIntegerField("实际压测时长（毫秒）", null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_performance_runs")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["tenant", "status", "created_at"], name="perf_run_tenant_status_idx")]


class PerformanceMetricBucket(models.Model):
    run = models.ForeignKey(PerformanceRun, on_delete=models.CASCADE, related_name="metric_buckets")
    timestamp = models.DateTimeField(db_index=True)
    vus = models.FloatField(default=0)
    target_vus = models.FloatField(default=0, null=True, blank=True)
    rps = models.FloatField(default=0)
    tps = models.FloatField(default=0)
    request_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    error_rate = models.FloatField(default=0)
    duration_avg = models.FloatField(default=0)
    duration_min = models.FloatField(default=0)
    duration_max = models.FloatField(default=0)
    duration_p90 = models.FloatField(default=0)
    duration_p95 = models.FloatField(default=0)
    duration_p99 = models.FloatField(default=0)

    class Meta:
        ordering = ["timestamp"]
        constraints = [models.UniqueConstraint(fields=["run", "timestamp"], name="unique_performance_run_bucket")]


class PerformanceEndpointMetric(models.Model):
    run = models.ForeignKey(PerformanceRun, on_delete=models.CASCADE, related_name="endpoint_metrics")
    endpoint_name = models.CharField(max_length=128)
    method = models.CharField(max_length=8, blank=True, default="")
    url = models.CharField(max_length=512, blank=True, default="")
    request_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    error_rate = models.FloatField(default=0)
    duration_avg = models.FloatField(default=0)
    duration_min = models.FloatField(default=0)
    duration_median = models.FloatField(default=0)
    duration_max = models.FloatField(default=0)
    duration_p90 = models.FloatField(default=0)
    duration_p95 = models.FloatField(default=0)
    duration_p99 = models.FloatField(default=0)
    throughput = models.FloatField(default=0)
    received_bytes = models.BigIntegerField(default=0)
    sent_bytes = models.BigIntegerField(default=0)
    configured_ratio = models.FloatField(default=0)

    class Meta:
        ordering = ["-duration_p95", "endpoint_name"]
        constraints = [models.UniqueConstraint(fields=["run", "endpoint_name"], name="unique_performance_run_endpoint")]


class PerformanceNotificationDelivery(models.Model):
    class Status(models.TextChoices):
        SENT = "sent", "已发送"
        FAILED = "failed", "发送失败"

    run = models.ForeignKey(PerformanceRun, on_delete=models.CASCADE, related_name="notification_deliveries")
    channel = models.ForeignKey("suite.NotificationChannel", on_delete=models.PROTECT, related_name="performance_deliveries")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.FAILED)
    response_code = models.PositiveIntegerField(null=True, blank=True)
    response_summary = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
