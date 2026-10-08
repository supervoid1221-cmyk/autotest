"""静态报告文件的服务端定位。

租户命名空间上线前，运行目录直接躺在 `upload_yaml/` 下；上线后是
`upload_yaml/tenant_<租户>/`。而 `suite/serializers.py` 的 `get_log_url`
只把「运行目录名」放进 URL（`/api/suite/static/<运行目录>/logs/pytest.log`），
不带租户那一段，所以服务端必须拿执行记录里的 `path` 去定位真实位置，
否则迁进租户目录之后所有历史报告链接都会 404。

既有测试把 `serve` mock 掉了，只断言「调没调」，证明不了文件真能读到，
所以这里走真实路由、真实认证，读真实文件内容。

两个容易踩的点：
- `static_server` 上挂着 `@api_view()`（DRF 的 api_view 返回的就是
  `WrappedAPIView.as_view()`），所以它是 DRF 视图、要带认证，
  用 `APIClient.force_authenticate`，裸 `RequestFactory` 会拿到 401。
- urlconf 里的 `document_root` 是相对的 `"upload_yaml"`，`serve` 也按当前
  工作目录解析，所以测试把工作目录切到临时目录，就不会碰真实仓库目录。
"""
import os
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from account.models import TenantMembership, get_default_tenant_id
from account.tenant_runtime import tenant_path
from project.models import Environment, Project
from suite.models import RunResult, Suite
from suite.serializers import RunResultSerializer


def body_of(response):
    if hasattr(response, "streaming_content"):
        return b"".join(response.streaming_content).decode("utf-8")
    return response.content.decode("utf-8")


class StaticReportPathTests(TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(os.chdir, self.original_cwd)
        os.chdir(self.temp.name)

        self.tenant_id = get_default_tenant_id()
        self.user = User.objects.create_user("static-reader")
        TenantMembership.objects.create(
            tenant_id=self.tenant_id,
            user=self.user,
            role=TenantMembership.Role.OWNER,
            status=TenantMembership.Status.ACTIVE,
        )
        self.project = Project.objects.create(name="静态报告项目", intro="", pm=self.user)
        environment = Environment.objects.create(
            project=self.project, name="Dev", base_url="https://static.example.com",
        )
        self.suite = Suite.objects.create(name="静态报告套件", environment=environment)

        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @property
    def tenant_dir(self):
        return f"tenant_{str(self.tenant_id).lower()}"

    def make_run(self, path):
        """按给定 path 建记录，并在磁盘上真的写出一份日志。"""
        run = RunResult.objects.create(suite=self.suite, project=self.project, path=path)
        log_dir = Path(path) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "pytest.log").write_text(f"日志内容::{path}", encoding="utf-8")
        return run

    def fetch(self, directory_name):
        return self.client.get(f"/api/suite/static/{directory_name}/logs/pytest.log")

    def test_flat_legacy_layout_is_served(self):
        """迁移前的扁平布局必须继续可用（迁移是渐进的，两种布局会共存）。"""
        self.make_run("upload_yaml/legacy-result")
        response = self.fetch("legacy-result")
        self.assertEqual(response.status_code, 200)
        self.assertIn("upload_yaml/legacy-result", body_of(response))

    def test_tenant_scoped_layout_is_served(self):
        """迁进租户目录后，URL 不带租户段也必须能取到文件。"""
        stored = f"upload_yaml/{self.tenant_dir}/scoped-result"
        self.make_run(stored)
        response = self.fetch("scoped-result")
        self.assertEqual(response.status_code, 200)
        self.assertIn(stored, body_of(response))

    def test_consolidated_tenant_storage_layout_is_served(self):
        stored = tenant_path(
            Path("upload_yaml"), self.tenant_id, "consolidated-result"
        )
        self.make_run(stored)

        response = self.fetch("consolidated-result")

        self.assertEqual(response.status_code, 200)
        self.assertIn(str(stored), body_of(response))

    def test_unknown_run_directory_is_404(self):
        response = self.fetch("no-such-run")
        self.assertEqual(response.status_code, 404)

    def test_log_url_uses_run_directory_name_only(self):
        """锁住前后端契约：URL 里只有运行目录名，不带租户段。

        这条是 static_server 那套定位逻辑的前提，改了它就会全线 404。
        """
        stored = f"upload_yaml/{self.tenant_dir}/scoped-result"
        run = self.make_run(stored)
        data = RunResultSerializer(run).data
        self.assertEqual(data["log_url"], "/api/suite/static/scoped-result/logs/pytest.log")
        self.assertEqual(data["artifacts_url"], "/api/suite/static/scoped-result/artifacts.zip")
