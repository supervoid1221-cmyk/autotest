from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from account.models import Tenant
from project.models import Project
from system.models import ServerConnection

from .models import MonitorCluster, MonitorTarget, PrometheusInstance, ServiceMonitor


class MonitorTenantIsolationTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="monitor-admin", password="test-password", is_staff=True,
        )
        self.tenant_a = Tenant.objects.create(name="监控租户 A", slug="monitor-tenant-a")
        self.tenant_b = Tenant.objects.create(name="监控租户 B", slug="monitor-tenant-b")
        self.project_a = Project.objects.create(name="监控项目 A", tenant=self.tenant_a, pm=self.admin)
        self.project_b = Project.objects.create(name="监控项目 B", tenant=self.tenant_b, pm=self.admin)
        self.server_a = ServerConnection.objects.create(
            tenant=self.tenant_a, project=self.project_a, name="服务器", host="10.0.0.1",
            username="root", private_key_path="/tmp/key", created_by=self.admin,
        )
        self.server_b = ServerConnection.objects.create(
            tenant=self.tenant_b, project=self.project_b, name="服务器", host="10.0.1.1",
            username="root", private_key_path="/tmp/key", created_by=self.admin,
        )
        self.prometheus_a = PrometheusInstance.objects.create(
            tenant=self.tenant_a, project=self.project_a, name="Prometheus",
            base_url="http://10.0.0.1:9090", created_by=self.admin,
        )
        self.prometheus_b = PrometheusInstance.objects.create(
            tenant=self.tenant_b, project=self.project_b, name="Prometheus",
            base_url="http://10.0.1.1:9090", created_by=self.admin,
        )
        self.cluster_a = MonitorCluster.objects.create(
            tenant=self.tenant_a, project=self.project_a, prometheus=self.prometheus_a,
            server=self.server_a, name="集群 A", created_by=self.admin,
        )
        self.cluster_b = MonitorCluster.objects.create(
            tenant=self.tenant_b, project=self.project_b, prometheus=self.prometheus_b,
            server=self.server_b, name="集群 B", created_by=self.admin,
        )
        self.target_a = MonitorTarget.objects.create(
            tenant=self.tenant_a, project=self.project_a, prometheus=self.prometheus_a,
            server=self.server_a, name="目标 A", instance_label="10.0.0.1:9100",
            created_by=self.admin,
        )
        self.target_b = MonitorTarget.objects.create(
            tenant=self.tenant_b, project=self.project_b, prometheus=self.prometheus_b,
            server=self.server_b, name="目标 B", instance_label="10.0.1.1:9100",
            created_by=self.admin,
        )
        self.service_a = ServiceMonitor.objects.create(
            tenant=self.tenant_a, project=self.project_a, name="服务 A", monitor_type="http",
            address="http://10.0.0.1/health", created_by=self.admin,
        )
        self.service_b = ServiceMonitor.objects.create(
            tenant=self.tenant_b, project=self.project_b, name="服务 B", monitor_type="http",
            address="http://10.0.1.1/health", created_by=self.admin,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def _tenant_get(self, path, tenant):
        return self.client.get(path, HTTP_X_TENANT_ID=str(tenant.id))

    def test_platform_admin_lists_only_current_tenant_monitor_configuration(self):
        cases = (
            ("/api/monitor/prometheus/", self.prometheus_a.id),
            ("/api/monitor/cluster/", self.cluster_a.id),
            ("/api/monitor/target/", self.target_a.id),
            ("/api/monitor/service/", self.service_a.id),
        )
        for path, expected_id in cases:
            with self.subTest(path=path):
                response = self._tenant_get(path, self.tenant_a)
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual([item["id"] for item in response.data], [expected_id])

    def test_other_tenant_monitor_detail_is_not_accessible(self):
        response = self._tenant_get(
            f"/api/monitor/target/{self.target_b.id}/", self.tenant_a,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cross_tenant_monitor_relations_are_rejected(self):
        response = self.client.post(
            "/api/monitor/target/",
            {
                "project": self.project_a.id,
                "prometheus": self.prometheus_a.id,
                "server": self.server_b.id,
                "name": "跨租户目标",
                "instance_label": "10.0.0.2:9100",
            },
            format="json", HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            "/api/monitor/prometheus/",
            {
                "project": self.project_b.id,
                "name": "跨租户 Prometheus",
                "base_url": "http://10.0.1.2:9090",
            },
            format="json", HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_created_monitor_configuration_records_current_tenant(self):
        response = self.client.post(
            "/api/monitor/prometheus/",
            {
                "project": self.project_a.id,
                "name": "新 Prometheus",
                "base_url": "http://10.0.0.2:9090",
            },
            format="json", HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(
            PrometheusInstance.objects.get(pk=response.data["id"]).tenant_id,
            self.tenant_a.id,
        )

