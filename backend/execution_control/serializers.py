from rest_framework import serializers

from .models import ExecutionTask, ExecutionWorker


class ExecutionTaskSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", default="-")
    source_type_name = serializers.CharField(source="get_source_type_display")
    status_name = serializers.CharField(source="get_status_display")
    report_path = serializers.SerializerMethodField()
    can_stop = serializers.SerializerMethodField()
    can_recover = serializers.SerializerMethodField()
    queue_position = serializers.SerializerMethodField()

    class Meta:
        model = ExecutionTask
        fields = "__all__"
        # 执行人由服务端在 sync 里从源任务推导，不接受客户端提交。
        read_only_fields = ["executor_name"]

    def get_report_path(self, obj):
        return f"/execution/report/{obj.source_type}/{obj.source_id}"

    def get_can_stop(self, obj):
        return obj.status in {
            ExecutionTask.Status.QUEUED, ExecutionTask.Status.PREPARING,
            ExecutionTask.Status.RUNNING, ExecutionTask.Status.PAUSED, ExecutionTask.Status.REPORTING,
        }

    def get_can_recover(self, obj):
        return obj.status in {ExecutionTask.Status.QUEUED, ExecutionTask.Status.PREPARING} and bool(obj.diagnostic_code)

    def get_queue_position(self, obj):
        # 列表/详情查询已在主 SQL 中注解该值；操作类响应无需另查数据库。
        return getattr(obj, "queue_position", None)

class ExecutionWorkerSerializer(serializers.ModelSerializer):
    kind_name = serializers.CharField(source="get_kind_display")
    status_name = serializers.CharField(source="get_status_display")

    class Meta:
        model = ExecutionWorker
        fields = "__all__"
