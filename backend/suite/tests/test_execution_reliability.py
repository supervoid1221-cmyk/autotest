import os
import json
import subprocess
import yaml
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from case_api.models import Endpoint, Scenario, ScenarioBranch, ScenarioFlowNode, ScenarioStep
from case_app.executor import _merge_suite_run_result
from case_app.models import AppApplication, AppCase, AppDevice, AppExecutionNode, AppRun, AppStep, AppStepResult
from case_ui.models import Element, PlaywrightCase, PlaywrightScenarioFile, PlaywrightStep, UiCase, UiStep
from project.models import Environment, Project
from execution_control.models import ExecutionTask
from suite.models import RunResult, Suite, SuiteAppCase, SuiteExecutionItem, SuitePlaywrightCase, SuiteScenario, SuiteUiCase
from suite.serializers import RunResultSerializer, SuiteSerializer
from suite.tasks import _reconcile_process_result, _stop_process, run_by_cron
from suite.reporting import (
    finalize_unfinished_steps,
    merge_ui_runtime_results,
    recalculate_native_report,
    sanitize_variable_snapshot,
)


class ExecutionFixtureMixin:
    def setUp(self):
        self.user = User.objects.create_user(username="runner")
        self.project = Project.objects.create(name="接口项目", pm=self.user)
        self.environment = Environment.objects.create(
            project=self.project,
            name=Environment.Name.TEST,
            base_url="https://example.com",
        )
        self.suite = Suite.objects.create(name="回归套件", environment=self.environment)


class SuiteScenarioOrderingTests(ExecutionFixtureMixin, TestCase):
    def _create_scenario(self, name):
        scenario = Scenario.objects.create(project=self.project, name=name)
        scenario.projects.add(self.project)
        endpoint = Endpoint.objects.create(
            name=f"{name}接口",
            project=self.project,
            method="GET",
            url=f"/{name}",
        )
        ScenarioStep.objects.create(scenario=scenario, endpoint=endpoint, order=1)
        return scenario

    def test_yaml_file_is_smart_ui_execution_item_and_runs_from_saved_content(self):
        yaml_case = PlaywrightScenarioFile.objects.create(
            project=self.project, filename="batch-check.yaml", environment_name="Test",
            content=("测试场景:\n- 场景名称: 批量质量检测 场景ID: BATCH_CHECK 描述: 检测入口\n"
                     "  步骤:\n  - 打开页面：/login\n  - 点击：IP管理--批量质量检测\n  截图：true\n"
                     "- 场景名称: 查看结果 场景ID: CHECK_RESULT 描述: 检查页面\n"
                     "  步骤:\n  - 点击：查看结果\n"),
        )
        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(
            f"/api/suite/suite/{self.suite.pk}/sync-execution-items/",
            {"items": [{"type": "yaml_ui", "id": yaml_case.pk}]}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        item = SuiteExecutionItem.objects.get(suite=self.suite)
        self.assertEqual(item.yaml_case_id, yaml_case.pk)
        serialized = SuiteSerializer(self.suite).data
        self.assertEqual(serialized["execution_items"][0]["type"], "yaml_ui")
        self.assertEqual(serialized["case_playwright_count"], 1)
        self.assertEqual(serialized["ui_step_count"], 3)

        original_cwd = os.getcwd()
        with TemporaryDirectory() as directory, patch("suite.models.submit_run"):
            os.chdir(directory)
            try:
                result = self.suite.run()
                with open(Path(result.path) / "execution_plan.yaml", encoding="utf-8") as file:
                    plan = yaml.safe_load(file)
            finally:
                os.chdir(original_cwd)
        self.assertEqual([item["type"] for item in plan], ["yaml_ui_group"])
        self.assertEqual([case["name"] for case in plan[0]["cases"]], ["批量质量检测", "查看结果"])
        self.assertEqual(plan[0]["cases"][0]["steps"][1]["target"], "IP管理--批量质量检测")
        self.assertTrue(plan[0]["cases"][0]["steps"][1]["options"]["screenshot"])
        self.assertEqual([item["source_type"] for item in result.native_report["scenarios"]], ["yaml_ui", "yaml_ui"])
        self.assertEqual([item["name"] for item in result.native_report["scenarios"]], ["批量质量检测", "查看结果"])

    def test_run_generates_and_reports_scenarios_in_suite_order(self):
        first_created = self._create_scenario("后执行")
        second_created = self._create_scenario("先执行")
        SuiteScenario.objects.create(suite=self.suite, scenario=first_created, order=2)
        SuiteScenario.objects.create(suite=self.suite, scenario=second_created, order=1)

        original_cwd = os.getcwd()
        with TemporaryDirectory() as directory, patch("suite.models.submit_run") as submit_run:
            os.chdir(directory)
            try:
                result = self.suite.run()
                run_path = Path(result.path)
                filenames = sorted(path.name for path in run_path.glob("scenario_*.yaml"))
            finally:
                os.chdir(original_cwd)

        result.refresh_from_db()
        self.assertEqual(
            [item["name"] for item in result.native_report["scenarios"]],
            ["先执行", "后执行"],
        )
        self.assertEqual(
            filenames,
            [
                f"scenario_000001_{second_created.id}.yaml",
                f"scenario_000002_{first_created.id}.yaml",
            ],
        )
        first_report_flow = result.native_report["scenarios"][0]["flow_nodes"]
        self.assertEqual(first_report_flow[0]["node_type"], "endpoint")
        self.assertIsNotNone(first_report_flow[0]["source_step_id"])
        self.assertNotIn("response_body", first_report_flow[0])
        submit_run.assert_called_once()

    def test_rerun_reuses_existing_result_record(self):
        scenario = self._create_scenario("可重跑场景")
        SuiteScenario.objects.create(suite=self.suite, scenario=scenario, order=1)

        original_cwd = os.getcwd()
        with TemporaryDirectory() as directory, patch("suite.models.submit_run"):
            os.chdir(directory)
            try:
                result = self.suite.run()
                self.assertIn(
                    f"tenant_{self.suite.tenant.slug}_{self.suite.tenant_id}",
                    Path(result.path).parts,
                )
                previous_path = Path(result.path)
                (previous_path / "old-run.log").write_text("previous", encoding="utf-8")
                result.status = RunResult.RunStatus.Done
                result.is_pass = True
                result.native_report = {"old": True}
                result.save(update_fields=["status", "is_pass", "native_report", "update_datetime"])

                rerun_result = self.suite.run(reuse_result=result, executor_name="runner")
            finally:
                os.chdir(original_cwd)

        rerun_result.refresh_from_db()
        self.assertEqual(rerun_result.id, result.id)
        self.assertEqual(rerun_result.status, RunResult.RunStatus.Ready)
        self.assertFalse(rerun_result.is_pass)
        self.assertEqual(rerun_result.executor_name, "runner")
        self.assertNotEqual(Path(rerun_result.path), previous_path)
        self.assertFalse(previous_path.exists())

    def test_run_saves_executor_snapshot(self):
        scenario = self._create_scenario("执行人快照")
        SuiteScenario.objects.create(suite=self.suite, scenario=scenario, order=1)
        original_cwd = os.getcwd()
        with TemporaryDirectory() as directory, patch("suite.models.submit_run"):
            os.chdir(directory)
            try:
                result = self.suite.run(executor_name="runner")
            finally:
                os.chdir(original_cwd)

        self.assertEqual(result.executor_name, "runner")
        self.assertEqual(RunResultSerializer(result).data["executor_name"], "runner")
        self.assertEqual(RunResultSerializer(result).data["environment_name"], self.environment.name)

    def test_run_without_suite_environment_does_not_create_result(self):
        suite = Suite.objects.create(name="未配置环境套件", environment=None)
        before_count = RunResult.objects.count()

        with self.assertRaisesRegex(ValueError, "未配置执行环境"):
            suite.run()

        self.assertEqual(RunResult.objects.count(), before_count)

    def test_run_missing_cross_project_environment_does_not_create_result(self):
        other_project = Project.objects.create(name="缺少环境项目", pm=self.user)
        scenario = Scenario.objects.create(project=other_project, name="跨项目场景")
        scenario.projects.add(other_project)
        endpoint = Endpoint.objects.create(
            name="跨项目接口",
            project=other_project,
            method="GET",
            url="/cross-project",
        )
        ScenarioStep.objects.create(scenario=scenario, endpoint=endpoint, order=1)
        SuiteScenario.objects.create(suite=self.suite, scenario=scenario, order=1)
        before_count = RunResult.objects.count()

        with self.assertRaisesRegex(ValueError, "缺少环境项目"):
            self.suite.run()

        self.assertEqual(RunResult.objects.count(), before_count)

    def test_legacy_report_recovers_condition_at_current_flow_position(self):
        scenario = self._create_scenario("历史分支")
        condition = ScenarioFlowNode.objects.create(
            scenario=scenario,
            node_type=ScenarioFlowNode.NodeType.CONDITION,
            name="余额判断",
            order=2,
        )
        branch = ScenarioBranch.objects.create(
            condition_node=condition,
            name="余额充足",
            order=1,
            conditions=[{"source": "variable", "variable": "balance", "operator": "gt", "expected": 0}],
        )
        branch_endpoint = Endpoint.objects.create(
            name="提交订单",
            project=self.project,
            method="POST",
            url="/orders",
        )
        branch_step = ScenarioStep.objects.create(
            scenario=scenario,
            endpoint=branch_endpoint,
            name="提交订单",
            order=2,
        )
        branch_step.flow_node.parent_branch = branch
        branch_step.flow_node.order = 1
        branch_step.flow_node.save(update_fields=["parent_branch", "order"])
        result = RunResult.objects.create(
            suite=self.suite,
            project=self.project,
            environment_name=self.environment.name,
            path="upload_yaml/legacy-flow",
            native_report={
                "scenarios": [{"id": scenario.id, "name": scenario.name, "type": "api", "steps": []}],
            },
        )

        scenario_report = RunResultSerializer(result).data["native_report"]["scenarios"][0]

        self.assertEqual(scenario_report["flow_snapshot_source"], "current_scenario")
        self.assertEqual(
            [node["node_type"] for node in scenario_report["flow_nodes"]],
            ["endpoint", "condition"],
        )
        self.assertEqual(scenario_report["flow_nodes"][1]["branches"][0]["name"], "余额充足")
        self.assertEqual(
            scenario_report["flow_nodes"][1]["branches"][0]["nodes"][0]["source_step_id"],
            branch_step.id,
        )

    def test_cron_run_uses_system_executor(self):
        with patch.object(Suite, "run") as run:
            run_by_cron(self.suite.id)

        run.assert_called_once_with(executor_name="系统")

    def test_run_result_serialization_tolerates_legacy_step_without_endpoint(self):
        scenario = Scenario.objects.create(project=self.project, name="历史场景")
        scenario.projects.add(self.project)
        ScenarioStep.objects.create(scenario=scenario, endpoint=None, order=1)
        SuiteScenario.objects.create(suite=self.suite, scenario=scenario, order=1)
        result = RunResult.objects.create(
            suite=self.suite,
            project=self.project,
            environment_name=self.environment.name,
            path="upload_yaml/legacy",
        )

        data = RunResultSerializer(result).data

        self.assertEqual(data["project_names"], self.project.name)

    def test_suite_run_rejects_legacy_step_without_endpoint_with_clear_error(self):
        scenario = Scenario.objects.create(project=self.project, name="历史场景")
        scenario.projects.add(self.project)
        ScenarioStep.objects.create(scenario=scenario, endpoint=None, order=1)
        SuiteScenario.objects.create(suite=self.suite, scenario=scenario, order=1)

        # 「存在未选择接口的步骤」这条校验发生在运行目录创建之后
        # （suite/models.py 第 3 步），所以这里必须切到临时目录，
        # 否则每次跑测试都会在真实仓库的 upload_yaml/ 下留一个租户目录。
        original_cwd = os.getcwd()
        with TemporaryDirectory() as directory:
            os.chdir(directory)
            try:
                with self.assertRaisesRegex(ValueError, "存在未选择接口的步骤"):
                    self.suite.run()
            finally:
                os.chdir(original_cwd)


class SuiteUiExecutionPlanningTests(ExecutionFixtureMixin, TestCase):
    def _create_app_case(self):
        application = AppApplication.objects.create(
            project=self.project, name="测试 App", package_name="com.example.app",
        )
        node = AppExecutionNode.objects.create(project=self.project, name="本地 Appium")
        device = AppDevice.objects.create(
            project=self.project, node=node, name="Pixel 5", udid="emulator-5554",
            state=AppDevice.State.ONLINE,
        )
        case = AppCase.objects.create(
            project=self.project, application=application, default_device=device, name="App 登录",
        )
        step = AppStep.objects.create(case=case, order=1, action="launch")
        return case, step

    def test_sync_execution_items_accepts_app_case(self):
        app_case, _ = self._create_app_case()
        client = APIClient()
        client.force_authenticate(self.user)

        response = client.post(
            f"/api/suite/suite/{self.suite.id}/sync-execution-items/",
            {"items": [{"type": "app", "id": app_case.id}]}, format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["execution_items"][0]["type"], "app")
        self.assertEqual(response.data["app_cases"], [app_case.id])
        self.assertEqual(response.data["case_app_count"], 1)

    def test_app_case_is_written_to_suite_execution_plan_and_report(self):
        app_case, step = self._create_app_case()
        SuiteAppCase.objects.create(suite=self.suite, app_case=app_case, order=1)

        original_cwd = os.getcwd()
        with TemporaryDirectory() as directory, patch("suite.models.submit_run") as submit_run:
            os.chdir(directory)
            try:
                result = self.suite.run()
                with open(Path(result.path) / "execution_plan.yaml", encoding="utf-8") as file:
                    plan = yaml.safe_load(file)
            finally:
                os.chdir(original_cwd)

        result.refresh_from_db()
        self.assertEqual(plan[0]["type"], "app")
        self.assertEqual(plan[0]["case"]["device_name"], "Pixel 5")
        self.assertEqual(result.native_report["scenarios"][0]["type"], "app")
        self.assertEqual(result.native_report["scenarios"][0]["steps"][0]["source_step_id"], step.id)
        submit_run.assert_called_once_with(Path(result.path), result.id, 0, 1)

    def test_app_step_results_are_merged_into_suite_report(self):
        app_case, step = self._create_app_case()
        result = RunResult.objects.create(
            suite=self.suite, project=self.project, environment_name=self.environment.name,
            path="todo", native_report={
                "scenarios": [{
                    "id": f"app-{app_case.id}", "name": app_case.name, "type": "app",
                    "steps": [{"source_step_id": step.id, "status": "pending", "passed": None}],
                }],
            },
        )
        app_run = AppRun.objects.create(
            case=app_case, project=self.project, application=app_case.application,
            device=app_case.default_device, status=AppRun.Status.PASSED,
            progress=100, summary={"total": 1, "passed": 1, "failed": 0},
        )
        AppStepResult.objects.create(
            run=app_run, step=step, order=1, action=step.action, name="启动应用",
            status="passed", duration_ms=123,
            detail={
                "value": "13800138000", "value_masked": False,
                "element_name": "手机号", "page_name": "登录页",
                "locator_type": "id", "locator_value": "com.example:id/mobile",
            },
        )

        with patch.dict(os.environ, {"PLATFORM_RUN_RESULT_ID": str(result.id)}):
            _merge_suite_run_result(app_run)

        result.refresh_from_db()
        merged = result.native_report["scenarios"][0]
        self.assertEqual(merged["app_run_id"], app_run.id)
        self.assertTrue(merged["steps"][0]["passed"])
        self.assertEqual(merged["steps"][0]["duration_ms"], 123)
        self.assertEqual(merged["steps"][0]["detail"]["value"], "13800138000")
        self.assertEqual(merged["steps"][0]["element_name"], "手机号")
        self.assertEqual(merged["steps"][0]["locator"], "com.example:id/mobile")

    def test_suite_child_app_run_does_not_create_duplicate_execution_task(self):
        app_case, _ = self._create_app_case()
        result = RunResult.objects.create(
            suite=self.suite, project=self.project, environment_name=self.environment.name,
            path="todo",
        )

        app_run = AppRun.objects.create(
            case=app_case, project=self.project, application=app_case.application,
            device=app_case.default_device,
            options={"suite_result_id": str(result.id)},
        )

        self.assertFalse(ExecutionTask.objects.filter(
            source_type=ExecutionTask.SourceType.APP,
            source_id=app_run.id,
        ).exists())
        self.assertTrue(ExecutionTask.objects.filter(
            source_type=ExecutionTask.SourceType.SUITE,
            source_id=result.id,
        ).exists())

    def test_suite_and_result_project_names_follow_actual_ui_case_project(self):
        actual_project = Project.objects.create(name="前台项目", pm=self.user)
        ui_case = UiCase.objects.create(name="跨项目 UI", project=actual_project)
        SuiteUiCase.objects.create(suite=self.suite, ui_case=ui_case, order=1)
        result = RunResult.objects.create(
            suite=self.suite,
            project=self.project,
            environment_name=self.environment.name,
            path="upload_yaml/cross-project-ui",
        )

        suite_data = SuiteSerializer(self.suite).data
        result_data = RunResultSerializer(result).data

        self.assertEqual(suite_data["project_name"], actual_project.name)
        self.assertEqual(result_data["project_name"], actual_project.name)
        self.assertEqual(result_data["project_names"], actual_project.name)

    def test_suite_list_ui_count_includes_playwright_cases(self):
        ui_case = UiCase.objects.create(name="传统 UI", project=self.project)
        playwright_case = PlaywrightCase.objects.create(name="智能 UI", project=self.project)
        SuiteUiCase.objects.create(suite=self.suite, ui_case=ui_case, order=1)
        SuitePlaywrightCase.objects.create(
            suite=self.suite, playwright_case=playwright_case, order=1,
        )

        data = SuiteSerializer(self.suite).data

        self.assertEqual(data["case_ui_count"], 2)
        self.assertEqual(data["case_playwright_count"], 1)

    def test_suite_execution_timeout_has_backend_bounds(self):
        low = SuiteSerializer(self.suite, data={"execution_timeout": 29}, partial=True)
        high = SuiteSerializer(self.suite, data={"execution_timeout": 86401}, partial=True)
        valid = SuiteSerializer(self.suite, data={"execution_timeout": 86400}, partial=True)

        self.assertFalse(low.is_valid())
        self.assertFalse(high.is_valid())
        self.assertTrue(valid.is_valid(), valid.errors)

    def test_scope_step_counts_follow_selected_enabled_cases(self):
        self.assertEqual(SuiteSerializer(self.suite).data["ui_step_count"], 0)
        self.assertEqual(SuiteSerializer(self.suite).data["app_step_count"], 0)
        items = []
        for case_model, step_model, step_fk, item_type in (
            (UiCase, UiStep, "ui_case", "ui"),
            (PlaywrightCase, PlaywrightStep, "case", "playwright_ui"),
            (AppCase, AppStep, "case", "app"),
        ):
            extra = {}
            if item_type == "app":
                extra["application"] = AppApplication.objects.create(
                    project=self.project, name="步骤统计 App", package_name="com.example.count",
                )
            # 两个有步骤的用例、空用例、停用用例、未选用例。
            for index, (enabled, count, selected) in enumerate(
                [(True, 2, True), (True, 3, True), (True, 0, True),
                 (False, 4, True), (True, 5, False)]
            ):
                case = case_model.objects.create(
                    project=self.project, name=f"{item_type}-{index}", enabled=enabled, **extra,
                )
                for order in range(1, count + 1):
                    step_model.objects.create(**{step_fk: case}, order=order, action="wait")
                if selected:
                    items.append({"type": item_type, "id": case.id})

        scenario = SuiteScenarioOrderingTests._create_scenario(self, "统计 API")
        items.append({"type": "api", "id": scenario.id})
        self.suite.sync_execution_items(items)
        data = SuiteSerializer(self.suite).data
        self.assertEqual(data["ui_step_count"], 10)
        self.assertEqual(data["app_step_count"], 5)
        self.assertEqual(data["case_ui_count"], 6)
        self.assertEqual(data["case_app_count"], 3)
        self.assertEqual(data["case_api_count"], 1)

        ui_case_id = items[0]["id"]
        UiStep.objects.create(ui_case_id=ui_case_id, order=3, action="wait")
        self.assertEqual(SuiteSerializer(self.suite).data["ui_step_count"], 11)
        app_case_id = next(item["id"] for item in items if item["type"] == "app")
        AppStep.objects.filter(case_id=app_case_id, order=1).delete()
        self.assertEqual(SuiteSerializer(self.suite).data["app_step_count"], 4)
        self.suite.sync_execution_items([])
        data = SuiteSerializer(self.suite).data
        self.assertEqual(data["ui_step_count"], 0)
        self.assertEqual(data["app_step_count"], 0)

    def test_sync_execution_items_api_persists_mixed_order(self):
        scenario = SuiteScenarioOrderingTests._create_scenario(self, "创建订单")
        ui_case = UiCase.objects.create(name="校验订单页面", project=self.project)
        UiStep.objects.create(ui_case=ui_case, order=1, action="goto", value="/orders")
        client = APIClient()
        client.force_authenticate(self.user)

        response = client.post(
            f"/api/suite/suite/{self.suite.id}/sync-execution-items/",
            {"items": [{"type": "ui", "id": ui_case.id}, {"type": "api", "id": scenario.id}]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [(item.item_type, item.order) for item in self.suite.ordered_execution_items()],
            [("ui", 1), ("api", 2)],
        )
        self.assertEqual(
            [(item["type"], item["id"]) for item in response.data["execution_items"]],
            [("ui", ui_case.id), ("api", scenario.id)],
        )

    def test_mixed_execution_items_generate_one_strictly_ordered_plan(self):
        first_api = SuiteScenarioOrderingTests._create_scenario(self, "登录鉴权")
        second_api = SuiteScenarioOrderingTests._create_scenario(self, "查询余额")
        ui_case = UiCase.objects.create(name="后台登录", project=self.project)
        UiStep.objects.create(ui_case=ui_case, order=1, action="goto", value="/login")
        self.suite.sync_execution_items([
            {"type": "api", "id": first_api.id},
            {"type": "ui", "id": ui_case.id},
            {"type": "api", "id": second_api.id},
        ])

        original_cwd = os.getcwd()
        with TemporaryDirectory() as directory, patch("suite.models.submit_run"):
            os.chdir(directory)
            try:
                result = self.suite.run()
                with open(Path(result.path) / "execution_plan.yaml", encoding="utf-8") as file:
                    plan = yaml.safe_load(file)
            finally:
                os.chdir(original_cwd)

        result.refresh_from_db()
        self.assertEqual([item["type"] for item in plan], ["api", "ui", "api"])
        self.assertEqual(
            [item["name"] for item in result.native_report["scenarios"]],
            ["登录鉴权", "后台登录", "查询余额"],
        )
        self.assertEqual(
            [(item.item_type, item.order) for item in self.suite.ordered_execution_items()],
            [("api", 1), ("ui", 2), ("api", 3)],
        )

    def test_run_generates_ui_yaml_and_native_report_after_api_scenarios(self):
        element = Element.objects.create(
            name="登录按钮", project=self.project, by="XPATH", value="//button[@type='submit']"
        )
        ui_case = UiCase.objects.create(
            name="后台登录", project=self.project, run_mode=UiCase.RunMode.HEADED,
            tabs=[{"key": "login", "name": "登录页", "order": 1}],
        )
        UiStep.objects.create(
            ui_case=ui_case, tab_key="login", order=1,
            action="goto", value="/login",
        )
        click_step = UiStep.objects.create(
            ui_case=ui_case, tab_key="login", order=2,
            action="click", element=element,
        )
        SuiteUiCase.objects.create(suite=self.suite, ui_case=ui_case, order=1)

        original_cwd = os.getcwd()
        with TemporaryDirectory() as directory, patch("suite.models.submit_run") as submit_run:
            os.chdir(directory)
            try:
                result = self.suite.run()
                run_path = Path(result.path)
                ui_files = list(run_path.glob("ui_case_*.yaml"))
                with open(ui_files[0], encoding="utf-8") as file:
                    generated_ui_case = yaml.safe_load(file)
            finally:
                os.chdir(original_cwd)

        result.refresh_from_db()
        self.assertEqual(len(ui_files), 1)
        self.assertEqual(generated_ui_case["browser"], "chrome")
        self.assertEqual(generated_ui_case["run_mode"], "headed")
        self.assertEqual(generated_ui_case["tabs"][0]["name"], "登录页")
        self.assertEqual(generated_ui_case["steps"][1]["tab_key"], "login")
        self.assertEqual(generated_ui_case["steps"][1]["tab_name"], "登录页")
        self.assertEqual(result.native_report["scenarios"][0]["id"], f"ui-{ui_case.id}")
        self.assertEqual(result.native_report["scenarios"][0]["type"], "ui")
        self.assertEqual(result.native_report["scenarios"][0]["run_mode"], "headed")
        self.assertEqual(result.native_report["scenarios"][0]["steps"][1]["tab_name"], "登录页")
        self.assertEqual(result.native_report["scenarios"][0]["steps"][1]["source_step_id"], click_step.id)
        self.assertEqual(result.native_report["summary"]["total"], 2)
        submit_run.assert_called_once_with(Path(result.path), result.id, 0, 1)

    def test_sync_ui_cases_preserves_submitted_order(self):
        first = UiCase.objects.create(name="先创建", project=self.project)
        second = UiCase.objects.create(name="后创建", project=self.project)
        self.suite.sync_ui_cases([second.id, first.id])
        self.assertEqual(
            list(self.suite.ordered_ui_case_links().values_list("ui_case_id", flat=True)),
            [second.id, first.id],
        )


class ProcessResultReconciliationTests(ExecutionFixtureMixin, TestCase):
    def _result(self, status):
        return RunResult.objects.create(
            suite=self.suite,
            project=self.project,
            environment_name=self.environment.name,
            path="todo",
            status=status,
        )

    @patch("suite.notifications.notify_execution_result")
    def test_nonzero_child_exit_marks_running_result_error(self, notify):
        result = self._result(RunResult.RunStatus.Running)
        _reconcile_process_result(result, SimpleNamespace(returncode=1))
        result.refresh_from_db()
        self.assertEqual(result.status, RunResult.RunStatus.Error)
        self.assertFalse(result.is_pass)
        self.assertIsNotNone(result.finished_at)
        notify.assert_called_once_with(result.id)

    @patch("suite.notifications.notify_execution_result")
    def test_zero_exit_still_marks_unfinished_result_error(self, notify):
        result = self._result(RunResult.RunStatus.Reporting)
        _reconcile_process_result(result, SimpleNamespace(returncode=0))
        result.refresh_from_db()
        self.assertEqual(result.status, RunResult.RunStatus.Error)
        notify.assert_called_once_with(result.id)

    @patch("suite.notifications.notify_execution_result")
    def test_abnormal_exit_does_not_overwrite_child_final_status(self, notify):
        result = self._result(RunResult.RunStatus.Done)
        result.is_pass = True
        result.save(update_fields=["is_pass"])
        _reconcile_process_result(result, SimpleNamespace(returncode=1))
        result.refresh_from_db()
        self.assertEqual(result.status, RunResult.RunStatus.Done)
        self.assertTrue(result.is_pass)
        notify.assert_not_called()

    @patch("suite.notifications.notify_execution_result")
    def test_init_result_is_closed_when_runner_fails_before_start(self, notify):
        result = self._result(RunResult.RunStatus.Init)
        _reconcile_process_result(result, None, execution_error=RuntimeError("启动失败"))
        result.refresh_from_db()
        self.assertEqual(result.status, RunResult.RunStatus.Error)
        self.assertFalse(result.is_pass)
        self.assertIsNotNone(result.finished_at)
        notify.assert_called_once_with(result.id)

    @patch("suite.notifications.notify_execution_result")
    def test_reconciliation_is_idempotent_for_terminal_result(self, notify):
        result = self._result(RunResult.RunStatus.Done)
        result.is_pass = True
        result.finished_at = timezone.now()
        result.save(update_fields=["is_pass", "finished_at"])
        _reconcile_process_result(result, None, execution_error=RuntimeError("late error"))
        result.refresh_from_db()
        self.assertEqual(result.status, RunResult.RunStatus.Done)
        self.assertTrue(result.is_pass)
        notify.assert_not_called()

    @patch("suite.tasks.os.killpg")
    @patch("suite.tasks.os.getpgid", return_value=13579)
    def test_stop_process_resumes_group_then_forces_kill_after_grace(self, getpgid, killpg):
        process = MagicMock(pid=24680)
        process.poll.return_value = None
        process.wait.side_effect = [subprocess.TimeoutExpired("runner", 5), 0]

        _stop_process(process, resume=True)

        self.assertEqual(
            [call.args for call in killpg.call_args_list],
            [(13579, __import__("signal").SIGCONT),
             (13579, __import__("signal").SIGTERM),
             (13579, __import__("signal").SIGKILL)],
        )
        self.assertEqual(process.wait.call_count, 2)


class NativeReportStateTests(TestCase):
    def test_merge_playwright_runtime_snapshot_exposes_running_steps(self):
        report = {
            "scenarios": [{
                "id": "playwright-ui-5",
                "name": "智能登录",
                "type": "playwright_ui",
                "steps": [
                    {"source_step_id": 11, "status": "pending", "tab_key": "login"},
                    {"source_step_id": 12, "status": "pending", "tab_key": "home"},
                ],
            }],
        }
        runtime = {
            "case_id": 5,
            "engine": "playwright",
            "steps": [
                {"id": 11, "status": "passed", "passed": True, "duration_ms": 20},
                {"id": 12, "status": "running", "started_at": "2026-08-22T12:00:00+08:00"},
            ],
        }
        with TemporaryDirectory() as directory:
            Path(directory, "playwright_native_result_5.json").write_text(
                json.dumps(runtime), encoding="utf-8",
            )
            merged = merge_ui_runtime_results(report, directory)

        self.assertEqual(merged["scenarios"][0]["steps"][0]["status"], "passed")
        self.assertEqual(merged["scenarios"][0]["steps"][1]["status"], "running")
        self.assertEqual(merged["scenarios"][0]["steps"][1]["tab_key"], "home")
        self.assertEqual(merged["summary"]["passed"], 1)
        self.assertEqual(merged["summary"]["running"], 1)


class RunResultProgressTests(ExecutionFixtureMixin, TestCase):
    @patch("suite.views.os.kill")
    def test_pause_action_toggles_running_process(self, kill):
        client = APIClient()
        client.force_authenticate(self.user)
        result = RunResult.objects.create(
            suite=self.suite,
            project=self.project,
            environment_name=self.environment.name,
            path="todo",
            status=RunResult.RunStatus.Running,
            run_process_id=24680,
        )

        paused = client.post(f"/api/suite/run_result/{result.id}/pause/")
        self.assertEqual(paused.status_code, 200)
        result.refresh_from_db()
        self.assertEqual(result.status, RunResult.RunStatus.Paused)
        kill.assert_called_once_with(24680, __import__("signal").SIGSTOP)

        resumed = client.post(f"/api/suite/run_result/{result.id}/pause/")
        self.assertEqual(resumed.status_code, 200)
        result.refresh_from_db()
        self.assertEqual(result.status, RunResult.RunStatus.Running)
        self.assertEqual(kill.call_args_list[-1].args, (24680, __import__("signal").SIGCONT))

    def test_progress_returns_live_ui_snapshot_without_waiting_for_database_finalize(self):
        client = APIClient()
        client.force_authenticate(self.user)
        report = {
            "scenarios": [{
                "id": "playwright-ui-5",
                "name": "智能登录",
                "type": "playwright_ui",
                "steps": [
                    {"source_step_id": 11, "status": "pending"},
                    {"source_step_id": 12, "status": "pending"},
                ],
            }],
        }
        with TemporaryDirectory() as directory:
            result = RunResult.objects.create(
                suite=self.suite,
                project=self.project,
                environment_name=self.environment.name,
                path=directory,
                status=RunResult.RunStatus.Running,
                native_report=report,
            )
            Path(directory, "playwright_native_result_5.json").write_text(
                json.dumps({
                    "case_id": 5,
                    "engine": "playwright",
                    "steps": [
                        {"id": 11, "status": "passed", "passed": True},
                        {"id": 12, "status": "running"},
                    ],
                }),
                encoding="utf-8",
            )

            response = client.get(f"/api/suite/run_result/{result.id}/progress/")

        self.assertEqual(response.status_code, 200)
        live_steps = response.data["result"]["native_report"]["scenarios"][0]["steps"]
        self.assertEqual([item["status"] for item in live_steps], ["passed", "running"])
        result.refresh_from_db()
        self.assertEqual(
            [item["status"] for item in result.native_report["scenarios"][0]["steps"]],
            ["pending", "pending"],
        )

    def test_finalize_unfinished_steps_marks_skipped_and_recalculates_groups(self):
        report = {
            "scenarios": [
                {
                    "id": "ui-1", "name": "登录", "type": "ui",
                    "steps": [
                        {"name": "打开页面", "status": "passed", "duration_ms": 12},
                        {"name": "点击登录", "status": "failed", "duration_ms": 8},
                        {"name": "进入首页", "status": "pending"},
                    ],
                },
                {
                    "id": 2, "name": "接口场景", "type": "api",
                    "steps": [{"name": "查询", "status": "running"}],
                },
            ]
        }
        finalized = finalize_unfinished_steps(report, "任务中断", "2026-08-16T12:00:00+08:00")
        self.assertEqual(finalized["scenarios"][0]["steps"][2]["status"], "skipped")
        self.assertEqual(finalized["scenarios"][1]["steps"][0]["status"], "skipped")
        self.assertEqual(finalized["scenarios"][0]["status"], "failed")
        self.assertEqual(finalized["scenarios"][1]["status"], "skipped")
        self.assertEqual(finalized["summary"]["skipped"], 2)
        self.assertEqual(finalized["summary"]["pending"], 0)
        self.assertEqual(finalized["summary"]["running"], 0)

    def test_recalculate_report_exposes_completed_count(self):
        report = {"scenarios": [{"steps": [
            {"status": "passed"}, {"status": "failed"},
            {"status": "skipped"}, {"status": "pending"},
        ]}]}
        recalculate_native_report(report)
        self.assertEqual(report["summary"]["total"], 4)
        self.assertEqual(report["summary"]["completed"], 3)

    def test_variable_snapshot_masks_sensitive_values_and_keeps_nested_data(self):
        snapshot = sanitize_variable_snapshot({
            "tenant_id": 100,
            "token": "secret-token",
            "profile": {"name": "tester", "password": "secret-password"},
            "items": [1, {"api_key": "secret-key"}],
        })
        self.assertEqual(snapshot["tenant_id"], 100)
        self.assertEqual(snapshot["token"], "***")
        self.assertEqual(snapshot["profile"]["name"], "tester")
        self.assertEqual(snapshot["profile"]["password"], "***")
        self.assertEqual(snapshot["items"][1]["api_key"], "***")
