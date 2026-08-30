import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ("monitor", "0006_prometheusinstance_project"),
        ("system", "0004_serverconnection_project"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(name="MonitorCluster", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("name", models.CharField(max_length=96, verbose_name="集群名称")),
            ("discovery_type", models.CharField(choices=[("prometheus", "Prometheus Targets"), ("kubernetes", "Kubernetes 服务发现"), ("file_sd", "文件服务发现"), ("cloud", "云服务发现")], default="prometheus", max_length=24, verbose_name="服务发现方式")),
            ("job", models.CharField(default="node", max_length=128, verbose_name="Prometheus Job")), ("label_rules", models.JSONField(blank=True, default=dict, verbose_name="标签规则")),
            ("instance_label_key", models.CharField(default="instance", max_length=128, verbose_name="实例标签名")), ("node_name_label", models.CharField(default="instance", max_length=128, verbose_name="节点名称标签")),
            ("enabled", models.BooleanField(default=True, verbose_name="启用同步")), ("cpu_warning_threshold", models.FloatField(default=80)), ("cpu_critical_threshold", models.FloatField(default=90)), ("memory_warning_threshold", models.FloatField(default=85)), ("memory_critical_threshold", models.FloatField(default=95)), ("disk_warning_threshold", models.FloatField(default=80)), ("disk_critical_threshold", models.FloatField(default=90)),
            ("last_synced_at", models.DateTimeField(blank=True, null=True)), ("last_sync_status", models.CharField(blank=True, default="", max_length=16)), ("last_sync_message", models.CharField(blank=True, default="", max_length=512)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)),
            ("created_by", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_monitor_clusters", to=settings.AUTH_USER_MODEL)), ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="monitor_clusters", to="project.project")), ("prometheus", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="clusters", to="monitor.prometheusinstance")), ("server", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="monitor_clusters", to="system.serverconnection"))], options={"ordering": ["-id"]}),
        migrations.AddConstraint(model_name="monitorcluster", constraint=models.UniqueConstraint(fields=("project", "name"), name="unique_project_monitor_cluster")),
        migrations.AddField(model_name="monitortarget", name="cluster", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="targets", to="monitor.monitorcluster")),
        migrations.AddField(model_name="monitortarget", name="mode", field=models.CharField(choices=[("standalone", "单机模式"), ("cluster", "集群模式")], default="standalone", max_length=16, verbose_name="监控模式")),
        migrations.AddField(model_name="monitortarget", name="discovered", field=models.BooleanField(default=False, verbose_name="服务发现生成")), migrations.AddField(model_name="monitortarget", name="discovery_active", field=models.BooleanField(default=True, verbose_name="服务发现在线")), migrations.AddField(model_name="monitortarget", name="discovery_labels", field=models.JSONField(blank=True, default=dict, verbose_name="发现标签")), migrations.AddField(model_name="monitortarget", name="last_discovered_at", field=models.DateTimeField(blank=True, null=True)),
    ]
