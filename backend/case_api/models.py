import re

import yaml
from django.conf import settings
from django.db import models

from project.models import Project


# 录制/历史接口中可能携带旧账号的一次性认证信息。启用项目环境认证后，
# 这类头必须由当前“项目 + 执行环境”生成的 Token 统一覆盖，避免跨域名、
# 跨项目或切换账号时继续发送旧 Token。
AUTH_HEADER_NAMES = {
    "authorization", "token", "x-token", "x-auth-token", "access-token",
    "access_token", "x-access-token", "bearer-token",
}


class EndpointModule(models.Model):
    """项目下的接口分组，项目名称作为固定根节点展示。"""

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="endpoint_modules", verbose_name="所属项目"
    )
    name = models.CharField("模块名称", max_length=64)

    class Meta:
        ordering = ["project_id", "id"]
        constraints = [
            models.UniqueConstraint(fields=["project", "name"], name="unique_endpoint_module_name")
        ]

    def __str__(self):
        return self.name


class Endpoint(models.Model):
    """接口"""

    objects: models.QuerySet

    name = models.CharField("接口名称", max_length=32)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_endpoints", verbose_name="创建人",
    )
    # 允许旧接口暂时不归属模块；新建接口由前端在模块内创建并选择模块。
    module = models.ForeignKey(
        EndpointModule,
        on_delete=models.SET_NULL,
        related_name="endpoints",
        null=True,
        blank=True,
        verbose_name="所属模块",
    )
    method = models.CharField("请求方法", max_length=8)
    url = models.CharField("接口地址", max_length=255)
    # 参数
    params = models.JSONField(
        "查询字符串", max_length=10240, blank=True, null=True
    )  # 必须是json
    data = models.JSONField("表单参数", max_length=10240, blank=True, null=True)  # 必须是json
    json = models.JSONField(
        "JSON参数", max_length=10240, blank=True, null=True
    )  # 必须是json
    # [["字段1", "字段2"], ["值1", "值2"], ...]；执行器按每一行展开独立请求。
    parametrize = models.JSONField("数据驱动参数", default=list, blank=True)
    cookies = models.JSONField(
        "Cookies", max_length=10240, blank=True, null=True
    )  # 必须是json
    headers = models.JSONField(
        "请求头", max_length=10240, blank=True, null=True
    )  # 必须是json
    # {"file": [{"name": "demo.xlsx", "path": "uploaded_api_files/uuid.xlsx", "size": 1024}]}
    # 文件内容保存在平台服务器，配置中仅保存文件元数据和受限的相对路径。
    files = models.JSONField("上传文件", default=dict, blank=True)

    def to_yaml_data(self, base_url, auth_headers=None, override=None):
        if self.url and not self.url.startswith(("http://", "https://")) and not (base_url or "").strip():
            raise ValueError(f"接口「{self.name}」使用相对地址，但未找到可用的执行环境 Base URL。")
        request = {"method": self.method, "url": self.url, "params": self.params or {}, "data": self.data or {}, "json": self.json or {}, "headers": self.headers or {}, "files": self.files or {}}
        if request["url"] and not request["url"].startswith(("http://", "https://")):
            request["url"] = f"{base_url.rstrip('/')}/{request['url'].lstrip('/')}"
        # 场景参数覆盖使用“直接参数对象”格式，例如 {"page": "1"}。
        # 同时兼容历史的 {"params": {...}, "json": {...}} 格式。
        override = override or {}
        request_fields = {"headers", "params", "data", "json"}
        if request_fields.intersection(override):
            for key, value in override.items():
                if key in request_fields:
                    request[key] = {**(request.get(key) or {}), **(value or {})}
        elif override:
            if self.params:
                target_field = "params"
            elif self.data:
                target_field = "data"
            elif self.json:
                target_field = "json"
            else:
                target_field = "params" if self.method.upper() == "GET" else "json"
            request[target_field] = {**(request.get(target_field) or {}), **override}
        if auth_headers:
            # requests 对 Header 名大小写不敏感，不能仅依赖 dict 的覆盖顺序。
            # 先删除接口定义/参数覆盖中遗留的认证头，再以环境认证结果写入，
            # 保证每个接口使用“自身项目 + 当前执行环境”的有效 Token。
            request["headers"] = {
                key: value for key, value in request["headers"].items()
                if str(key).strip().lower() not in AUTH_HEADER_NAMES
            }
            request["headers"].update(auth_headers)
        # 兼容此前通过浏览器录制保存的数据：HTTP/2 伪请求头（:authority 等）
        # 以及包含空白/换行的 Header 名均不能由 requests 发送。
        request["headers"] = {
            str(key): value for key, value in request["headers"].items()
            if str(key) == str(key).strip()
            and not str(key).startswith(":")
            and re.match(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$", str(key))
        }
        # requests 会在 multipart 请求时生成带 boundary 的 Content-Type；手填会导致文件无法解析。
        if request["files"]:
            request["headers"] = {key: value for key, value in request["headers"].items() if key.lower() != "content-type"}
        result = {"test_name": self.name, "request": request, "extract": {}, "validate": {}}
        if self.parametrize:
            result["parametrize"] = self.parametrize
        return result


class Scenario(models.Model):
    """业务场景：按顺序编排多个接口用例。"""

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="scenarios")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="created_scenarios", verbose_name="创建人",
    )
    projects = models.ManyToManyField(Project, related_name="linked_scenarios", blank=True)
    name = models.CharField("场景名称", max_length=64)
    description = models.CharField("场景描述", max_length=250, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class ScenarioStep(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name="steps")
    # 历史迁移允许存在尚未选择接口的编辑中步骤；新增和更新仍由序列化器校验为必填。
    # 接口被删除后保留场景步骤，方便用户在场景/套件中看到失效步骤并主动移除或替换。
    # 不能级联删除，否则前端仍显示旧步骤时再次删除会得到 404。
    endpoint = models.ForeignKey(Endpoint, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField("步骤名称", max_length=64, blank=True)
    order = models.PositiveIntegerField("执行顺序", default=1)
    request_method = models.CharField("请求方式覆盖", max_length=8, blank=True)
    request_url = models.CharField("请求地址覆盖", max_length=255, blank=True)
    request_override = models.JSONField("参数覆盖", default=dict, blank=True)
    extract = models.JSONField("数据提取", default=dict, blank=True)
    validate = models.JSONField("断言", default=dict, blank=True)
    # 在接口响应、断言、数据提取均成功后依次执行；每项使用 ${execute_sql_xxx("SQL")} 语法。
    post_sql = models.JSONField("后置数据库操作", default=list, blank=True)
    # {enabled, timeout, interval, initial_delay, retry_http_error, retry_assertion}
    polling = models.JSONField("轮询等待", default=dict, blank=True)
    continue_on_failure = models.BooleanField("失败后继续", default=True)
    retry_on_failure = models.BooleanField("失败后重试", default=False)
    failure_retry_count = models.PositiveSmallIntegerField("失败重试次数", default=1)

    class Meta:
        ordering = ["order", "id"]

    def apply_request_target(self, case_data, base_url):
        """将场景步骤的 Method/URL 覆盖应用到最终请求，不修改接口库定义。"""
        request = case_data["request"]
        if self.request_method:
            request["method"] = self.request_method.upper()
        if self.request_url:
            url = self.request_url.strip()
            if url and not url.startswith(("http://", "https://")):
                if not (base_url or "").strip():
                    raise ValueError(f"步骤「{self.name or self.endpoint.name}」使用相对地址，但未找到可用的执行环境 Base URL。")
                url = f"{base_url.rstrip('/')}/{url.lstrip('/')}"
            request["url"] = url
        return case_data


class ScenarioFlowNode(models.Model):
    """场景编排节点。

    接口配置仍存放在 ScenarioStep 中，节点只定义其处于主流程还是某个条件分支，
    因此原有的参数覆盖、提取、断言和轮询能力无需复制一份。
    """

    class NodeType(models.TextChoices):
        ENDPOINT = "endpoint", "接口步骤"
        CONDITION = "condition", "判断分支"

    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name="flow_nodes")
    node_type = models.CharField("节点类型", max_length=16, choices=NodeType.choices)
    step = models.OneToOneField(
        ScenarioStep, null=True, blank=True, on_delete=models.CASCADE, related_name="flow_node"
    )
    parent_branch = models.ForeignKey(
        "ScenarioBranch", null=True, blank=True, on_delete=models.CASCADE, related_name="nodes"
    )
    name = models.CharField("节点名称", max_length=64, blank=True)
    order = models.PositiveIntegerField("执行顺序", default=1)
    condition_logic = models.CharField("条件关系", max_length=8, default="and")

    class Meta:
        ordering = ["parent_branch_id", "order", "id"]


class ScenarioBranch(models.Model):
    """条件节点下的一个可选分支。第一版仅支持一层分支。"""

    condition_node = models.ForeignKey(
        ScenarioFlowNode, on_delete=models.CASCADE, related_name="branches", verbose_name="判断节点"
    )
    name = models.CharField("分支名称", max_length=64)
    order = models.PositiveIntegerField("优先级", default=1)
    # [{source: variable|step, variable, step_id, path, operator, expected}]
    conditions = models.JSONField("条件明细", default=list, blank=True)

    class Meta:
        ordering = ["order", "id"]
        constraints = [models.UniqueConstraint(fields=["condition_node", "order"], name="unique_scenario_branch_order")]
