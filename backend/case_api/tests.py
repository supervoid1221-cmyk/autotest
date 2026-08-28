from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from types import SimpleNamespace

from .flow import execute_flow
from .models import Endpoint, Scenario, ScenarioFlowNode, ScenarioStep
from project.models import Environment, Project


class ScenarioFlowExecutionTests(SimpleTestCase):
    def test_first_matching_branch_runs_then_returns_to_main_flow(self):
        called = []
        nodes = [
            {"id": 1, "node_type": "endpoint", "order": 1, "step": {"id": 11}, "label": "查询订单"},
            {"id": 2, "node_type": "condition", "name": "订单状态", "order": 2, "condition_logic": "and", "branches": [
                {"id": 21, "name": "成功", "order": 1, "conditions": [{"source": "step", "step_id": 11, "path": "$.data.status", "operator": "equals", "expected": "SUCCESS"}], "nodes": [
                    {"id": 3, "node_type": "endpoint", "order": 1, "step": {"id": 12}, "label": "成功校验"},
                ]},
                {"id": 22, "name": "失败", "order": 2, "conditions": [{"source": "step", "step_id": 11, "path": "$.data.status", "operator": "equals", "expected": "FAILED"}], "nodes": [
                    {"id": 4, "node_type": "endpoint", "order": 1, "step": {"id": 13}, "label": "失败处理"},
                ]},
            ]},
            {"id": 5, "node_type": "endpoint", "order": 3, "step": {"id": 14}, "label": "后续接口"},
        ]

        def run_endpoint(node):
            step_id = node["step"]["id"]
            called.append(step_id)
            return {"step_id": step_id, "passed": True, "response_json": {"data": {"status": "SUCCESS"}}}

        result = execute_flow(nodes, {}, run_endpoint)

        self.assertTrue(result["passed"])
        self.assertEqual(called, [11, 12, 14])
        self.assertEqual(result["decisions"][0]["selected_branch_name"], "成功")
        skipped = [item["step_id"] for item in result["results"] if item.get("skipped")]
        self.assertEqual(skipped, [13])

    def test_no_matching_branch_stops_flow_and_skips_branch_steps(self):
        nodes = [{"id": 1, "node_type": "condition", "order": 1, "branches": [
            {"id": 2, "name": "不命中", "order": 1, "conditions": [{"source": "variable", "variable": "status", "operator": "equals", "expected": "SUCCESS"}], "nodes": [{"id": 3, "node_type": "endpoint", "order": 1, "step": {"id": 12}}]},
        ]}]
        result = execute_flow(nodes, {"status": "FAILED"}, lambda node: {"passed": True})
        self.assertFalse(result["passed"])
        self.assertTrue(result["stopped"])
        self.assertIsNone(result["decisions"][0]["selected_branch_name"])
        self.assertEqual(result["results"][0]["skip_reason"], "没有满足条件的分支。")

    def test_model_step_uses_continue_on_failure_flag(self):
        step = SimpleNamespace(id=99, continue_on_failure=True)
        result = execute_flow(
            [{"id": 1, "node_type": "endpoint", "order": 1, "step": step}], {},
            lambda node: {"step_id": 99, "passed": False, "response_json": {}},
        )
        self.assertTrue(result["passed"] is False)
        self.assertFalse(result["stopped"])

    def test_failed_step_continues_by_default(self):
        called = []
        nodes = [
            {"id": 1, "node_type": "endpoint", "order": 1, "step": {"id": 11}},
            {"id": 2, "node_type": "endpoint", "order": 2, "step": {"id": 12}},
        ]

        def run_endpoint(node):
            step_id = node["step"]["id"]
            called.append(step_id)
            return {"step_id": step_id, "passed": step_id != 11, "response_json": {}}

        result = execute_flow(nodes, {}, run_endpoint)

        self.assertEqual(called, [11, 12])
        self.assertFalse(result["passed"])
        self.assertFalse(result["stopped"])

    def test_failed_step_stops_when_continue_is_explicitly_disabled(self):
        called = []
        nodes = [
            {"id": 1, "node_type": "endpoint", "order": 1, "step": {"id": 11, "continue_on_failure": False}},
            {"id": 2, "node_type": "endpoint", "order": 2, "step": {"id": 12}},
        ]

        def run_endpoint(node):
            step_id = node["step"]["id"]
            called.append(step_id)
            return {"step_id": step_id, "passed": False, "response_json": {}}

        result = execute_flow(nodes, {}, run_endpoint)

        self.assertEqual(called, [11])
        self.assertTrue(result["stopped"])
        self.assertTrue(result["results"][1]["skipped"])


class ScenarioStepRequestTargetTests(SimpleTestCase):
    def test_applies_method_and_relative_url_overrides(self):
        step = ScenarioStep(request_method="post", request_url="/api/v2/deposit/list")
        case_data = {"request": {"method": "GET", "url": "https://old.example/list"}}

        result = step.apply_request_target(case_data, "https://api.example.com/")

        self.assertEqual(result["request"]["method"], "POST")
        self.assertEqual(result["request"]["url"], "https://api.example.com/api/v2/deposit/list")

    def test_keeps_endpoint_defaults_without_overrides(self):
        step = ScenarioStep(request_method="", request_url="")
        case_data = {"request": {"method": "GET", "url": "https://api.example.com/default"}}

        result = step.apply_request_target(case_data, "https://api.example.com")

        self.assertEqual(result["request"], case_data["request"])

    def test_uses_absolute_override_url_directly(self):
        step = ScenarioStep(request_method="PATCH", request_url="https://other.example/update")
        case_data = {"request": {"method": "GET", "url": "https://api.example.com/default"}}

        result = step.apply_request_target(case_data, "https://api.example.com")

        self.assertEqual(result["request"]["url"], "https://other.example/update")


class EndpointRunAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser("endpoint-runner", "runner@example.com", "pass")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.project = Project.objects.create(name="接口调试项目", intro="", pm=self.user)
        self.environment = Environment.objects.create(
            project=self.project,
            name="Dev",
            base_url="https://api.example.com",
        )
        self.endpoint = Endpoint.objects.create(
            project=self.project,
            name="查询余额",
            method="GET",
            url="/wallet",
            headers={},
            params={},
            data={},
            json={},
            cookies={},
        )

    def test_create_endpoint_and_scenario_record_creator(self):
        endpoint_response = self.client.post(
            "/api/case_api/endpoint/",
            {
                "project": self.project.id, "name": "创建人接口",
                "method": "GET", "url": "/creator",
            },
            format="json",
        )
        scenario_response = self.client.post(
            "/api/case_api/scenario/",
            {"projects": [self.project.id], "name": "创建人场景", "description": ""},
            format="json",
        )

        self.assertEqual(endpoint_response.status_code, 201, endpoint_response.data)
        self.assertEqual(scenario_response.status_code, 201, scenario_response.data)
        endpoint = Endpoint.objects.get(pk=endpoint_response.data["id"])
        scenario = Scenario.objects.get(pk=scenario_response.data["id"])
        self.assertEqual(endpoint.created_by, self.user)
        self.assertEqual(scenario.created_by, self.user)
        self.assertEqual(endpoint_response.data["creator_name"], self.user.username)
        self.assertEqual(scenario_response.data["creator_name"], self.user.username)

    def test_scenario_list_is_sorted_by_creation_time_descending(self):
        earlier = Scenario.objects.create(project=self.project, name="较早创建的场景")
        earlier.projects.add(self.project)
        later = Scenario.objects.create(project=self.project, name="较晚创建的场景")
        later.projects.add(self.project)

        response = self.client.get("/api/case_api/scenario/")
        items = response.data.get("list", []) if isinstance(response.data, dict) else response.data
        scenario_ids = [item["id"] for item in items]

        self.assertEqual(response.status_code, 200)
        self.assertLess(scenario_ids.index(later.id), scenario_ids.index(earlier.id))

    @patch("case_api.views._run_step")
    def test_runs_saved_endpoint_with_selected_project_environment(self, run_step):
        run_step.return_value = {
            "passed": True,
            "status_code": 200,
            "duration_ms": 12,
            "response_body": '{"ok": true}',
            "errors": [],
        }

        response = self.client.post(
            f"/api/case_api/endpoint/{self.endpoint.id}/run/",
            {"environment": self.environment.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["environment"], "Dev")
        self.assertTrue(response.data["passed"])
        step, selected_environment, variables = run_step.call_args.args
        self.assertEqual(step.endpoint_id, self.endpoint.id)
        self.assertEqual(selected_environment.id, self.environment.id)
        self.assertEqual(variables, {})

    def test_rejects_environment_from_another_project(self):
        another_project = Project.objects.create(name="其他项目", intro="", pm=self.user)
        another_environment = Environment.objects.create(
            project=another_project,
            name="Test",
            base_url="https://other.example.com",
        )

        response = self.client.post(
            f"/api/case_api/endpoint/{self.endpoint.id}/run/",
            {"environment": another_environment.id},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_deleting_endpoint_keeps_scenario_step_removable(self):
        scenario = Scenario.objects.create(project=self.project, name="删除接口场景")
        scenario.projects.add(self.project)
        step = ScenarioStep.objects.create(scenario=scenario, endpoint=self.endpoint, order=1)

        self.endpoint.delete()

        step.refresh_from_db()
        self.assertIsNone(step.endpoint_id)
        response = self.client.delete(f"/api/case_api/scenario-step/{step.id}/")
        self.assertEqual(response.status_code, 204, response.data)
        self.assertFalse(ScenarioStep.objects.filter(pk=step.id).exists())

    def test_creating_step_with_missing_endpoint_returns_friendly_error(self):
        scenario = Scenario.objects.create(project=self.project, name="失效接口场景")
        scenario.projects.add(self.project)

        response = self.client.post(
            "/api/case_api/scenario-step/",
            {"scenario": scenario.id, "endpoint": 999999, "order": 1},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("所选接口不存在", str(response.data))


class ProjectPermissionIsolationTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user("project-member", password="pass")
        self.other_owner = User.objects.create_user("other-owner", password="pass")
        self.project_a = Project.objects.create(name="可访问项目", intro="", pm=self.member)
        self.project_b = Project.objects.create(name="不可访问项目", intro="", pm=self.other_owner)
        self.endpoint_a = Endpoint.objects.create(
            project=self.project_a, name="接口 A", method="GET", url="/a",
        )
        self.endpoint_b = Endpoint.objects.create(
            project=self.project_b, name="接口 B", method="GET", url="/b",
        )
        self.scenario = Scenario.objects.create(
            project=self.project_a, name="跨项目场景", created_by=self.member,
        )
        self.scenario.projects.add(self.project_a, self.project_b)
        self.step_a = ScenarioStep.objects.create(
            scenario=self.scenario, endpoint=self.endpoint_a, order=1,
        )
        self.step_b = ScenarioStep.objects.create(
            scenario=self.scenario, endpoint=self.endpoint_b, order=2,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.member)

    def test_cross_project_scenario_requires_access_to_every_linked_project(self):
        list_response = self.client.get("/api/case_api/scenario/")
        detail_response = self.client.get(f"/api/case_api/scenario/{self.scenario.id}/")
        step_response = self.client.get(f"/api/case_api/scenario-step/{self.step_b.id}/")

        self.assertEqual(list_response.status_code, 200)
        items = list_response.data.get("list", []) if isinstance(list_response.data, dict) else list_response.data
        self.assertNotIn(self.scenario.id, [item["id"] for item in items])
        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(step_response.status_code, 404)

    def test_historical_step_endpoint_project_cannot_bypass_declared_projects(self):
        historical = Scenario.objects.create(
            project=self.project_a,
            name="历史异常场景",
            created_by=self.member,
        )
        historical.projects.add(self.project_a)
        hidden_step = ScenarioStep.objects.create(
            scenario=historical,
            endpoint=self.endpoint_b,
            order=1,
        )

        scenario_response = self.client.get(f"/api/case_api/scenario/{historical.id}/")
        step_response = self.client.get(f"/api/case_api/scenario-step/{hidden_step.id}/")

        self.assertEqual(scenario_response.status_code, 404)
        self.assertEqual(step_response.status_code, 404)

    def test_reorder_cannot_bypass_scenario_project_filter(self):
        response = self.client.post(
            "/api/case_api/scenario-step/reorder/",
            {"scenario": self.scenario.id, "step_ids": [self.step_b.id, self.step_a.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.step_a.refresh_from_db()
        self.step_b.refresh_from_db()
        self.assertEqual((self.step_a.order, self.step_b.order), (1, 2))

    def test_flow_node_reorder_cannot_bypass_scenario_project_filter(self):
        node_a = ScenarioFlowNode.objects.get(step=self.step_a)
        node_b = ScenarioFlowNode.objects.get(step=self.step_b)

        response = self.client.post(
            "/api/case_api/scenario-flow-node/reorder/",
            {"scenario": self.scenario.id, "node_ids": [node_b.id, node_a.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        node_a.refresh_from_db()
        node_b.refresh_from_db()
        self.assertEqual((node_a.order, node_b.order), (1, 2))

    def test_scenario_run_rejects_environment_outside_linked_projects(self):
        unrelated_project = Project.objects.create(name="无关项目", intro="", pm=self.member)
        environment = Environment.objects.create(
            project=unrelated_project, name="Dev", base_url="https://example.com",
        )
        # 先补齐跨项目权限，使请求能进入环境校验逻辑。
        self.project_b.user_list.add(self.member)

        response = self.client.post(
            f"/api/case_api/scenario/{self.scenario.id}/run/",
            {"environment": environment.id},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("不属于场景关联项目", str(response.data))
