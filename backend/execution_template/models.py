from django.db import models

from Tesla.model_fields import EncryptedJSONField

from project.models import Project
from suite.models import Suite
from account.models import get_default_tenant_id


class ExecutionTemplate(models.Model):
    """参数化执行模板：定义参数列表并绑定套件，前台据此生成执行入口表单。"""

    tenant = models.ForeignKey(
        "account.Tenant", on_delete=models.PROTECT, related_name="execution_templates",
        default=get_default_tenant_id, editable=False,
    )
    name = models.CharField("模板名称", max_length=64)
    description = models.CharField("模板描述", max_length=250, blank=True)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="execution_templates", verbose_name="归属项目"
    )
    suite = models.ForeignKey(
        Suite, on_delete=models.CASCADE, related_name="execution_templates", verbose_name="关联套件"
    )
    # 参数定义：[{"key","label","type","required","default_value","options"}]
    # type: text / number / boolean / select
    parameters = EncryptedJSONField("参数定义", default=list, blank=True)
    # 输出字段：[{"key","label","source_step_id","json_path","display_type","sort"}]
    output_fields = models.JSONField("输出字段配置", default=list, blank=True)
    enabled = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-id"]
        constraints = [models.UniqueConstraint(fields=["tenant", "project", "name"], name="unique_tenant_execution_template")]
        indexes = [models.Index(fields=["tenant", "project", "id"], name="exec_tpl_tenant_project_idx")]

    def __str__(self):
        return self.name
