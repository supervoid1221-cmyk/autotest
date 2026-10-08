from django.db import models
from django.db.models.functions import Coalesce
from account.models import get_default_tenant_id


class ExecutionTask(models.Model):
    tenant = models.ForeignKey(
        "account.Tenant", on_delete=models.PROTECT, related_name="execution_tasks",
        default=get_default_tenant_id, editable=False,
    )
    class SourceType(models.TextChoices):
        SUITE = "suite", "测试计划"
        APP = "app", "App 测试"
        PERFORMANCE = "performance", "性能测试"

    class Status(models.TextChoices):
        QUEUED = "queued", "等待调度"
        PREPARING = "preparing", "准备环境"
        RUNNING = "running", "执行中"
        PAUSED = "paused", "已暂停"
        REPORTING = "reporting", "汇总报告"
        SUCCEEDED = "succeeded", "执行成功"
        FAILED = "failed", "执行失败"
        ERROR = "error", "执行异常"
        CANCELED = "canceled", "已取消"
        STOPPED = "stopped", "已停止"

    source_type = models.CharField("任务类型", max_length=20, choices=SourceType.choices, db_index=True)
    source_id = models.PositiveBigIntegerField("源任务 ID")
    execution_no = models.CharField("执行编号", max_length=32, db_index=True)
    project = models.ForeignKey(
        "project.Project", null=True, blank=True, on_delete=models.CASCADE, related_name="execution_control_tasks"
    )
    name = models.CharField("任务名称", max_length=160)
    engine = models.CharField("执行引擎", max_length=32)
    status = models.CharField(max_length=20, choices=Status.choices, db_index=True)
    raw_status = models.CharField("原始状态", max_length=32, blank=True, default="")
    # 执行人名称快照，与 RunResult.executor_name 同策略：存名字而不是外键，
    # 用户改名或注销后历史任务仍能显示归属。补字段之前的历史任务没有这个信息，
    # 留空由前端显示为「-」，所以这里不用 default="系统" 之类的占位值把
    # 「无数据」伪装成「有数据」。
    executor_name = models.CharField("执行人", max_length=150, blank=True, default="")
    stage = models.CharField("当前阶段", max_length=64, blank=True, default="")
    progress = models.PositiveSmallIntegerField("进度", default=0)
    diagnostic_code = models.CharField("诊断编码", max_length=64, blank=True, default="")
    diagnostic_message = models.TextField("诊断信息", blank=True, default="")
    resource_keys = models.JSONField("所需资源", default=list, blank=True)
    dispatched_at = models.DateTimeField("派发时间", null=True, blank=True, db_index=True)
    dispatch_attempts = models.PositiveSmallIntegerField("派发次数", default=0)
    waiting_reason = models.CharField("排队原因", max_length=255, blank=True, default="")
    recovery_count = models.PositiveSmallIntegerField("恢复次数", default=0)
    last_recovered_at = models.DateTimeField("最近恢复时间", null=True, blank=True)
    timeout_seconds = models.PositiveIntegerField("超时秒数", default=1800)
    last_activity_at = models.DateTimeField("最近活动", db_index=True)
    queued_at = models.DateTimeField("入队时间")
    started_at = models.DateTimeField("开始时间", null=True, blank=True)
    finished_at = models.DateTimeField("结束时间", null=True, blank=True)
    source_created_at = models.DateTimeField("源任务创建时间")
    source_updated_at = models.DateTimeField("源任务更新时间")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-source_created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "source_type", "source_id"], name="unique_tenant_execution_control_source")
        ]
        indexes = [
            models.Index(fields=["status", "last_activity_at"], name="exec_task_status_activity_idx"),
            models.Index(fields=["project", "source_created_at"], name="exec_task_project_created_idx"),
            models.Index(fields=["tenant", "status", "last_activity_at"], name="exec_task_tenant_status_idx"),
            models.Index(
                models.F("tenant"),
                Coalesce("started_at", "queued_at").desc(),
                models.F("id").desc(),
                name="exec_task_tenant_started_idx",
            ),
        ]


class ExecutionWorker(models.Model):
    class Kind(models.TextChoices):
        SCHEDULER = "scheduler", "API/UI/App 执行器"
        PERFORMANCE = "performance", "性能执行器"

    class Status(models.TextChoices):
        ONLINE = "online", "在线"
        DEGRADED = "degraded", "异常"
        OFFLINE = "offline", "离线"

    instance_id = models.CharField("实例标识", max_length=160, unique=True)
    name = models.CharField("执行器名称", max_length=160)
    kind = models.CharField("执行器类型", max_length=20, choices=Kind.choices, db_index=True)
    hostname = models.CharField("主机名", max_length=255)
    process_id = models.PositiveIntegerField("进程 ID", null=True, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ONLINE, db_index=True)
    capacity = models.PositiveSmallIntegerField("并发容量", default=1)
    active_tasks = models.PositiveSmallIntegerField("活动任务", default=0)
    capabilities = models.JSONField("能力", default=list, blank=True)
    version = models.CharField("版本", max_length=64, blank=True, default="")
    message = models.CharField("状态说明", max_length=500, blank=True, default="")
    started_at = models.DateTimeField("启动时间")
    last_heartbeat_at = models.DateTimeField("最近心跳", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["kind", "name", "instance_id"]
