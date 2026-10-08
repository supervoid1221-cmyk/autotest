from django.contrib import admin

from .models import ExecutionTask, ExecutionWorker


@admin.register(ExecutionTask)
class ExecutionTaskAdmin(admin.ModelAdmin):
    list_display = ("execution_no", "source_type", "name", "project", "status", "progress", "last_activity_at")
    list_filter = ("source_type", "status")
    search_fields = ("execution_no", "name")


@admin.register(ExecutionWorker)
class ExecutionWorkerAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "hostname", "status", "active_tasks", "last_heartbeat_at")
    list_filter = ("kind", "status")
