import secrets
import uuid

from django.conf import settings
from django.db import models

from Tesla.model_fields import EncryptedJSONField, EncryptedTextField
from account.models import get_default_tenant_id


def generate_execution_no():
    return 1_000_000_000 + secrets.randbelow(9_000_000_000)


class AppApplication(models.Model):
    project = models.ForeignKey("project.Project", on_delete=models.CASCADE, related_name="app_applications")
    name = models.CharField("应用名称", max_length=96)
    platform = models.CharField("平台", max_length=16, choices=[("android", "Android")], default="android")
    package_name = models.CharField("Package Name", max_length=255)
    main_activity = models.CharField("Main Activity", max_length=255, blank=True, default="")
    startup_options = EncryptedJSONField("启动参数", default=dict, blank=True)
    auto_install = models.BooleanField("自动安装", default=False)
    replace_install = models.BooleanField("覆盖安装", default=True)
    clear_data = models.BooleanField("执行前清理数据", default=False)
    enabled = models.BooleanField("启用", default=True)
    description = models.CharField("描述", max_length=500, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_app_applications")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["project", "package_name"], name="unique_project_app_package")]


class AppVersion(models.Model):
    application = models.ForeignKey(AppApplication, on_delete=models.CASCADE, related_name="versions")
    version_name = models.CharField("版本名称", max_length=64)
    version_code = models.CharField("版本号", max_length=64, blank=True, default="")
    original_name = models.CharField("原始文件名", max_length=255, blank=True, default="")
    file_path = models.CharField("安装包路径", max_length=512, blank=True, default="")
    file_size = models.PositiveBigIntegerField("文件大小", default=0)
    enabled = models.BooleanField("启用", default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="uploaded_app_versions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
        constraints = [models.UniqueConstraint(fields=["application", "version_name"], name="unique_app_version_name")]


class AppExecutionNode(models.Model):
    project = models.ForeignKey("project.Project", on_delete=models.CASCADE, related_name="app_execution_nodes")
    name = models.CharField("节点名称", max_length=96)
    server_url = models.URLField("Appium 地址", max_length=255, default="http://127.0.0.1:4723")
    enabled = models.BooleanField("启用", default=True)
    status = models.CharField("状态", max_length=16, choices=[("unknown", "未知"), ("online", "在线"), ("offline", "离线")], default="unknown")
    last_message = models.CharField("最近检测信息", max_length=500, blank=True, default="")
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_app_nodes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        constraints = [models.UniqueConstraint(fields=["project", "name"], name="unique_project_app_node_name")]


class AppDevice(models.Model):
    class State(models.TextChoices):
        UNKNOWN = "unknown", "未知"
        ONLINE = "online", "在线"
        OFFLINE = "offline", "离线"
        BUSY = "busy", "占用中"
        INSPECTING = "inspecting", "检查中"

    project = models.ForeignKey("project.Project", on_delete=models.CASCADE, related_name="app_devices")
    node = models.ForeignKey(AppExecutionNode, on_delete=models.PROTECT, related_name="devices")
    name = models.CharField("设备名称", max_length=96)
    udid = models.CharField("设备 UDID", max_length=255)
    platform = models.CharField("平台", max_length=16, choices=[("android", "Android")], default="android")
    platform_version = models.CharField("系统版本", max_length=64, blank=True, default="")
    model = models.CharField("设备型号", max_length=128, blank=True, default="")
    resolution = models.CharField("分辨率", max_length=64, blank=True, default="")
    state = models.CharField("设备状态", max_length=16, choices=State.choices, default=State.UNKNOWN)
    enabled = models.BooleanField("启用", default=True)
    last_message = models.CharField("最近检测信息", max_length=500, blank=True, default="")
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_app_devices")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["state", "name", "id"]
        constraints = [models.UniqueConstraint(fields=["node", "udid"], name="unique_app_node_device_udid")]


class AppElement(models.Model):
    project = models.ForeignKey("project.Project", on_delete=models.CASCADE, related_name="app_elements")
    application = models.ForeignKey(
        AppApplication, null=True, blank=True, on_delete=models.CASCADE, related_name="elements"
    )
    module = models.ForeignKey(
        "project.Module", null=True, blank=True, on_delete=models.SET_NULL, related_name="app_elements"
    )
    name = models.CharField("元素名称", max_length=96)
    page_name = models.CharField("页面名称", max_length=128, blank=True, default="")
    activity = models.CharField("Activity", max_length=255, blank=True, default="")
    locator_type = models.CharField("定位方式", max_length=32, choices=[
        ("accessibility id", "Accessibility ID"), ("id", "Resource ID"), ("-android uiautomator", "UIAutomator"),
        ("xpath", "XPath"), ("text", "文本"), ("coordinate", "坐标"),
        ("ocr_text", "OCR 文字"), ("image_text", "图像文字"),
    ], default="id")
    locator_value = models.CharField("定位表达式", max_length=1000)
    fallback_locator = models.JSONField("备用定位", default=list, blank=True)
    element_class = models.CharField("元素类型", max_length=255, blank=True, default="")
    snapshot = models.JSONField("元素快照", default=dict, blank=True)
    description = models.CharField("描述", max_length=300, blank=True, default="")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_app_elements")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "application", "name"], name="unique_project_application_app_element_name"
            )
        ]


class AppInspectionSession(models.Model):
    class Status(models.TextChoices):
        STARTING = "starting", "启动中"
        ACTIVE = "active", "检查中"
        CLOSED = "closed", "已结束"
        ERROR = "error", "异常"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey("project.Project", on_delete=models.CASCADE, related_name="app_inspection_sessions")
    application = models.ForeignKey(AppApplication, on_delete=models.CASCADE, related_name="inspection_sessions")
    device = models.ForeignKey(AppDevice, on_delete=models.CASCADE, related_name="inspection_sessions")
    version = models.ForeignKey(AppVersion, null=True, blank=True, on_delete=models.SET_NULL, related_name="inspection_sessions")
    remote_session_id = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.STARTING, db_index=True)
    last_error = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="app_inspection_sessions"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now_add=True, db_index=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class AppCase(models.Model):
    tenant = models.ForeignKey(
        "account.Tenant", on_delete=models.PROTECT, related_name="app_cases",
        default=get_default_tenant_id, editable=False,
    )
    project = models.ForeignKey("project.Project", on_delete=models.CASCADE, related_name="app_cases")
    application = models.ForeignKey(AppApplication, on_delete=models.PROTECT, related_name="cases")
    default_device = models.ForeignKey(AppDevice, null=True, blank=True, on_delete=models.SET_NULL, related_name="default_cases")
    name = models.CharField("用例名称", max_length=96)
    description = models.CharField("描述", max_length=500, blank=True, default="")
    environment_name = models.CharField("执行环境", max_length=64, blank=True, default="")
    default_timeout = models.PositiveIntegerField("默认超时（毫秒）", default=10000)
    stop_on_failure = models.BooleanField("失败后停止", default=True)
    retry_count = models.PositiveSmallIntegerField("重试次数", default=0)
    enabled = models.BooleanField("启用", default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_app_cases")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [models.UniqueConstraint(fields=["tenant", "project", "name"], name="unique_tenant_app_case_name")]
        indexes = [models.Index(fields=["tenant", "project", "updated_at"], name="app_case_tenant_project_idx")]


class AppStep(models.Model):
    ACTIONS = [
        ("launch", "启动应用"), ("terminate", "关闭应用"), ("restart", "重启应用"),
        ("click", "点击"), ("input", "输入文本"), ("clear", "清空输入"), ("swipe", "滑动"),
        ("back", "返回"), ("home", "Home"), ("wait", "固定等待"), ("wait_element", "等待元素"),
        ("get_text", "提取文本"), ("assert_exists", "断言元素存在"), ("assert_text", "断言文本"),
        ("assert_attribute", "断言属性"), ("screenshot", "截图"), ("set_variable", "设置变量"),
    ]
    case = models.ForeignKey(AppCase, on_delete=models.CASCADE, related_name="steps")
    order = models.PositiveIntegerField("执行顺序", default=1)
    action = models.CharField("操作", max_length=32, choices=ACTIONS)
    element = models.ForeignKey(AppElement, null=True, blank=True, on_delete=models.SET_NULL, related_name="steps")
    target = EncryptedJSONField("定位/坐标", default=dict, blank=True)
    value = EncryptedTextField("操作值", blank=True, default="")
    options = EncryptedJSONField("扩展配置", default=dict, blank=True)
    continue_on_failure = models.BooleanField("失败后继续", default=False)

    class Meta:
        ordering = ["order", "id"]
        constraints = [models.UniqueConstraint(fields=["case", "order"], name="unique_app_case_step_order")]


class AppRun(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "等待设备"
        PREPARING = "preparing", "准备环境"
        INSTALLING = "installing", "安装应用"
        RUNNING = "running", "执行中"
        REPORTING = "reporting", "汇总报告"
        PASSED = "passed", "通过"
        FAILED = "failed", "未通过"
        ERROR = "error", "执行异常"
        STOPPED = "stopped", "已停止"

    tenant = models.ForeignKey(
        "account.Tenant", on_delete=models.PROTECT, related_name="app_runs",
        default=get_default_tenant_id, editable=False,
    )
    case = models.ForeignKey(AppCase, on_delete=models.PROTECT, related_name="runs")
    project = models.ForeignKey("project.Project", on_delete=models.CASCADE, related_name="app_runs")
    application = models.ForeignKey(AppApplication, on_delete=models.PROTECT, related_name="runs")
    version = models.ForeignKey(AppVersion, null=True, blank=True, on_delete=models.SET_NULL, related_name="runs")
    device = models.ForeignKey(AppDevice, on_delete=models.PROTECT, related_name="runs")
    execution_no = models.BigIntegerField(default=generate_execution_no, unique=True, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED, db_index=True)
    progress = models.PositiveSmallIntegerField(default=0)
    options = EncryptedJSONField(default=dict, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default="")
    log_content = models.TextField(blank=True, default="")
    stop_requested = models.BooleanField(default=False)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="created_app_runs")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        indexes = [models.Index(fields=["tenant", "status", "created_at"], name="app_run_tenant_status_idx")]


class AppStepResult(models.Model):
    run = models.ForeignKey(AppRun, on_delete=models.CASCADE, related_name="step_results")
    step = models.ForeignKey(AppStep, null=True, on_delete=models.SET_NULL, related_name="results")
    order = models.PositiveIntegerField(default=1)
    action = models.CharField(max_length=32)
    name = models.CharField(max_length=160)
    status = models.CharField(max_length=16, choices=[("running", "执行中"), ("passed", "通过"), ("failed", "失败"), ("skipped", "跳过")])
    duration_ms = models.PositiveIntegerField(default=0)
    message = models.TextField(blank=True, default="")
    detail = models.JSONField("执行快照", default=dict, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["order", "id"]


class AppArtifact(models.Model):
    run = models.ForeignKey(AppRun, on_delete=models.CASCADE, related_name="artifacts")
    step_result = models.ForeignKey(AppStepResult, null=True, blank=True, on_delete=models.CASCADE, related_name="artifacts")
    artifact_type = models.CharField(max_length=24, choices=[("screenshot", "截图"), ("page_source", "页面结构"), ("log", "日志")])
    name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=512)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
