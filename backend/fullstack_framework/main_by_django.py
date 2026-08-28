"""
@Filename:   api_framework_20230529/main_by_django
@Time:        2023/8/6 21:17
@Describe:    ...
"""
import os
from datetime import datetime

#  import shutil  # linux命令行常用函数
import sys  # 和python内部打交道
from pathlib import Path

import pytest
from django import setup
from django.utils import timezone

result_id = sys.argv[-1]
sys.argv = sys.argv[:-2]


path = Path(__file__).parents[1]  # 上级目录
sys.path.append(str(path))
# 框架历史代码使用 ``from commons import ...``，子进程 cwd 通常是上传结果目录，
# 因此必须显式加入 fullstack_framework 本身，否则场景运行会报 No module named commons。
framework_path = Path(__file__).parent
sys.path.insert(0, str(framework_path))

print(path)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Tesla.settings")
setup()

from suite.models import RunResult
from suite.reporting import (
    finalize_unfinished_steps, load_variable_resolution,
    merge_ui_runtime_results, recalculate_native_report, sanitize_variable_snapshot,
)

result: RunResult = RunResult.objects.get(id=result_id)

# 执行器通过该标识把接口步骤级结果写回当前 RunResult，供平台原生报告读取。
os.environ["PLATFORM_RUN_RESULT_ID"] = str(result.id)

result.status = result.RunStatus.Running
result.native_report = result.native_report or {}
result.native_report.setdefault("suite", result.suite.name)
result.native_report.setdefault("environment", getattr(result.suite.environment, "name", ""))
result.native_report["started_at"] = timezone.now().isoformat()
result.native_report.setdefault("scenarios", [])
recalculate_native_report(result.native_report)
result.save(update_fields=["status", "native_report", "update_datetime"])
ret_code = pytest.main()  # 启动框架，得到结果
no_tests_collected = ret_code == pytest.ExitCode.NO_TESTS_COLLECTED
execution_error = ret_code in (pytest.ExitCode.INTERNAL_ERROR, pytest.ExitCode.USAGE_ERROR)

if ret_code == pytest.ExitCode.OK:
    print("测试通过")
    result.is_pass = True
    # 原生报告会在 pytest 执行期间由每个接口步骤单独写入，不能用旧对象全字段保存覆盖它。
    result.save(update_fields=["is_pass", "update_datetime"])
else:
    print("测试失败")
    result.is_pass = False
    result.save(update_fields=["is_pass", "update_datetime"])

# pytest 结束后直接收口原生报告，不再生成第三方 HTML 报告。
result.status = result.RunStatus.Error if (no_tests_collected or execution_error) else result.RunStatus.Done
result.save(update_fields=["status", "update_datetime"])

result: RunResult = RunResult.objects.get(id=result_id)
report = result.native_report or {}

# UI/Playwright 在 pytest 子流程中逐步骤写入运行目录；最终报告与进度接口
# 共用同一套合并逻辑，避免实时状态和最终状态口径不一致。
report = merge_ui_runtime_results(report, Path.cwd())
finished_at = timezone.now()
report = finalize_unfinished_steps(
    report,
    "测试进程未执行到该步骤。",
    finished_at.isoformat(),
)
report["finished_at"] = finished_at.isoformat()
try:
    from fullstack_framework.commons.case_util import extrac_data
    report["variables"] = sanitize_variable_snapshot(extrac_data)
except Exception:
    report.setdefault("variables", {})
report["variable_resolution"] = load_variable_resolution(Path.cwd())
if report.get("started_at"):
    try:
        report["duration_ms"] = round((finished_at - datetime.fromisoformat(report["started_at"])).total_seconds() * 1000, 2)
    except (TypeError, ValueError):
        pass
result.native_report = report
result.finished_at = timezone.now()
result.save(update_fields=["native_report", "finished_at", "update_datetime"])
from suite.notifications import notify_execution_result
notify_execution_result(result.id)
print(result_id, result.is_pass, result.status)
