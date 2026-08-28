from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
import jsonpath
import requests
import yaml

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows 开发环境的降级兼容
    fcntl = None


def response_indicates_expired_token(response):
    """识别认证失效响应，兼容 HTTP 401 和 HTTP 200 业务码。"""
    status_code = getattr(response, "status_code", None)
    if status_code == 401:
        return True
    try:
        payload = response.json() or {}
    except (AttributeError, ValueError):
        payload = {}
    if str(payload.get("code", "")) in {"1023", "401"}:
        return True
    message = " ".join(str(payload.get(key, "")) for key in ("msg", "message", "detail"))
    normalized_message = message.lower()
    return any(marker in normalized_message for marker in (
        "jwt expired", "token expired", "token has expired",
        "invalid token", "token invalid", "unauthorized",
    ))


@contextmanager
def _environment_auth_lock(project_id, environment_name):
    """以文件锁协调多个执行子进程，确保同一项目环境只会发起一次登录刷新。"""
    lock_dir = Path(__file__).resolve().parent.parent / "runtime_auth_locks"
    lock_dir.mkdir(exist_ok=True)
    lock_path = lock_dir / f"project_{project_id}_{environment_name}.lock"
    with open(lock_path, "a+", encoding="utf-8") as lock_file:
        if fcntl:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


# Create your models here.
class Project(models.Model):
    objects: models.QuerySet  # 将来会有这个属性

    name = models.CharField("项目名称", max_length=32)
    # 项目简介在页面中为可选项；允许提交空字符串，避免新建项目时因未填写简介被校验拦截。
    intro = models.CharField("项目简介", max_length=256, default="", blank=True)
    user_list = models.ManyToManyField(User, blank=True, related_name="project_set")
    pm = models.ForeignKey(
        User,
        null=True,
        on_delete=models.SET_DEFAULT,
        default=1,
        related_name="project_pm_list",
    )


class ProjectVariable(models.Model):
    """项目级运行变量，随场景调试和套件执行注入到当前运行上下文。"""

    objects: models.QuerySet

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="variables")
    name = models.CharField("变量名", max_length=64)
    value = models.TextField("变量值", blank=True, default="")
    description = models.CharField("参数描述", max_length=256, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "name"], name="unique_project_variable_name"),
        ]
        ordering = ["name", "id"]

    def __str__(self):
        return f"{self.project.name} / {self.name}"

    @classmethod
    def values_for_projects(cls, project_ids):
        """返回项目变量字典；传入项目顺序决定同名变量的覆盖顺序。"""
        ordered_ids = list(dict.fromkeys(int(project_id) for project_id in (project_ids or []) if project_id))
        values = {}
        for project_id in ordered_ids:
            for variable in cls.objects.filter(project_id=project_id).order_by("id"):
                values[variable.name] = variable.value
        return values


class Environment(models.Model):
    """项目的一个可执行环境，以及该环境的登录认证规则。"""

    objects: models.QuerySet

    class Name(models.TextChoices):
        DEV = "Dev", "Dev"
        TEST = "Test", "Test"
        PRE = "Pre", "Pre"
        PROD = "Prod", "Prod"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="environments")
    name = models.CharField("环境名称", max_length=64, choices=Name.choices, default=Name.TEST)
    base_url = models.CharField("环境地址", max_length=256)

    # 认证关闭时，套件仅使用 base_url，不会发起预登录请求。
    auth_enabled = models.BooleanField("启用自动登录", default=False)
    login_url = models.CharField("登录接口", max_length=256, blank=True)
    login_method = models.CharField("登录方法", max_length=8, default="POST")
    login_headers = models.JSONField("登录请求头", default=dict, blank=True)
    login_params = models.JSONField("登录查询参数", default=dict, blank=True)
    login_data = models.JSONField("登录表单参数", default=dict, blank=True)
    login_json = models.JSONField("登录 JSON 参数", default=dict, blank=True)
    token_jsonpath = models.CharField("Token 提取表达式", max_length=256, blank=True)
    token_name = models.CharField("变量名", max_length=64, default="token")
    token_header = models.CharField("Token 请求头", max_length=64, default="Authorization")
    token_prefix = models.CharField("Token 前缀", max_length=64, default="Bearer ", blank=True)
    token_ttl = models.PositiveIntegerField("Token 默认有效期（秒）", default=1800)
    # 认证缓存仅供服务端执行器使用，序列化器不会返回这三个字段。
    cached_token = models.TextField("共享 Token 缓存", blank=True, default="")
    token_expires_at = models.DateTimeField("Token 过期时间", null=True, blank=True)
    token_refreshed_at = models.DateTimeField("Token 刷新时间", null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["project", "name"], name="unique_project_environment_name")
        ]
        ordering = ["project_id", "id"]

    def __str__(self):
        return f"{self.project.name} - {self.name}"

    def save(self, *args, **kwargs):
        """认证规则变更后立即废弃旧缓存，避免继续使用错误账号或旧环境地址。"""
        if self.pk:
            previous = Environment.objects.filter(pk=self.pk).values(
                "project_id", "name", "base_url", "auth_enabled", "login_url", "login_method",
                "login_headers", "login_params", "login_data", "login_json", "token_jsonpath",
                "token_name", "token_header", "token_prefix", "token_ttl",
            ).first()
            if previous and any(previous[field] != getattr(self, field) for field in previous):
                self.cached_token = ""
                self.token_expires_at = None
                self.token_refreshed_at = None
        return super().save(*args, **kwargs)

    def _cached_token_valid(self):
        """只按平台配置的 token_ttl 判断缓存，不依赖 JWT exp。"""
        if not self.cached_token or not self.token_refreshed_at:
            return False
        return self._token_expire_time(self.token_refreshed_at) > timezone.now()

    def _token_expire_time(self, refreshed_at=None):
        """平台缓存过期时间始终为刷新时间 + token_ttl。"""
        refreshed_at = refreshed_at or timezone.now()
        return refreshed_at + timedelta(seconds=max(1, int(self.token_ttl or 1800)))

    def _login_and_extract_token(self):
        if not self.auth_enabled:
            return ""

        login_url = (self.login_url or "").strip()
        if not login_url.startswith(("http://", "https://")):
            login_url = f"{self.base_url.rstrip('/')}/{login_url.lstrip('/')}"

        try:
            response = requests.request(
                method=self.login_method,
                url=login_url,
                headers=self.login_headers or {},
                params=self.login_params or {},
                data=self.login_data or {},
                json=self.login_json or {},
                timeout=30,
            )
            response.raise_for_status()
            response_json = response.json()
        except requests.HTTPError as exc:
            # 登录请求参数不回显；仅返回服务端响应摘要，便于在页面定位账号、字段或网关校验问题。
            response_text = (exc.response.text or "").strip().replace("\n", " ")[:300]
            suffix = f"；服务端响应：{response_text}" if response_text else ""
            raise ValueError(
                f"环境「{self.name}」自动登录失败（HTTP {exc.response.status_code}）{suffix}"
            ) from exc
        except (requests.RequestException, ValueError) as exc:
            raise ValueError(f"环境「{self.name}」自动登录失败：{exc}") from exc

        values = jsonpath.jsonpath(response_json, self.token_jsonpath)
        if not values:
            raise ValueError(
                f"环境「{self.name}」未能按表达式「{self.token_jsonpath}」提取 Token。"
            )
        return str(values[0])

    def _write_token_to_run(self, run_path, alias, token):
        """共享缓存中的 Token 仍按本次运行写入独立变量文件，隔离变量生命周期。"""
        extract_path = run_path / "extract.yaml"
        existing = {}
        if extract_path.exists():
            with open(extract_path, encoding="utf-8") as file:
                existing = yaml.safe_load(file) or {}
        # 同时提供点号和下划线两种变量名；例如 ${front_api.token}、${front_api_token}。
        existing[f"{alias}.{self.token_name}"] = token
        existing[f"{alias}_{self.token_name}"] = token
        if alias == "default":
            existing[self.token_name] = token
        with open(extract_path, "w", encoding="utf-8") as file:
            yaml.safe_dump(existing, file, allow_unicode=True)
        return {self.token_header: f"{self.token_prefix}{token}"}

    def prepare_auth(self, run_path, alias="default", force_refresh=False):
        """按“项目 + 环境”复用认证 Token；失效时用跨进程锁保证只刷新一次。"""
        if not self.auth_enabled:
            return {}

        with _environment_auth_lock(self.project_id, self.name):
            # 每次都从数据库读取最新缓存，避免不同套件进程使用旧 Environment 实例。
            environment = Environment.objects.get(pk=self.pk)
            if not force_refresh and environment._cached_token_valid():
                token = environment.cached_token
            else:
                if force_refresh:
                    Environment.objects.filter(pk=environment.pk).update(
                        cached_token="", token_expires_at=None,
                    )
                token = environment._login_and_extract_token()
                refreshed_at = timezone.now()
                expires_at = environment._token_expire_time(refreshed_at)
                Environment.objects.filter(pk=environment.pk).update(
                    cached_token=token,
                    token_expires_at=expires_at,
                    token_refreshed_at=refreshed_at,
                )
                environment.cached_token = token
                environment.token_expires_at = expires_at
                environment.token_refreshed_at = refreshed_at
            return environment._write_token_to_run(run_path, alias, token)


class DatabaseConnection(models.Model):
    """多个项目在同一环境下可共享的数据库连接。"""

    class DatabaseType(models.TextChoices):
        MYSQL = "mysql", "MySQL"
        POSTGRESQL = "postgresql", "PostgreSQL"

    class SSLMode(models.TextChoices):
        PREFERRED = "preferred", "优先使用 TLS"
        REQUIRED = "required", "强制使用 TLS"
        DISABLED = "disabled", "关闭 TLS"

    projects = models.ManyToManyField(Project, related_name="database_connections", verbose_name="所属项目")
    environment_name = models.CharField("执行环境", max_length=16, choices=Environment.Name.choices)
    database_type = models.CharField("数据库类型", max_length=16, choices=DatabaseType.choices)
    function_name = models.CharField("调用函数", max_length=64)
    host = models.CharField("Host", max_length=255)
    port = models.PositiveIntegerField("Port")
    database = models.CharField("Database", max_length=128)
    username = models.CharField("用户名", max_length=128)
    password = models.CharField("密码", max_length=512, blank=True)
    ssl_mode = models.CharField("TLS 模式", max_length=16, choices=SSLMode.choices, default=SSLMode.PREFERRED)
    connect_timeout = models.PositiveIntegerField("连接超时（秒）", default=10)
    # SELECT 默认可用；写入能力必须由连接配置显式开启，避免测试过程误改数据。
    allow_write = models.BooleanField("允许执行 UPDATE", default=False)
    enabled = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["environment_name", "id"]

    def __str__(self):
        return f"{self.environment_name} - {self.function_name}"


class DynamicFunction(models.Model):
    """可被多个项目复用的动态函数代码组。"""
    projects = models.ManyToManyField(Project, related_name="dynamic_functions", verbose_name="所属项目")
    # 保留旧字段以兼容已有数据库记录；全局函数库中不再使用名称和说明字段。
    name = models.CharField("函数名称", max_length=64, blank=True, default="functions")
    description = models.CharField("函数说明", max_length=256, blank=True, default="")
    code = models.TextField("函数代码")
    enabled = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        if not self.pk:
            return "未保存动态函数"
        return "、".join(self.projects.values_list("name", flat=True)) or f"动态函数 #{self.pk}"
