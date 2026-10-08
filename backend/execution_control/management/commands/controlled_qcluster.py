import subprocess
import sys
import time
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from execution_control.models import ExecutionTask, ExecutionWorker
from execution_control.services import WorkerHeartbeat, diagnose_tasks
from execution_control.dispatcher import dispatch_waiting_tasks
from system.runtime import configured_max_worker_count


class Command(BaseCommand):
    help = "启动受控 Django-Q 执行器，并向统一执行控制中心上报心跳。"

    def add_arguments(self, parser):
        parser.add_argument("--run-once", action="store_true")
        parser.add_argument("-n", "--name", dest="cluster_name", default="")

    def handle(self, *args, **options):
        current_capacity = configured_max_worker_count()
        heartbeat = WorkerHeartbeat(
            ExecutionWorker.Kind.SCHEDULER,
            "API/UI/App 执行器",
            ["api", "ui", "playwright", "appium"],
            capacity=current_capacity,
        )

        command = [sys.executable, str(Path(settings.BASE_DIR) / "manage.py"), "qcluster"]
        if options.get("run_once"):
            command.append("--run-once")
        if options.get("cluster_name"):
            command.extend(["--name", options["cluster_name"]])

        def start_cluster(capacity):
            worker_environment = dict(os.environ)
            worker_environment["DJANGO_Q_WORKERS"] = str(capacity)
            return subprocess.Popen(command, cwd=settings.BASE_DIR, env=worker_environment)

        process = None
        try:
            heartbeat.touch(message="正在启动调度子进程。")
            process = start_cluster(current_capacity)
            while process.poll() is None:
                active = ExecutionTask.objects.filter(
                    source_type__in=[ExecutionTask.SourceType.SUITE, ExecutionTask.SourceType.APP],
                    status__in=[
                        ExecutionTask.Status.PREPARING, ExecutionTask.Status.RUNNING,
                        ExecutionTask.Status.PAUSED, ExecutionTask.Status.REPORTING,
                    ],
                ).count()
                desired_capacity = configured_max_worker_count()
                if desired_capacity != current_capacity and active == 0:
                    process.terminate()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    current_capacity = desired_capacity
                    heartbeat.defaults["capacity"] = current_capacity
                    process = start_cluster(current_capacity)
                    heartbeat.touch(message=f"Worker 数已更新为 {current_capacity}。")
                    continue
                message = "调度器运行正常。"
                if desired_capacity != current_capacity:
                    message = f"Worker 数待调整为 {desired_capacity}，将在当前任务结束后生效。"
                heartbeat.touch(active_tasks=active, message=message)
                dispatch_waiting_tasks()
                diagnose_tasks()
                time.sleep(10)
            if process.returncode:
                raise CommandError(f"Django-Q 调度器异常退出，退出码 {process.returncode}。")
        except KeyboardInterrupt:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        finally:
            if process and process.poll() is None:
                process.terminate()
            heartbeat.close()
