"""端到端校验租户并发数与存储配额是否真的生效。

为什么单独写这个文件：`max_regular_concurrent_executions` / `storage_quota_bytes` 只是 Tenant
上的配置字段，光看配置值判断不出有没有被强制执行。已有的覆盖是：

- `account/tests.py::TenantStorageQuotaTests` —— 只单测了 `ensure_tenant_storage_capacity`
  本身，没有证明**真实上传接口**会拦住超配额；
- `execution_control/tests.py::test_tenant_concurrency_limit_does_not_block_other_tenants`
  —— 覆盖了派发链路，但没钉住 `max_regular_concurrent_executions` 的判定边界。

这里补上缺口：
  1) 配额未满时上传必须通过（证明不是「一律拒绝」）；
  2) 配额用满后上传必须被拒，且**不落盘**；
  3) 别的租户的占用不能算到本租户头上；
  4) 并发额度的边界：活跃数达到上限即用尽，减少后恢复；排队未派发不占额度。
"""
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from account.models import Tenant, TenantMembership
from account.tenant_runtime import (
    tenant_active_regular_execution_count,
    tenant_has_regular_execution_capacity,
    tenant_storage_usage,
)
from execution_control.models import ExecutionTask
from project.models import Project


UPLOAD_URL = "/api/case_api/endpoint/upload-file/"


class TenantStorageQuotaEnforcementTests(TestCase):
    """存储配额：撞真实上传接口（case_api endpoint/upload-file）。"""

    def setUp(self):
        self.user = User.objects.create_user(username="quota-owner")
        self.tenant = Tenant.objects.create(name="配额租户", slug="quota-tenant")
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.user, role=TenantMembership.Role.OWNER
        )
        self.project = Project.objects.create(tenant=self.tenant, name="配额项目", pm=self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.upload_root = self.base / "uploaded_api_files"

    def tearDown(self):
        self._tmp.cleanup()

    # —— 辅助 ——

    def _set_quota(self, size):
        self.tenant.storage_quota_bytes = size
        self.tenant.save(update_fields=["storage_quota_bytes"])

    def _tenant_dir(self):
        return self.upload_root / f"tenant_{self.tenant.pk}"

    def _upload(self, size, name="demo.txt"):
        payload = SimpleUploadedFile(name, b"x" * size, content_type="text/plain")
        return self.client.post(
            UPLOAD_URL,
            {"file": payload},
            format="multipart",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )

    def _patched(self):
        """BASE_DIR 决定用量扫描的根；UPLOAD_ROOT 在导入时就算好了，必须单独打补丁，
        否则测试会往仓库目录里写真实文件。"""
        return (
            self.settings(BASE_DIR=self.base),
            patch("case_api.views.UPLOAD_ROOT", self.upload_root),
        )

    # —— 用例 ——

    def test_upload_within_quota_succeeds(self):
        self._set_quota(1000)
        settings_ctx, root_ctx = self._patched()
        with settings_ctx, root_ctx:
            response = self._upload(200)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(tenant_storage_usage(self.tenant.pk, base_dir=self.base), 200)

    def test_upload_over_quota_is_rejected_and_writes_nothing(self):
        self._set_quota(1000)
        # 预置 900 字节已用空间：再传 200 字节就超了
        tenant_dir = self._tenant_dir()
        tenant_dir.mkdir(parents=True)
        (tenant_dir / "existing.bin").write_bytes(b"x" * 900)

        settings_ctx, root_ctx = self._patched()
        with settings_ctx, root_ctx:
            response = self._upload(200)

        self.assertEqual(response.status_code, 409, response.data)
        self.assertIn("存储配额不足", str(response.data))
        # 被拒的请求不能留下任何文件
        self.assertEqual([p.name for p in tenant_dir.iterdir()], ["existing.bin"])

    def test_usage_does_not_count_other_tenants(self):
        """邻居租户占满空间，不能把本租户一起卡住。"""
        self._set_quota(1000)
        neighbour = Tenant.objects.create(name="邻居租户", slug="neighbour-tenant")
        neighbour_dir = self.upload_root / f"tenant_{neighbour.pk}"
        neighbour_dir.mkdir(parents=True)
        (neighbour_dir / "big.bin").write_bytes(b"x" * 5000)

        settings_ctx, root_ctx = self._patched()
        with settings_ctx, root_ctx:
            response = self._upload(200)

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(tenant_storage_usage(self.tenant.pk, base_dir=self.base), 200)

    def test_zero_quota_means_unlimited(self):
        """配额为 0 表示不限制（ensure_tenant_storage_capacity 里的 `if quota and ...`）。"""
        self._set_quota(0)
        settings_ctx, root_ctx = self._patched()
        with settings_ctx, root_ctx:
            response = self._upload(4096)

        self.assertEqual(response.status_code, 200, response.data)


class TenantConcurrencyQuotaTests(TestCase):
    """普通任务并发额度：钉住独立额度的判定边界。

    派发链路的集成验证在 execution_control/tests.py，这里只保证边界语义
    （`count < limit` 而不是 `<=`）不被改坏。
    """

    def setUp(self):
        self.user = User.objects.create_user(username="quota-concurrency")
        self.tenant = Tenant.objects.create(name="并发配额租户", slug="quota-concurrency")
        TenantMembership.objects.create(
            tenant=self.tenant, user=self.user, role=TenantMembership.Role.OWNER
        )
        self.project = Project.objects.create(tenant=self.tenant, name="并发项目", pm=self.user)

    def _task(self, status, source_id, dispatched=False, source_type="suite"):
        now = timezone.now()
        return ExecutionTask.objects.create(
            tenant=self.tenant, source_type=source_type, source_id=source_id,
            execution_no=str(source_id), project=self.project, name="配额任务",
            engine="pytest", status=status, last_activity_at=now, queued_at=now,
            started_at=now, source_created_at=now, source_updated_at=now,
            dispatched_at=now if dispatched else None,
        )

    def _set_limit(self, limit):
        self.tenant.max_regular_concurrent_executions = limit
        self.tenant.save(update_fields=["max_regular_concurrent_executions"])

    def test_limit_is_exclusive_boundary(self):
        self._set_limit(2)

        self.assertEqual(tenant_active_regular_execution_count(self.tenant.pk), 0)
        self.assertTrue(tenant_has_regular_execution_capacity(self.tenant), "空闲时应还有额度")

        self._task(ExecutionTask.Status.RUNNING, 5100)
        self.assertTrue(tenant_has_regular_execution_capacity(self.tenant), "1/2 应还有额度")

        self._task(ExecutionTask.Status.RUNNING, 5101)
        self.assertFalse(tenant_has_regular_execution_capacity(self.tenant), "2/2 应已用尽")

    def test_every_active_status_consumes_quota(self):
        """准备中 / 执行中 / 已暂停 / 汇总报告都算占用。"""
        self._set_limit(4)
        for index, status in enumerate((
            ExecutionTask.Status.PREPARING,
            ExecutionTask.Status.RUNNING,
            ExecutionTask.Status.PAUSED,
            ExecutionTask.Status.REPORTING,
        )):
            self._task(status, 5200 + index)

        self.assertEqual(tenant_active_regular_execution_count(self.tenant.pk), 4)
        self.assertFalse(tenant_has_regular_execution_capacity(self.tenant))

    def test_queued_task_consumes_quota_only_after_dispatch(self):
        """排队但还没交给 worker 的任务不该占额度，否则队列会自己把自己堵死。"""
        self._set_limit(1)
        task = self._task(ExecutionTask.Status.QUEUED, 5300)

        self.assertEqual(tenant_active_regular_execution_count(self.tenant.pk), 0)
        self.assertTrue(tenant_has_regular_execution_capacity(self.tenant), "未派发的排队任务不占额度")

        task.dispatched_at = timezone.now()
        task.save(update_fields=["dispatched_at"])

        self.assertEqual(tenant_active_regular_execution_count(self.tenant.pk), 1)
        self.assertFalse(tenant_has_regular_execution_capacity(self.tenant), "已派发的排队任务占额度")

    def test_finished_task_releases_quota(self):
        self._set_limit(1)
        task = self._task(ExecutionTask.Status.RUNNING, 5400)
        self.assertFalse(tenant_has_regular_execution_capacity(self.tenant))

        task.status = ExecutionTask.Status.SUCCEEDED
        task.save(update_fields=["status"])

        self.assertTrue(tenant_has_regular_execution_capacity(self.tenant), "结束后额度应释放")

    def test_lowering_limit_takes_effect_immediately(self):
        self._set_limit(3)
        self._task(ExecutionTask.Status.RUNNING, 5500)
        self.assertTrue(tenant_has_regular_execution_capacity(self.tenant))

        self._set_limit(1)
        self.assertFalse(tenant_has_regular_execution_capacity(self.tenant), "调小配额后应立即生效")

    def test_performance_task_does_not_consume_regular_capacity(self):
        self._set_limit(1)
        self._task(
            ExecutionTask.Status.RUNNING,
            5600,
            source_type=ExecutionTask.SourceType.PERFORMANCE,
        )

        self.assertEqual(tenant_active_regular_execution_count(self.tenant.pk), 0)
        self.assertTrue(tenant_has_regular_execution_capacity(self.tenant))
