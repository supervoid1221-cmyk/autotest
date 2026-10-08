"""套件执行队列与子进程生命周期管理。"""
import os
import logging
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path
from threading import Lock

from django.conf import settings
from django.utils import timezone

from suite.reporting import load_variable_resolution, load_variable_snapshot

api_framework_path = settings.BASE_DIR / settings.FRAMEWORK_DIR
python_path = sys.executable
run_path = api_framework_path / "main_by_django.py"
ini_path = api_framework_path / "pytest.ini"
execution_plan_path = api_framework_path / "execution_plan_test.py"

_cleanup_lock = Lock()
_last_cleanup_date = None
logger = logging.getLogger(__name__)


def _stop_process(process, resume=False, grace_seconds=5):
    """结束整组执行进程，宽限期后仍未退出则强制终止。"""
    if process is None or process.poll() is not None:
        return

    def send(sig):
        try:
            # pytest、浏览器驱动及 App 执行器都在独立进程组中，避免只结束父进程。
            os.killpg(os.getpgid(process.pid), sig)
        except OSError:
            try:
                process.send_signal(sig)
            except OSError:
                pass

    if resume:
        send(signal.SIGCONT)
    send(signal.SIGTERM)
    try:
        process.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        send(signal.SIGKILL)
        process.wait(timeout=grace_seconds)


def _is_terminal(result):
    """判断执行结果是否已经进入不可逆的终态。"""
    return result.status in {
        result.RunStatus.Done,
        result.RunStatus.Error,
        result.RunStatus.Canceled,
    }


def _claim_ready_run(result_id):
    """原子领取一条待执行记录。

    即使队列因网络重试或历史异常出现两条相同消息，也只有一个
    worker 能将 Ready 切换为 Running，其他 worker 直接返回。
    """
    from .models import RunResult

    return RunResult.objects.filter(
        pk=result_id,
        status=RunResult.RunStatus.Ready,
        cancel_requested=False,
    ).update(
        status=RunResult.RunStatus.Running,
        started_at=timezone.now(),
        update_datetime=timezone.now(),
    ) == 1


def cleanup_expired_files(retention_days=None, dry_run=False):
    """供 Django-Q 每日调度，也可由管理命令手动调用。"""
    from .retention import cleanup_expired_files as cleanup
    return cleanup(retention_days, dry_run=dry_run)


def _cleanup_once_daily():
    """执行任务时的兜底清理：每个 Web 进程每天最多执行一次。"""
    global _last_cleanup_date
    # 项目 USE_TZ=False，timezone.localdate() 不接受此时的 naive datetime。
    today = timezone.now().date()
    if _last_cleanup_date == today:
        return
    with _cleanup_lock:
        if _last_cleanup_date == today:
            return
        try:
            cleanup_expired_files()
            _last_cleanup_date = today
        except Exception:
            # 清理失败不应阻塞用户的测试任务。
            logger.exception("清理过期执行文件失败")


def submit_run(path, result_id, case_api_count, case_ui_count=0):
    """登记到统一 FIFO 调度器，资源不足时保持等待状态。"""
    _cleanup_once_daily()
    from execution_control.dispatcher import dispatch_waiting_tasks
    return dispatch_waiting_tasks()


def _finish(result, status, is_pass=None):
    from .reporting import finalize_unfinished_steps

    # 收口操作可能由子进程、超时处理和父进程 finally 同时触发。
    # 终态不可被后续的退出码或清理异常覆盖，避免“已通过”又变成“已取消”。
    if _is_terminal(result):
        return
    result.status = status
    result.finished_at = timezone.now()
    reason = "任务已取消。" if status == result.RunStatus.Canceled else "执行进程异常结束，步骤未执行。"
    report = result.native_report or {}
    snapshot = load_variable_snapshot(result.path)
    if snapshot:
        report["variables"] = snapshot
    report["variable_resolution"] = load_variable_resolution(result.path)
    result.native_report = finalize_unfinished_steps(
        report, reason, result.finished_at.isoformat()
    )
    result.run_process_id = None
    fields = ["status", "finished_at", "native_report", "run_process_id", "update_datetime"]
    if is_pass is not None:
        result.is_pass = is_pass
        fields.append("is_pass")
    result.save(update_fields=fields)
    if status == result.RunStatus.Error:
        # 执行器启动、超时等异常未必进入 pytest 子进程，也需要通知失败。
        try:
            from .notifications import notify_execution_result
            notify_execution_result(result.id)
        except Exception:
            pass


def _archive(path, result_id):
    archive_base = Path(path) / f"artifacts_{result_id}"
    archive_path = archive_base.with_suffix(".zip")
    try:
        shutil.make_archive(str(archive_base), "zip", path)
        shutil.move(str(archive_path), Path(path) / "artifacts.zip")
    except Exception:
        # 归档失败不覆盖已经生成的执行状态；日志仍可从运行目录读取。
        pass


def _reconcile_process_result(result, process, canceled=False, timed_out=False, execution_error=None):
    """子进程退出后统一收口执行状态。

    正常路径由 main_by_django 写入 Done/Error；如果子进程崩溃、异常退出，
    或返回后仍停留在 Ready/Running/Reporting，父进程必须兜底标记 Error。
    """
    result.refresh_from_db()
    if _is_terminal(result):
        # 子进程正常写入终态时也要清理运行 PID，避免后续误向已退出进程发信号。
        if result.run_process_id is not None:
            result.run_process_id = None
            result.save(update_fields=["run_process_id", "update_datetime"])
        return
    if canceled or result.cancel_requested:
        _finish(result, result.RunStatus.Canceled, False)
        return
    if timed_out:
        _finish(result, result.RunStatus.Error, False)
        return

    active_statuses = {
        result.RunStatus.Ready,
        result.RunStatus.Running,
        result.RunStatus.Reporting,
        result.RunStatus.Paused,
    }
    return_code = getattr(process, "returncode", None)
    abnormal_exit = execution_error is not None or process is None or return_code != 0
    if abnormal_exit or result.status in active_statuses or not _is_terminal(result):
        # 已由子进程写入 Done/Error 的结果不应被通知异常等后续退出码覆盖。
        _finish(result, result.RunStatus.Error, False)


def run_pytest(path, result_id=0, case_api_count=0, case_ui_count=0, tenant_id=None):
    """运行 pytest，并支持排队取消、运行中取消和总超时终止。"""
    from .models import RunResult
    result = None
    process = None
    canceled = False
    timed_out = False
    execution_error = None
    runner_log = Path(path) / "logs" / "runner.log"
    try:
        # 从这里开始所有执行异常都必须进入统一 finally；包括取结果、建目录、
        # 启动子进程和轮询数据库等异常。
        result = RunResult.objects.get(id=result_id)
        if tenant_id is not None and str(result.tenant_id) != str(tenant_id):
            raise ValueError("执行任务租户与执行记录不一致。")
        if _is_terminal(result):
            return
        if result.cancel_requested:
            _finish(result, result.RunStatus.Canceled)
            return
        if not _claim_ready_run(result_id):
            # 同一执行编号已被另一 worker 领取，不再启动第二个 pytest 进程。
            return
        result.refresh_from_db()

        command = [str(python_path), str(run_path), "-c", str(ini_path)]
        if case_api_count > 0 or case_ui_count > 0:
            command.append(str(execution_plan_path))
        command.extend(["./", "result_id", str(result_id)])
        environment = dict(os.environ)
        environment["PYTHONPATH"] = os.pathsep.join(
            [str(api_framework_path), str(settings.BASE_DIR), environment.get("PYTHONPATH", "")]
        )
        environment["PLATFORM_TENANT_ID"] = str(result.tenant_id)
        log_dir = Path(path) / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        from .execution_log import write_execution_log
        write_execution_log(f"套件任务开始，执行编号：{result_id}", base_path=path)
        runner_log = log_dir / "runner.log"
        with open(runner_log, "a", encoding="utf-8") as output:
            output.write(f"开始执行：{timezone.now().isoformat()}\n")
            output.flush()
            process = subprocess.Popen(
                command, cwd=path, env=environment,
                stdout=output, stderr=subprocess.STDOUT, text=True,
                start_new_session=True,
            )
            result.run_process_id = process.pid
            result.save(update_fields=["run_process_id", "update_datetime"])
            deadline = time.monotonic() + max(1, int(result.timeout_seconds or 1800))
            while process.poll() is None:
                time.sleep(0.5)
                result.refresh_from_db(fields=["cancel_requested", "timeout_seconds", "status"])
                if result.cancel_requested:
                    canceled = True
                    _stop_process(process, resume=result.status == result.RunStatus.Paused)
                    break
                elif time.monotonic() >= deadline:
                    timed_out = True
                    _stop_process(process, resume=result.status == result.RunStatus.Paused)
                    break
            if not canceled and not timed_out:
                process.wait(timeout=5)
            if canceled:
                output.write("任务已取消，执行进程已终止。\n")
                write_execution_log("套件任务已取消", "WARNING", base_path=path)
            elif timed_out:
                output.write("任务执行超时，执行进程已终止。\n")
                write_execution_log("套件任务执行超时", "ERROR", base_path=path)
    except Exception as exc:
        execution_error = exc
        try:
            from .execution_log import write_execution_log
            write_execution_log(f"执行器异常：{exc}", "ERROR", base_path=path)
        except Exception:
            pass
        try:
            runner_log.parent.mkdir(parents=True, exist_ok=True)
            with open(runner_log, "a", encoding="utf-8") as output:
                output.write(f"执行器异常：{exc}\n")
        except Exception:
            logger.exception("写入执行器异常日志失败，result_id=%s", result_id)
    finally:
        # finally 内的每一步也不能阻断后续收口；否则归档失败可能导致任务永久 running。
        try:
            _archive(path, result_id)
        except Exception:
            logger.exception("归档执行文件失败，result_id=%s", result_id)
        if result is not None:
            try:
                result.refresh_from_db()
                _reconcile_process_result(
                    result, process, canceled=canceled, timed_out=timed_out,
                    execution_error=execution_error,
                )
            except Exception:
                # 最后的兜底：即使报告/归档收口失败，也必须把活动任务置为 Error。
                logger.exception("收口执行结果失败，result_id=%s", result_id)
                try:
                    result.refresh_from_db()
                    if not _is_terminal(result):
                        _finish(result, result.RunStatus.Error, False)
                except Exception:
                    logger.exception("强制标记执行结果失败，result_id=%s", result_id)
        try:
            from execution_control.dispatcher import dispatch_waiting_tasks
            dispatch_waiting_tasks()
        except Exception:
            logger.exception("继续派发等待任务失败，result_id=%s", result_id)


def run_by_cron(suite_id, tenant_id=None):
    from .models import Suite
    queryset = Suite.objects.filter(id=suite_id)
    if tenant_id is not None:
        queryset = queryset.filter(tenant_id=tenant_id)
    suite = queryset.first()
    if suite is None:
        raise ValueError("定时任务租户与测试套件不一致。")
    return suite.run(executor_name="系统")
