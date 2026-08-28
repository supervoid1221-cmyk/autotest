import shutil
import time
import secrets
from datetime import datetime
from pathlib import Path

from croniter import croniter
from django.db import models, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django_q.humanhash import uuid
from django_q.models import Schedule
from django_q.tasks import schedule

import yaml

from case_api.models import Scenario, ScenarioFlowNode
from case_ui.models import PlaywrightCase, UiCase, playwright_step_display_name, ui_step_display_name
from project.models import Environment, Project, ProjectVariable
from fullstack_framework.commons.ddt_util import ddt
from suite.tasks import submit_run
from suite.reporting import load_variable_resolution, recalculate_native_report, record_variable_resolution


def generate_execution_no():
    """生成不体现数据库顺序的 10 位纯数字执行编号。"""
    return 1_000_000_000 + secrets.randbelow(9_000_000_000)


def _merge_initial_variables(run_path, variables):
    """把参数化执行的初始变量写入运行目录的 extract.yaml，覆盖同名变量。

    pytest 执行时优先按 ${变量名} 占位符读取该文件，因此用户本次填写的参数
    会以最高优先级替换环境 Token、历史提取变量等同名变量。
    """
    extract_path = Path(run_path) / "extract.yaml"
    existing = {}
    if extract_path.exists():
        with open(extract_path, encoding="utf-8") as file:
            existing = yaml.safe_load(file) or {}
    existing.update(variables)
    with open(extract_path, "w", encoding="utf-8") as file:
        yaml.safe_dump(existing, file, allow_unicode=True)


class Suite(models.Model):
    """测试套件"""

    objects: models.QuerySet

    class RunType(models.TextChoices):
        ONCE = "O", "单次执行"
        CRON = "C", "Cron"
        WebHook = "W", "WebHook"

    class ScheduleKind(models.TextChoices):
        ONCE = "once", "一次性"
        DAILY = "daily", "每日"
        WEEKLY = "weekly", "每周"
        MONTHLY = "monthly", "每月"
        CUSTOM = "custom", "自定义 Cron"

    name = models.CharField("套件名称", max_length=32)
    environment = models.ForeignKey(
        Environment,
        verbose_name="执行环境",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    scenarios = models.ManyToManyField(Scenario, through="SuiteScenario", blank=True)
    ui_cases = models.ManyToManyField(UiCase, through="SuiteUiCase", blank=True)
    playwright_cases = models.ManyToManyField(PlaywrightCase, through="SuitePlaywrightCase", blank=True)
    description = models.CharField("套件描述", max_length=250, blank=True)
    enabled = models.BooleanField("启用", default=True)
    run_type = models.CharField(
        "运行类型", choices=RunType.choices, default=RunType.ONCE, max_length=1
    )

    cron = models.CharField("cron表达式", max_length=20, blank=True)
    schedule_kind = models.CharField(
        "定时类型", choices=ScheduleKind.choices, max_length=12, default=ScheduleKind.DAILY
    )
    schedule_config = models.JSONField("定时配置", default=dict, blank=True)
    schedule_timezone = models.CharField("定时时区", max_length=64, default="Asia/Shanghai")
    hook_key = models.CharField("hook密钥", max_length=255, blank=True)
    execution_timeout = models.PositiveIntegerField("执行超时（秒）", default=1800)
    schedule = models.ForeignKey(
        Schedule, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        ordering = ["-id"]

    def save(self, *args, **kwargs):
        if self.run_type == self.RunType.WebHook:
            # 创建webhook 的密钥
            if not self.hook_key:
                self.hook_key = uuid()[0]

        # 必须先保存套件，才能拿到有效 ID；旧实现先创建 Schedule，导致 args=(None,)。
        previous_schedule = self.schedule
        result = super().save(*args, **kwargs)

        if self.run_type == self.RunType.CRON and self.enabled:
            # 每次保存仅保留一个调度记录，避免重复保存产生多条 Cron 任务。
            if previous_schedule:
                previous_schedule.delete()
            if self.schedule_kind == self.ScheduleKind.ONCE:
                run_at = parse_datetime(str((self.schedule_config or {}).get("run_at") or ""))
                if run_at is None:
                    raise ValueError("一次性定时任务缺少有效的执行时间")
                if timezone.is_naive(run_at):
                    run_at = timezone.make_aware(run_at, timezone.get_current_timezone())
                self.schedule = schedule(
                    "suite.tasks.run_by_cron", self.id,
                    schedule_type=Schedule.ONCE, next_run=run_at,
                )
            else:
                # django-q 默认 next_run 是保存时刻，会造成调度器启动后立即补跑。
                # 改为计算 Cron 的下一次匹配时间，确保只在用户设置的时间触发。
                next_run = croniter(self.cron, timezone.now()).get_next(datetime)
                self.schedule = schedule(
                    "suite.tasks.run_by_cron", self.id, cron=self.cron,
                    schedule_type=Schedule.CRON, next_run=next_run,
                )
            super().save(update_fields=["schedule"])
        elif previous_schedule:
            # 切换运行类型或停用套件时移除旧的定时调度。
            previous_schedule.delete()
            self.schedule = None
            super().save(update_fields=["schedule"])

        return result

    def case_api_count(self):
        """场景中的 API 步骤数量。"""
        return sum(
            suite_scenario.scenario.steps.count()
            for suite_scenario in self.ordered_scenario_links()
        )

    def case_ui_count(self):
        """套件中启用的 UI 用例数量。"""
        return self.ordered_ui_case_links().filter(ui_case__enabled=True).count()

    def case_playwright_count(self):
        return self.ordered_playwright_case_links().filter(playwright_case__enabled=True).count()

    def case_all_ui_count(self):
        """列表展示使用的 UI 用例总数，包含传统 UI 与 Playwright 智能 UI。"""
        return self.case_ui_count() + self.case_playwright_count()

    def ordered_scenario_links(self):
        """按套件中配置的顺序返回场景关联，避免退化为 Scenario 默认排序。"""
        return self.suitescenario_set.select_related("scenario").order_by("order", "id")

    def ordered_ui_case_links(self):
        return self.suiteuicase_set.select_related("ui_case", "ui_case__project").order_by("order", "id")

    def ordered_playwright_case_links(self):
        return self.suiteplaywrightcase_set.select_related("playwright_case", "playwright_case__project").order_by("order", "id")

    def ordered_execution_items(self):
        """返回接口场景和 UI 用例的统一混合执行队列。"""
        items = list(self.execution_items.select_related(
            "scenario", "scenario__project", "ui_case", "ui_case__project", "playwright_case", "playwright_case__project"
        ).order_by("order", "id"))
        if items:
            return items
        # 兼容迁移前数据和直接写入旧关联表的调用方。
        legacy_items = []
        order = 1
        for link in self.ordered_scenario_links():
            legacy_items.append(SuiteExecutionItem(
                suite=self, item_type=SuiteExecutionItem.ItemType.API,
                scenario=link.scenario, order=order,
            ))
            order += 1
        for link in self.ordered_ui_case_links():
            legacy_items.append(SuiteExecutionItem(
                suite=self, item_type=SuiteExecutionItem.ItemType.UI,
                ui_case=link.ui_case, order=order,
            ))
            order += 1
        for link in self.ordered_playwright_case_links():
            legacy_items.append(SuiteExecutionItem(
                suite=self, item_type=SuiteExecutionItem.ItemType.PLAYWRIGHT_UI,
                playwright_case=link.playwright_case, order=order,
            ))
            order += 1
        return legacy_items

    def sync_execution_items(self, items):
        """原子同步混合执行顺序，并保持旧的多对多关联可用。"""
        items = list(items)
        scenario_ids = [item["id"] for item in items if item["type"] == SuiteExecutionItem.ItemType.API]
        ui_case_ids = [item["id"] for item in items if item["type"] == SuiteExecutionItem.ItemType.UI]
        playwright_case_ids = [item["id"] for item in items if item["type"] == SuiteExecutionItem.ItemType.PLAYWRIGHT_UI]
        with transaction.atomic():
            Suite.objects.select_for_update().get(pk=self.pk)
            previous_continue = dict(
                SuiteScenario.objects.filter(suite=self).values_list("scenario_id", "continue_on_failure")
            )
            SuiteExecutionItem.objects.filter(suite=self).delete()
            SuiteScenario.objects.filter(suite=self).delete()
            SuiteUiCase.objects.filter(suite=self).delete()
            SuitePlaywrightCase.objects.filter(suite=self).delete()
            SuiteScenario.objects.bulk_create([
                SuiteScenario(
                    suite=self, scenario_id=scenario_id, order=order,
                    continue_on_failure=previous_continue.get(scenario_id, False),
                )
                for order, scenario_id in enumerate(scenario_ids, start=1)
            ])
            SuiteUiCase.objects.bulk_create([
                SuiteUiCase(suite=self, ui_case_id=ui_case_id, order=order)
                for order, ui_case_id in enumerate(ui_case_ids, start=1)
            ])
            SuitePlaywrightCase.objects.bulk_create([
                SuitePlaywrightCase(suite=self, playwright_case_id=case_id, order=order)
                for order, case_id in enumerate(playwright_case_ids, start=1)
            ])
            SuiteExecutionItem.objects.bulk_create([
                SuiteExecutionItem(
                    suite=self,
                    item_type=item["type"],
                    scenario_id=item["id"] if item["type"] == SuiteExecutionItem.ItemType.API else None,
                    ui_case_id=item["id"] if item["type"] == SuiteExecutionItem.ItemType.UI else None,
                    playwright_case_id=item["id"] if item["type"] == SuiteExecutionItem.ItemType.PLAYWRIGHT_UI else None,
                    order=order,
                )
                for order, item in enumerate(items, start=1)
            ])

    def sync_scenarios(self, scenario_ids):
        """兼容旧接口：接口场景在前，保留当前 UI 用例顺序。"""
        current_ui_ids = list(self.ordered_ui_case_links().values_list("ui_case_id", flat=True))
        current_playwright_ids = list(self.ordered_playwright_case_links().values_list("playwright_case_id", flat=True))
        self.sync_execution_items(
            [{"type": SuiteExecutionItem.ItemType.API, "id": item_id} for item_id in scenario_ids]
            + [{"type": SuiteExecutionItem.ItemType.UI, "id": item_id} for item_id in current_ui_ids]
            + [{"type": SuiteExecutionItem.ItemType.PLAYWRIGHT_UI, "id": item_id} for item_id in current_playwright_ids]
        )

    def sync_ui_cases(self, ui_case_ids):
        """兼容旧接口：保留当前接口场景顺序，UI 用例排在其后。"""
        current_scenario_ids = list(self.ordered_scenario_links().values_list("scenario_id", flat=True))
        current_playwright_ids = list(self.ordered_playwright_case_links().values_list("playwright_case_id", flat=True))
        self.sync_execution_items(
            [{"type": SuiteExecutionItem.ItemType.API, "id": item_id} for item_id in current_scenario_ids]
            + [{"type": SuiteExecutionItem.ItemType.UI, "id": item_id} for item_id in ui_case_ids]
            + [{"type": SuiteExecutionItem.ItemType.PLAYWRIGHT_UI, "id": item_id} for item_id in current_playwright_ids]
        )

    def run(self, initial_variables=None, environment=None, executor_name=None, reuse_result=None):
        """执行套件中用例。

        initial_variables: 参数化执行的初始变量，写入 extract.yaml 并覆盖同名变量。
        environment: 可选，覆盖套件默认执行环境（需与套件环境同项目）。
        executor_name: 本次执行人的显示名称；未传入时视为系统任务。
        """
        environment = environment or self.active_environment
        execution_environment_name = str(environment.name)
        execution_executor_name = str(executor_name or "系统").strip() or "系统"

        # 1. 生成执行结果
        # 2. 生成 yaml 和 excel 测试用例
        # 3. 子进程
        #    1. 启动pytest
        #    2. 更新执行结果

        # 1. 锁定套件记录后再检查/创建，避免双击或并发请求同时创建两条执行任务。
        #    手动重跑时复用原执行记录，保证报告链接和执行编号保持不变。
        previous_path = None
        with transaction.atomic():
            locked_suite = Suite.objects.select_for_update().get(pk=self.pk)
            active_result = RunResult.objects.filter(
                suite=locked_suite,
                status__in=[RunResult.RunStatus.Ready, RunResult.RunStatus.Running, RunResult.RunStatus.Reporting, RunResult.RunStatus.Paused],
            ).exclude(pk=getattr(reuse_result, "pk", None)).first()
            if active_result:
                raise ValueError(f"套件正在执行中（执行记录 #{active_result.id}），请等待完成或先取消该任务。")

            if reuse_result is not None:
                result = RunResult.objects.select_for_update().get(pk=reuse_result.pk)
                if result.suite_id != locked_suite.id:
                    raise ValueError("执行记录不属于当前套件，无法重新执行。")
                if result.status in [RunResult.RunStatus.Ready, RunResult.RunStatus.Running, RunResult.RunStatus.Reporting, RunResult.RunStatus.Paused]:
                    raise ValueError("该执行记录正在执行中，请等待完成或先取消任务。")
                previous_path = str(result.path or "")
                result.project = environment.project
                result.path = "todo"
                result.environment_name = execution_environment_name
                result.executor_name = execution_executor_name
                result.status = RunResult.RunStatus.Ready
                result.is_pass = False
                result.native_report = {}
                result.cancel_requested = False
                result.timeout_seconds = locked_suite.execution_timeout
                result.started_at = None
                result.finished_at = None
                result.save(update_fields=[
                    "project", "path", "environment_name", "executor_name", "status", "is_pass",
                    "native_report", "cancel_requested", "timeout_seconds", "started_at", "finished_at",
                    "update_datetime",
                ])
                # 重新执行覆盖同一报告的投递状态，避免旧结果混入当前结果。
                result.notification_deliveries.all().delete()
            else:
                # 先进入队列，实际 pytest 执行由全局受控线程池调度。
                result = RunResult.objects.create(
                    suite=locked_suite, project=environment.project, path="todo",
                    environment_name=execution_environment_name,
                    executor_name=execution_executor_name,
                    status=RunResult.RunStatus.Ready, timeout_seconds=locked_suite.execution_timeout,
                )

        if previous_path:
            old_path = Path(previous_path)
            upload_root = Path("upload_yaml").resolve()
            try:
                if old_path.exists() and old_path.resolve().is_relative_to(upload_root):
                    shutil.rmtree(old_path)
            except OSError:
                # 历史执行文件清理失败不应阻塞本次重跑；新运行目录仍使用新的时间戳。
                pass

        path = Path("upload_yaml") / f"result_{result.id}_{time.time()}"  # 创建绝不重名的目录名
        path.mkdir(parents=True, exist_ok=True)  # 创建目录

        result.path = path
        result.save()

        # 2. 当前环境登录并生成运行期变量。Token 只存在于本次运行目录。
        environment_context = {}
        try:
            def get_context(target_environment):
                # 不同项目可存在同名环境（例如都叫 dev），缓存必须按具体环境区分。
                key = target_environment.id
                if key not in environment_context:
                    environment_context[key] = {
                        "base_url": target_environment.base_url,
                        "headers": target_environment.prepare_auth(path, str(target_environment.name)),
                    }
                return environment_context[key]

            if environment:
                get_context(environment)
        except Exception:
            result.status = result.RunStatus.Error
            result.save(update_fields=["status", "update_datetime"])
            raise

        # 项目变量作为本次套件执行的基础变量。套件执行环境所属项目优先，
        # 跨项目场景的同名变量不会覆盖套件主项目变量。
        project_ids = []
        for execution_item in self.ordered_execution_items():
            if execution_item.item_type == SuiteExecutionItem.ItemType.API:
                scenario = execution_item.scenario
                project_ids.extend([scenario.project_id, *scenario.projects.values_list("id", flat=True)])
            elif execution_item.ui_case:
                project_ids.append(execution_item.ui_case.project_id)
            elif execution_item.playwright_case:
                project_ids.append(execution_item.playwright_case.project_id)
        project_ids = [project_id for project_id in project_ids if project_id and project_id != environment.project_id]
        project_ids.append(environment.project_id)
        project_variables = ProjectVariable.values_for_projects(project_ids)

        # 3. 生成 yaml 和 excel 测试用例
        try:
            planned_scenarios = []
            execution_plan = []
            for execution_item in self.ordered_execution_items():
                if execution_item.item_type == SuiteExecutionItem.ItemType.API:
                    scenario = execution_item.scenario
                    def serialize_step(step):
                        if not step or not step.endpoint_id:
                            raise ValueError(f"场景「{scenario.name}」存在未选择接口的步骤。")
                        step_environment = Environment.objects.filter(
                            project_id=step.endpoint.project_id, name=execution_environment_name
                        ).first()
                        if not step_environment:
                            raise ValueError(
                                f"项目「{step.endpoint.project.name}」未配置名为「{execution_environment_name}」的执行环境。"
                            )
                        context = get_context(step_environment)
                        data = step.endpoint.to_yaml_data(
                            base_url=context["base_url"], auth_headers=context["headers"], override=step.request_override,
                        )
                        data = step.apply_request_target(data, context["base_url"])
                        data.update({
                            "test_name": step.name or step.endpoint.name, "scenario_id": scenario.id,
                            "scenario_name": scenario.name, "source_step_id": step.id,
                            "project_id": step.endpoint.project_id, "environment_name": execution_environment_name,
                            "epic": self.name, "feature": scenario.name,
                        })
                        data["extract"] = step.extract or {}
                        data["post_sql"] = step.post_sql or []
                        data["validate"] = step.validate or {}
                        data["polling"] = step.polling or {}
                        data["continue_on_failure"] = step.continue_on_failure
                        data["retry_on_failure"] = step.retry_on_failure
                        data["failure_retry_count"] = step.failure_retry_count
                        return data

                    def serialize_nodes(parent_branch=None):
                        nodes = ScenarioFlowNode.objects.filter(
                            scenario=scenario, parent_branch=parent_branch
                        ).select_related("step", "step__endpoint", "step__endpoint__project").order_by("order", "id")
                        payload = []
                        for node in nodes:
                            item = {"id": node.id, "node_type": node.node_type, "name": node.name,
                                    "order": node.order, "condition_logic": node.condition_logic}
                            if node.node_type == ScenarioFlowNode.NodeType.ENDPOINT:
                                item["case"] = serialize_step(node.step)
                            else:
                                item["branches"] = [
                                    {"id": branch.id, "name": branch.name, "order": branch.order,
                                     "conditions": branch.conditions or [],
                                     "nodes": serialize_nodes(branch)}
                                    for branch in node.branches.all().order_by("order", "id")
                                ]
                            payload.append(item)
                        return payload

                    def planned_steps_from(nodes):
                        values = []
                        for node in nodes:
                            if node["node_type"] == ScenarioFlowNode.NodeType.ENDPOINT:
                                case = node["case"]
                                values.append({"source_step_id": case.get("source_step_id"), "name": case["test_name"],
                                               "method": str(case["request"].get("method", "")).upper(),
                                               "url": case["request"].get("url", ""), "status": "pending", "passed": None})
                            else:
                                for branch in node.get("branches", []):
                                    values.extend(planned_steps_from(branch.get("nodes", [])))
                        return values

                    def report_flow_from(nodes):
                        """保存报告展示所需的轻量流程，不重复写入请求和响应正文。"""
                        values = []
                        for node in nodes:
                            if node["node_type"] == ScenarioFlowNode.NodeType.ENDPOINT:
                                values.append({
                                    "node_type": "endpoint",
                                    "node_id": node.get("id"),
                                    "order": node.get("order"),
                                    "source_step_id": (node.get("case") or {}).get("source_step_id"),
                                })
                                continue
                            values.append({
                                "node_type": "condition",
                                "node_id": node.get("id"),
                                "name": node.get("name") or "判断分支",
                                "order": node.get("order"),
                                "condition_logic": node.get("condition_logic") or "and",
                                "branches": [
                                    {
                                        "id": branch.get("id"),
                                        "name": branch.get("name") or "未命名分支",
                                        "order": branch.get("order"),
                                        "conditions": branch.get("conditions") or [],
                                        "nodes": report_flow_from(branch.get("nodes", [])),
                                    }
                                    for branch in node.get("branches", [])
                                ],
                            })
                        return values

                    flow_nodes = serialize_nodes()
                    planned_steps = planned_steps_from(flow_nodes)
                    if not planned_steps:
                        raise ValueError(f"场景「{scenario.name}」没有可执行步骤。")
                    flow_data = {"id": scenario.id, "name": scenario.name, "epic": self.name, "nodes": flow_nodes}
                    if any(node["node_type"] == ScenarioFlowNode.NodeType.CONDITION for node in flow_nodes):
                        execution_plan.append({"type": "api_flow", "case": flow_data})
                    else:
                        # 没有判断节点的历史场景继续维持“一接口一执行项”，保留既有
                        # pytest 用例与套件执行顺序；条件场景才使用流程执行器。
                        for node in flow_nodes:
                            case = node["case"]
                            for expanded_case in ddt(case) if case.get("parametrize") else [case]:
                                execution_plan.append({"type": "api", "case": expanded_case})
                    with open(path / f"scenario_{execution_item.order:06d}_{scenario.id}.yaml", "w", encoding="utf-8") as file:
                        yaml.safe_dump(flow_data, file, allow_unicode=True, sort_keys=False)
                    planned_scenarios.append({
                        "id": scenario.id, "name": scenario.name, "type": "api",
                        "execution_order": execution_item.order, "steps": planned_steps,
                        "flow_nodes": report_flow_from(flow_nodes),
                    })
                    continue

                if execution_item.item_type == SuiteExecutionItem.ItemType.PLAYWRIGHT_UI:
                    playwright_case = execution_item.playwright_case
                    if not playwright_case.enabled:
                        raise ValueError(f"Playwright 用例「{playwright_case.name}」已停用。")
                    pw_environment = Environment.objects.filter(
                        project_id=playwright_case.project_id, name=execution_environment_name
                    ).first()
                    if not pw_environment:
                        raise ValueError(
                            f"Playwright 用例项目「{playwright_case.project.name}」未配置名为「{execution_environment_name}」的执行环境。"
                        )
                    steps = list(playwright_case.steps.order_by("order", "id"))
                    if not steps:
                        raise ValueError(f"Playwright 用例「{playwright_case.name}」没有可执行步骤。")
                    pw_data = {
                        "id": playwright_case.id, "name": playwright_case.name,
                        "browser": playwright_case.browser, "run_mode": playwright_case.run_mode,
                        "default_timeout": playwright_case.default_timeout,
                        "viewport": playwright_case.viewport, "base_url": pw_environment.base_url,
                        "project_id": playwright_case.project_id,
                        "environment_name": execution_environment_name, "epic": self.name,
                        "steps": [
                            {
                                "id": step.id,
                                "name": playwright_step_display_name(step.action, step.target, step.value),
                                "action": step.action,
                                "tab_key": step.tab_key,
                                "target": step.target, "value": step.value,
                                "locator_mode": step.locator_mode, "fallback_type": step.fallback_type,
                                "fallback_value": step.fallback_value, "options": step.options,
                                "continue_on_failure": step.continue_on_failure,
                            }
                            for step in steps
                        ],
                    }
                    execution_plan.append({"type": "playwright_ui", "case": pw_data})
                    with open(path / f"playwright_case_{execution_item.order:06d}_{playwright_case.id}.yaml", "w", encoding="utf-8") as file:
                        yaml.safe_dump(pw_data, file, allow_unicode=True, sort_keys=False)
                    pw_tab_names = {
                        str(item.get("key")): str(item.get("name") or "")
                        for item in (playwright_case.tabs or []) if isinstance(item, dict)
                    }
                    pw_tabs = sorted(
                        [
                            {
                                "key": str(item.get("key") or "tab-1"),
                                "name": str(item.get("name") or "未命名 Tab"),
                                "order": int(item.get("order") or 0),
                            }
                            for item in (playwright_case.tabs or []) if isinstance(item, dict)
                        ],
                        key=lambda item: item["order"],
                    )
                    planned_scenarios.append({
                        "id": f"playwright-ui-{playwright_case.id}", "name": playwright_case.name,
                        "type": "playwright_ui", "browser": playwright_case.browser,
                        "run_mode": playwright_case.run_mode, "execution_order": execution_item.order,
                        "tabs": pw_tabs,
                        "steps": [
                            {"source_step_id": step.id,
                             "name": playwright_step_display_name(step.action, step.target, step.value),
                             "action": step.get_action_display(),
                             "action_key": step.action, "target": step.target, "tab_key": step.tab_key,
                             "tab_name": pw_tab_names.get(step.tab_key, ""),
                             "status": "pending", "passed": None}
                            for step in steps
                        ],
                    })
                    continue

                ui_case = execution_item.ui_case
                if not ui_case.enabled:
                    raise ValueError(f"UI 用例「{ui_case.name}」已停用。")
                ui_environment = Environment.objects.filter(
                    project_id=ui_case.project_id, name=execution_environment_name
                ).first()
                if not ui_environment:
                    raise ValueError(
                        f"UI 用例项目「{ui_case.project.name}」未配置名为「{execution_environment_name}」的执行环境。"
                    )
                steps = list(ui_case.steps.select_related("element").order_by("order", "id"))
                if not steps:
                    raise ValueError(f"UI 用例「{ui_case.name}」没有可执行步骤。")
                tabs = sorted(
                    [item for item in (ui_case.tabs or []) if isinstance(item, dict)],
                    key=lambda item: item.get("order", 0),
                )
                tab_names = {str(item.get("key")): str(item.get("name") or "") for item in tabs}
                ui_data = {
                    "id": ui_case.id, "name": ui_case.name,
                    "browser": ui_case.browser, "run_mode": ui_case.run_mode,
                    "tabs": tabs,
                    "base_url": ui_environment.base_url,
                    "project_id": ui_case.project_id,
                    "environment_name": execution_environment_name,
                    "epic": self.name,
                    "steps": [
                        {
                            "id": step.id,
                            "name": ui_step_display_name(step.action, step.element.name if step.element else "", step.value),
                            "action": step.action,
                            "tab_key": step.tab_key,
                            "tab_name": tab_names.get(step.tab_key, ""),
                            "by": step.element.by if step.element else None,
                            "locator": step.element.value if step.element else None,
                            "element_name": step.element.name if step.element else "",
                            "value": step.value, "options": step.options,
                            "continue_on_failure": step.continue_on_failure,
                        }
                        for step in steps
                    ],
                }
                execution_plan.append({"type": "ui", "case": ui_data})
                with open(path / f"ui_case_{execution_item.order:06d}_{ui_case.id}.yaml", "w", encoding="utf-8") as file:
                    yaml.safe_dump(ui_data, file, allow_unicode=True, sort_keys=False)
                planned_scenarios.append({
                    "id": f"ui-{ui_case.id}", "name": ui_case.name, "type": "ui",
                    "browser": ui_case.browser, "run_mode": ui_case.run_mode,
                    "tabs": tabs,
                    "execution_order": execution_item.order,
                    "steps": [
                        {
                            "source_step_id": step.id,
                            "name": ui_step_display_name(step.action, step.element.name if step.element else "", step.value),
                            "tab_key": step.tab_key,
                            "tab_name": tab_names.get(step.tab_key, ""),
                            "action": step.get_action_display(), "action_key": step.action,
                            "status": "pending", "passed": None,
                        }
                        for step in steps
                    ],
                })

            if not execution_plan:
                raise ValueError("套件没有可执行的接口场景或 UI 用例。")
            with open(path / "execution_plan.yaml", "w", encoding="utf-8") as file:
                yaml.safe_dump(execution_plan, file, allow_unicode=True, sort_keys=False)
            result.native_report = {
                "suite": self.name,
                "environment": execution_environment_name,
                "scenarios": planned_scenarios,
            }
            recalculate_native_report(result.native_report)
            result.save(update_fields=["native_report", "update_datetime"])
        except Exception:
            result.status = result.RunStatus.Error
            result.save(update_fields=["status", "update_datetime"])
            raise

        # 按实际优先级记录变量来源：项目参数 < 环境 Token < 模板参数。
        extract_path = path / "extract.yaml"
        environment_variables = {}
        if extract_path.exists():
            with extract_path.open(encoding="utf-8") as file:
                environment_variables = yaml.safe_load(file) or {}
        record_variable_resolution(path, "project", project_variables)
        record_variable_resolution(path, "environment_token", environment_variables,
                                   environment=execution_environment_name)
        record_variable_resolution(path, "template", initial_variables or {})
        result.native_report["variable_resolution"] = load_variable_resolution(path)
        result.save(update_fields=["native_report", "update_datetime"])

        # 环境认证覆盖同名项目默认值；模板/手工参数优先级最高。
        run_variables = {**project_variables, **environment_variables, **(initial_variables or {})}
        if run_variables:
            _merge_initial_variables(path, run_variables)

        # 4. 全局受控队列：超过并发上限的任务保持“准备开始”，等待空闲工作线程。
        submit_run(path, result.id, self.case_api_count(), self.case_ui_count() + self.case_playwright_count())

        return result

    @property
    def active_environment(self):
        return self.environment

    @property
    def base_url(self):
        """接口地址只从套件选择的执行环境中获取。"""
        if self.active_environment:
            return self.active_environment.base_url
        return ""


class SuiteScenario(models.Model):
    suite = models.ForeignKey(Suite, on_delete=models.CASCADE)
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE)
    order = models.PositiveIntegerField("执行顺序", default=1)
    continue_on_failure = models.BooleanField("失败后继续下一场景", default=False)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["suite", "scenario"], name="unique_suite_scenario"),
            models.UniqueConstraint(fields=["suite", "order"], name="unique_suite_scenario_order"),
        ]


class SuiteUiCase(models.Model):
    suite = models.ForeignKey(Suite, on_delete=models.CASCADE)
    ui_case = models.ForeignKey(UiCase, on_delete=models.CASCADE)
    order = models.PositiveIntegerField("执行顺序", default=1)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["suite", "ui_case"], name="unique_suite_ui_case"),
            models.UniqueConstraint(fields=["suite", "order"], name="unique_suite_ui_case_order"),
        ]


class SuitePlaywrightCase(models.Model):
    suite = models.ForeignKey(Suite, on_delete=models.CASCADE)
    playwright_case = models.ForeignKey(PlaywrightCase, on_delete=models.CASCADE)
    order = models.PositiveIntegerField("执行顺序", default=1)

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["suite", "playwright_case"], name="unique_suite_playwright_case"),
            models.UniqueConstraint(fields=["suite", "order"], name="unique_suite_playwright_case_order"),
        ]


class SuiteExecutionItem(models.Model):
    """套件的统一执行队列，允许接口场景和 UI 用例交错编排。"""

    class ItemType(models.TextChoices):
        API = "api", "接口场景"
        UI = "ui", "UI 用例"
        PLAYWRIGHT_UI = "playwright_ui", "Playwright 智能 UI"

    suite = models.ForeignKey(Suite, on_delete=models.CASCADE, related_name="execution_items")
    item_type = models.CharField("类型", max_length=16, choices=ItemType.choices)
    scenario = models.ForeignKey(Scenario, null=True, blank=True, on_delete=models.CASCADE)
    ui_case = models.ForeignKey(UiCase, null=True, blank=True, on_delete=models.CASCADE)
    playwright_case = models.ForeignKey(PlaywrightCase, null=True, blank=True, on_delete=models.CASCADE)
    order = models.PositiveIntegerField("执行顺序")

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["suite", "order"], name="unique_suite_execution_order"),
            models.UniqueConstraint(
                fields=["suite", "scenario"], condition=models.Q(scenario__isnull=False),
                name="unique_suite_execution_scenario",
            ),
            models.UniqueConstraint(
                fields=["suite", "ui_case"], condition=models.Q(ui_case__isnull=False),
                name="unique_suite_execution_ui_case",
            ),
            models.UniqueConstraint(
                fields=["suite", "playwright_case"], condition=models.Q(playwright_case__isnull=False),
                name="unique_suite_execution_playwright_case",
            ),
            models.CheckConstraint(
                check=(
                    models.Q(item_type="api", scenario__isnull=False, ui_case__isnull=True, playwright_case__isnull=True)
                    | models.Q(item_type="ui", scenario__isnull=True, ui_case__isnull=False, playwright_case__isnull=True)
                    | models.Q(item_type="playwright_ui", scenario__isnull=True, ui_case__isnull=True, playwright_case__isnull=False)
                ),
                name="suite_execution_item_matches_type",
            ),
        ]


class RunResult(models.Model):
    """执行结果"""

    objects: models.QuerySet
    # 新执行记录直接使用随机 10 位数字作为主键；迁移不会修改历史记录的 ID。
    id = models.PositiveBigIntegerField(primary_key=True, default=generate_execution_no, editable=False)

    class RunStatus(models.IntegerChoices):
        Init = 0, "初始化"
        Ready = 1, "准备开始"
        Running = 2, "正在执行"
        Reporting = 3, "正在正常报告"
        Done = 4, "执行完毕"
        Error = -1, "执行出错"
        Canceled = -2, "已取消"
        Paused = -3, "已暂停"

    suite = models.ForeignKey(Suite, on_delete=models.CASCADE)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    # 保存本次运行的环境快照，避免套件后续切换环境后历史记录跟着变化。
    environment_name = models.CharField("执行环境", max_length=16, blank=True)
    # 保存执行人名称快照，避免用户改名或删除后历史执行记录失去归属信息。
    executor_name = models.CharField("执行人", max_length=150, default="系统")

    path = models.CharField("用例路径", max_length=255)
    is_pass = models.BooleanField("测试通过", default=False)

    # 平台原生报告。按“场景 → 接口步骤”保存结构化执行信息。
    native_report = models.JSONField("原生执行报告", default=dict, blank=True)

    status = models.IntegerField(
        "执行状态", choices=RunStatus.choices, default=RunStatus.Init
    )

    cancel_requested = models.BooleanField("已请求取消", default=False)
    # pytest 子进程 PID 仅在运行期间使用，用于暂停/恢复本机执行器。
    run_process_id = models.PositiveIntegerField("执行进程 PID", null=True, blank=True)
    timeout_seconds = models.PositiveIntegerField("超时秒数", default=1800)
    started_at = models.DateTimeField("开始时间", null=True, blank=True)
    finished_at = models.DateTimeField("结束时间", null=True, blank=True)

    create_datetime = models.DateTimeField("创建时间", auto_now_add=True)
    update_datetime = models.DateTimeField("更新时间", auto_now=True)


class NotificationChannel(models.Model):
    class Platform(models.TextChoices):
        LARK = "lark", "飞书"
        WECOM = "wecom", "企业微信"
    projects = models.ManyToManyField(Project, related_name="notification_channels", verbose_name="关联项目")
    name = models.CharField("渠道名称", max_length=64)
    platform = models.CharField("平台", max_length=16, choices=Platform.choices)
    webhook_url = models.URLField("Webhook 地址", max_length=1024)
    enabled = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class WebhookReplayNonce(models.Model):
    """已通过鉴权的 Webhook Nonce，用数据库唯一约束保证多 Worker 防重放。"""

    suite = models.ForeignKey(Suite, on_delete=models.CASCADE, related_name="webhook_nonces")
    nonce_digest = models.CharField("Nonce 摘要", max_length=64)
    request_timestamp = models.BigIntegerField("请求时间戳")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["suite", "nonce_digest"], name="unique_suite_webhook_nonce"
            )
        ]
        indexes = [models.Index(fields=["created_at"], name="suite_hook_nonce_created_idx")]


class NotificationRule(models.Model):
    class Event(models.TextChoices):
        SUCCEEDED = "succeeded", "执行成功"
        FAILED = "failed", "执行失败"
        ALL = "all", "成功或失败"
    channel = models.ForeignKey(NotificationChannel, on_delete=models.CASCADE, related_name="rules")
    suite = models.ForeignKey(Suite, null=True, blank=True, on_delete=models.CASCADE, related_name="notification_rules")
    event = models.CharField("触发事件", max_length=16, choices=Event.choices)
    enabled = models.BooleanField("启用", default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class NotificationDelivery(models.Model):
    class Status(models.TextChoices):
        SENT = "sent", "已发送"
        FAILED = "failed", "发送失败"
    result = models.ForeignKey(RunResult, on_delete=models.CASCADE, related_name="notification_deliveries")
    channel = models.ForeignKey(NotificationChannel, on_delete=models.CASCADE, related_name="deliveries")
    rule = models.ForeignKey(NotificationRule, on_delete=models.SET_NULL, null=True, related_name="deliveries")
    event = models.CharField("触发事件", max_length=16)
    status = models.CharField("投递状态", max_length=16, choices=Status.choices)
    payload = models.JSONField("消息内容", default=dict, blank=True)
    response_code = models.IntegerField("响应码", null=True, blank=True)
    response_summary = models.CharField("响应摘要", max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
