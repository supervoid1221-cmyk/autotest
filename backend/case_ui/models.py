from django.conf import settings
from django.db import models
from selenium.webdriver.common.by import By

from project.models import Project

by_list = []

for attr in dir(By):
    if attr.startswith("_"):
        continue
    by_list.append((attr, attr))


def default_ui_case_tabs():
    """新建用例的默认页签。

    页签使用稳定 key 关联步骤，修改页签名称时不会导致步骤丢失。
    """
    return [{"key": "tab-1", "name": "登录页", "order": 1}]


def default_playwright_viewport():
    return {"width": 1440, "height": 900}


def playwright_step_display_name(action, target="", value=""):
    """根据操作本身生成展示名称，不在数据库重复保存派生字段。"""
    labels = {
        "goto": "打开页面", "input": "输入文本", "click": "点击元素", "clear": "清空输入",
        "select": "选择下拉项", "check": "勾选", "uncheck": "取消勾选",
        "assert_visible": "断言可见", "assert_text": "断言文本", "save_text": "提取文本",
        "sleep": "固定等待",
    }
    label = labels.get(str(action or ""), str(action or "操作"))
    subject = str(value or "").strip() if action in {"goto", "sleep"} else str(target or "").strip()
    if action == "sleep" and subject:
        subject = f"{subject}秒"
    return f"{label}：{subject}"[:64] if subject else label[:64]


def ui_step_display_name(action, element_name="", value=""):
    """传统 UI 步骤展示名称由操作和配置自动生成，不再持久化。"""
    labels = {
        "goto": "打开页面", "click": "点击元素", "input": "输入文本",
        "upload_file": "上传文件", "clear": "清空输入", "save_text": "提取文本",
        "assert_text": "断言文本", "assert_value": "断言值", "iframe_enter": "进入 IFrame",
        "iframe_exit": "退出 IFrame", "select": "选择下拉项", "js_code": "执行 JavaScript",
        "sleep": "固定等待",
    }
    action = str(action or "")
    label = labels.get(action, action or "操作")
    subject = str(value or "").strip() if action in {"goto", "sleep", "js_code"} else str(element_name or "").strip()
    return f"{label}：{subject}"[:64] if subject else label[:64]


# Create your models here.
class ElementModule(models.Model):
    """UI 元素在项目下的功能分组。"""

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="ui_element_modules", verbose_name="所属项目"
    )
    name = models.CharField("模块名称", max_length=64)

    class Meta:
        ordering = ["project_id", "id"]
        constraints = [
            models.UniqueConstraint(fields=["project", "name"], name="unique_ui_element_module_name")
        ]

    def __str__(self):
        return self.name


class Element(models.Model):
    """UI元素"""

    objects: models.QuerySet

    name = models.CharField("元素名称", max_length=32)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_ui_elements", verbose_name="创建人",
    )
    module = models.ForeignKey(
        ElementModule,
        on_delete=models.SET_NULL,
        related_name="elements",
        null=True,
        blank=True,
        verbose_name="所属模块",
    )

    by = models.CharField("定位方式", choices=by_list, default="XPATH", max_length=20)

    value = models.CharField("定位表达式", max_length=255)

    class Meta:
        ordering = ["-id"]


class UiCase(models.Model):
    """可直接由套件执行的 UI 自动化用例。"""

    class Browser(models.TextChoices):
        CHROME = "chrome", "Chrome"

    class RunMode(models.TextChoices):
        HEADLESS = "headless", "无头模式"
        HEADED = "headed", "有界面模式"

    name = models.CharField("用例名称", max_length=64)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="ui_cases")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_ui_cases", verbose_name="创建人",
    )
    description = models.CharField("用例描述", max_length=250, blank=True)
    browser = models.CharField("浏览器", max_length=16, choices=Browser.choices, default=Browser.CHROME)
    run_mode = models.CharField("运行模式", max_length=16, choices=RunMode.choices, default=RunMode.HEADLESS)
    tabs = models.JSONField("页签配置", default=default_ui_case_tabs, blank=True)
    enabled = models.BooleanField("启用", default=True)
    create_datetime = models.DateTimeField(auto_now_add=True)
    update_datetime = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]


class UiUploadedFile(models.Model):
    """供 UI 自动化步骤引用的项目级测试文件。"""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="ui_uploaded_files")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="uploaded_ui_test_files", verbose_name="上传人",
    )
    original_name = models.CharField("原始文件名", max_length=255)
    stored_path = models.CharField("存储路径", max_length=512, unique=True)
    size = models.PositiveBigIntegerField("文件大小", default=0)
    create_datetime = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return self.original_name


class UiStep(models.Model):
    """UI 用例中的有序操作步骤。"""

    class Action(models.TextChoices):
        GOTO = "goto", "打开页面"
        CLICK = "click", "点击元素"
        INPUT = "input", "输入文本"
        UPLOAD_FILE = "upload_file", "上传文件"
        CLEAR = "clear", "清空输入"
        SAVE_TEXT = "save_text", "提取文本"
        ASSERT_TEXT = "assert_text", "断言文本"
        ASSERT_VALUE = "assert_value", "断言值"
        IFRAME_ENTER = "iframe_enter", "进入 IFrame"
        IFRAME_EXIT = "iframe_exit", "退出 IFrame"
        SELECT = "select", "选择下拉项"
        JS_CODE = "js_code", "执行 JavaScript"
        SLEEP = "sleep", "固定等待"

    ui_case = models.ForeignKey(UiCase, on_delete=models.CASCADE, related_name="steps")
    tab_key = models.CharField("所属页签", max_length=64, default="tab-1")
    order = models.PositiveIntegerField("执行顺序", default=1)
    action = models.CharField("操作", max_length=24, choices=Action.choices)
    element = models.ForeignKey(Element, null=True, blank=True, on_delete=models.SET_NULL, related_name="ui_steps")
    value = models.TextField("操作值", blank=True)
    options = models.JSONField("扩展配置", default=dict, blank=True)
    continue_on_failure = models.BooleanField("失败后继续", default=False)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["ui_case", "order"], name="unique_ui_case_step_order"),
        ]


class PlaywrightCase(models.Model):
    """独立的 Playwright 智能定位 UI 用例，不改变既有 Selenium 用例。"""

    class Browser(models.TextChoices):
        CHROMIUM = "chromium", "Chromium"
        FIREFOX = "firefox", "Firefox"
        WEBKIT = "webkit", "WebKit"

    class RunMode(models.TextChoices):
        HEADLESS = "headless", "无头模式"
        HEADED = "headed", "有界面模式"

    name = models.CharField("用例名称", max_length=64)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="playwright_cases")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_playwright_cases", verbose_name="创建人",
    )
    description = models.CharField("用例描述", max_length=250, blank=True)
    browser = models.CharField("浏览器", max_length=16, choices=Browser.choices, default=Browser.CHROMIUM)
    run_mode = models.CharField("运行模式", max_length=16, choices=RunMode.choices, default=RunMode.HEADLESS)
    environment_name = models.CharField("执行环境", max_length=64, blank=True, default="")
    default_timeout = models.PositiveIntegerField("默认超时（毫秒）", default=10000)
    viewport = models.JSONField("视口", default=default_playwright_viewport, blank=True)
    tabs = models.JSONField("页签配置", default=default_ui_case_tabs, blank=True)
    enabled = models.BooleanField("启用", default=True)
    create_datetime = models.DateTimeField(auto_now_add=True)
    update_datetime = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]


class PlaywrightStep(models.Model):
    """Playwright 智能 UI 步骤：target 是自然语言元素描述，locator 是可选兜底。"""

    class Action(models.TextChoices):
        GOTO = "goto", "打开页面"
        INPUT = "input", "输入文本"
        UPLOAD_FILE = "upload_file", "上传文件"
        CLICK = "click", "点击"
        CLEAR = "clear", "清空输入"
        SELECT = "select", "选择下拉项"
        CHECK = "check", "勾选"
        UNCHECK = "uncheck", "取消勾选"
        ASSERT_VISIBLE = "assert_visible", "断言可见"
        ASSERT_TEXT = "assert_text", "断言文本"
        SAVE_TEXT = "save_text", "提取文本"
        SLEEP = "sleep", "固定等待"

    case = models.ForeignKey(PlaywrightCase, on_delete=models.CASCADE, related_name="steps")
    tab_key = models.CharField("所属页签", max_length=64, default="tab-1")
    order = models.PositiveIntegerField("执行顺序", default=1)
    action = models.CharField("操作方式", max_length=32, choices=Action.choices)
    target = models.CharField("页面元素/访问地址", max_length=512, blank=True, default="")
    value = models.TextField("操作值", blank=True, default="")
    locator_mode = models.CharField("定位方式", max_length=16, choices=[("auto", "智能定位"), ("manual", "手动兜底")], default="auto")
    fallback_type = models.CharField("备用定位类型", max_length=32, blank=True, default="")
    fallback_value = models.CharField("备用定位表达式", max_length=512, blank=True, default="")
    options = models.JSONField("扩展配置", default=dict, blank=True)
    continue_on_failure = models.BooleanField("失败后继续", default=False)

    class Meta:
        ordering = ["order", "id"]
        constraints = [models.UniqueConstraint(fields=["case", "order"], name="unique_playwright_case_step_order")]

    @property
    def display_name(self):
        return playwright_step_display_name(self.action, self.target, self.value)


class PlaywrightLocatorFingerprint(models.Model):
    """智能定位成功后的稳定元素特征，用于同环境下的后续定位加权。"""

    step = models.ForeignKey(PlaywrightStep, on_delete=models.CASCADE, related_name="locator_fingerprints")
    environment_name = models.CharField("执行环境", max_length=64, blank=True, default="")
    fingerprint = models.JSONField("元素指纹", default=dict)
    strategy = models.CharField("最后定位策略", max_length=64)
    success_count = models.PositiveIntegerField("成功次数", default=1)
    last_seen_at = models.DateTimeField("最后成功时间", auto_now=True)

    class Meta:
        ordering = ["-last_seen_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["step", "environment_name"], name="unique_playwright_locator_fingerprint_environment"
            )
        ]


