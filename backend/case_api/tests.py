from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient
from types import SimpleNamespace

from .flow import execute_flow
from .models import Endpoint, Scenario, ScenarioFlowNode, ScenarioStep
from .recording import normalize_record
from .swagger_import import parse_swagger
from .swagger_links import suggest_relations
from fullstack_framework.commons.api_executor import apply_extract_processor
from project.models import Environment, Module, Project


class SwaggerImportParserTests(SimpleTestCase):
    def test_required_extract_processor_rejects_missing_value(self):
        with self.assertRaisesRegex(ValueError, "必需的响应值"):
            apply_extract_processor("no data", {"type": "required"})
        self.assertEqual(apply_extract_processor(0, {"type": "required"}), 0)

    def test_openapi_link_is_preferred_over_name_matching(self):
        content = '''{"openapi":"3.0.3","paths":{"/create":{"post":{"operationId":"create","responses":{"201":{"description":"ok","links":{"next":{"operationId":"fetch","parameters":{"id":"$response.body#/data/id"}}}}}}},"/lookup/{id}":{"get":{"operationId":"fetch"}}}}'''
        relations = suggest_relations(parse_swagger(content))
        self.assertEqual(len(relations), 1)
        self.assertEqual(relations[0]["score"], 100)
        self.assertEqual(relations[0]["response_path"], "$.data.id")

    def test_openapi_json_resolves_examples_and_drops_auth_headers(self):
        document = '''{"openapi":"3.0.3","servers":[{"url":"https://example.com/v1"}],"paths":{"/users/{id}":{"post":{"summary":"新增用户","parameters":[{"name":"q","in":"query","schema":{"example":"hello"}},{"name":"Authorization","in":"header","example":"secret"}],"requestBody":{"content":{"application/json":{"schema":{"type":"object","properties":{"name":{"example":"张三"}}}}}}}}}}'''
        entries = parse_swagger(document)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["url"], "/v1/users/{id}")
        self.assertEqual(entries[0]["params"], {"q": "hello"})
        self.assertEqual(entries[0]["json"], {"name": "张三"})
        self.assertEqual(entries[0]["headers"], {})

    def test_swagger_yaml_body_and_base_path(self):
        document = '''swagger: '2.0'
basePath: /api
paths:
  /items:
    post:
      summary: 新增商品
      parameters:
        - name: body
          in: body
          schema:
            type: object
            properties:
              title:
                example: 商品
'''
        entries = parse_swagger(document)
        self.assertEqual(entries[0]["url"], "/api/items")
        self.assertEqual(entries[0]["json"], {"title": "商品"})

    def test_rejects_unrelated_yaml(self):
        with self.assertRaises(ValueError):
            parse_swagger("foo: bar")

    def test_module_name_prefers_tag_and_falls_back_to_path(self):
        content = '''{"openapi":"3.0.3","paths":{"/users/{id}":{"get":{"tags":["用户管理"]}},"/orders":{"post":{}}}}'''
        entries = parse_swagger(content)
        self.assertEqual([entry["module_name"] for entry in entries], ["用户管理", "orders"])


class ScenarioFlowExecutionTests(SimpleTestCase):
    def test_disabled_steps_and_branches_are_skipped_without_stopping_flow(self):
        called = []
        nodes = [
            {"id": 1, "order": 1, "node_type": "endpoint", "enabled": False, "step": {"id": 11}},
            {"id": 2, "order": 2, "node_type": "condition", "enabled": False, "branches": [
                {"id": 21, "nodes": [{"id": 3, "node_type": "endpoint", "step": {"id": 12}}]},
            ]},
            {"id": 4, "order": 3, "node_type": "endpoint", "step": {"id": 13}},
        ]
        def run(node):
            called.append(node["step"]["id"])
            return {"step_id": node["step"]["id"], "passed": True}
        result = execute_flow(nodes, {}, run)
        self.assertEqual(called, [13])
        self.assertTrue(result["passed"])
        self.assertEqual(len([item for item in result["results"] if item.get("skipped")]), 2)
        self.assertEqual(result["decisions"][0]["status"], "disabled")

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


class RecordingHeaderSanitizationTests(SimpleTestCase):
    def test_parse_drops_volatile_anti_replay_headers_case_insensitively(self):
        record = normalize_record({
            "request": {
                "method": "GET",
                "url": "https://api.example.com/wallet",
                "headers": [
                    {"name": "X-Timestamp", "value": "1789716122"},
                    {"name": "x-nonce", "value": "once-only"},
                    {"name": "X-SIGNATURE", "value": "stale-signature"},
                    {"name": "X-Platform", "value": "WEB"},
                ],
            },
        })

        self.assertEqual(record["headers"], {"X-Platform": "WEB"})


class EndpointRunAPITests(TestCase):
    def test_import_dataset_preserves_json_types_and_csv_quoted_cells(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        response = self.client.post(
            "/api/case_api/endpoint/import-dataset/",
            {"file": SimpleUploadedFile("input.json", b'[{"id":"001","active":true,"count":2,"extra":null}]', content_type="application/json")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["rows"], [["001", True, 2, None]])
        response = self.client.post(
            "/api/case_api/endpoint/import-dataset/",
            {"file": SimpleUploadedFile("input.csv", b'name,note\nuser,"hello, world"\n', content_type="text/csv")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["rows"], [["user", "hello, world"]])

    def test_rejects_invalid_dataset_shape_and_all_disabled_rows(self):
        for payload in (
            {"parametrize": 12},
            {"parametrize": [123, [1]]},
            {"parametrize": [["id"], [1]], "dataset_options": {"enabled": True, "disabled_rows": [0]}},
        ):
            response = self.client.patch(f"/api/case_api/endpoint/{self.endpoint.pk}/", payload, format="json")
            self.assertEqual(response.status_code, 400, response.data)

    @patch("case_api.views._run_step")
    def test_selecting_data_row_does_not_modify_saved_dataset(self, run_step):
        self.endpoint.parametrize = [["id"], ["001"], [2]]
        self.endpoint.dataset_options = {"enabled": True, "disabled_rows": [0]}
        self.endpoint.save()
        run_step.return_value = {"passed": True, "errors": []}
        response = self.client.post(
            f"/api/case_api/endpoint/{self.endpoint.pk}/run/",
            {"environment": self.environment.pk, "data_row": 1}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(run_step.call_args.args[0].endpoint.parametrize, [["id"], [2]])
        self.endpoint.refresh_from_db()
        self.assertEqual(self.endpoint.parametrize, [["id"], ["001"], [2]])
        self.assertEqual(self.endpoint.dataset_options["disabled_rows"], [0])

    def test_yaml_respects_enabled_rows_and_disabled_mode(self):
        self.endpoint.parametrize = [["id"], [1], [2]]
        self.endpoint.dataset_options = {"enabled": True, "disabled_rows": [0]}
        self.assertEqual(self.endpoint.to_yaml_data("https://example.com")["parametrize"], [["id"], [2]])
        self.endpoint.dataset_options = {"enabled": False}
        self.assertNotIn("parametrize", self.endpoint.to_yaml_data("https://example.com"))

    def test_form_data_preserves_text_fields_and_removes_manual_content_type(self):
        self.endpoint.method = "POST"
        self.endpoint.body_type = "form_data"
        self.endpoint.data = {"description": "测试文本"}
        self.endpoint.headers = {"Content-Type": "multipart/form-data", "X-Test": "1"}
        request = self.endpoint.to_yaml_data("https://example.com")["request"]
        self.assertEqual(request["body_type"], "form_data")
        self.assertEqual(request["data"], {"description": "测试文本"})
        self.assertNotIn("Content-Type", request["headers"])

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
        self.module = Module.objects.create(project=self.project, name="默认模块")
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

    def test_swagger_import_previews_and_skips_existing_endpoint(self):
        content = '''{"openapi":"3.0.3","paths":{"/wallet":{"get":{"summary":"旧接口"}},"/new":{"post":{"summary":"新接口"}}}}'''
        payload = {"project": self.project.pk, "module": self.module.pk, "content": content}
        url = "/api/case_api/endpoint/import-swagger/"
        preview = self.client.post(url, payload, format="json")
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data["new"], 1)
        self.assertEqual(Endpoint.objects.filter(project=self.project).count(), 1)
        saved = self.client.post(url, {**payload, "save": True}, format="json")
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(saved.data, {"created": 1, "skipped": 1})
        self.assertEqual(Endpoint.objects.get(project=self.project, url="/new").module, self.module)
        repeated = self.client.post(url, {**payload, "save": True}, format="json")
        self.assertEqual(repeated.data, {"created": 0, "skipped": 2})

    def test_swagger_import_auto_creates_and_reuses_modules(self):
        content = '''{"openapi":"3.0.3","paths":{"/users":{"get":{"tags":["用户管理"],"summary":"用户列表"}},"/users/{id}":{"delete":{"tags":["用户管理"]}},"/orders":{"post":{}}}}'''
        payload = {"project": self.project.pk, "content": content}
        url = "/api/case_api/endpoint/import-swagger/"
        preview = self.client.post(url, payload, format="json")
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(preview.data["modules"], ["orders", "用户管理"])
        self.assertFalse(Module.objects.filter(project=self.project, name="用户管理").exists())
        saved = self.client.post(url, {**payload, "save": True}, format="json")
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(saved.data["created"], 3)
        self.assertEqual(Module.objects.filter(project=self.project, name="用户管理").count(), 1)
        self.assertEqual(Endpoint.objects.get(project=self.project, url="/users").module.name, "用户管理")
        self.assertEqual(Endpoint.objects.get(project=self.project, url="/orders").module.name, "orders")
        repeated = self.client.post(url, {**payload, "save": True}, format="json")
        self.assertEqual(repeated.data, {"created": 0, "skipped": 3})
        self.assertEqual(Module.objects.filter(project=self.project).count(), 3)

    def test_swagger_selected_module_overrides_tags(self):
        content = '''{"openapi":"3.0.3","paths":{"/users":{"get":{"tags":["用户管理"]}}}}'''
        payload = {"project": self.project.pk, "module": self.module.pk, "content": content, "save": True}
        response = self.client.post("/api/case_api/endpoint/import-swagger/", payload, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Endpoint.objects.get(project=self.project, url="/users").module, self.module)
        self.assertFalse(Module.objects.filter(project=self.project, name="用户管理").exists())

    def test_swagger_relation_preview_and_generated_scenario(self):
        content = '''{"openapi":"3.0.3","paths":{"/users":{"post":{"summary":"创建用户","responses":{"201":{"description":"created","content":{"application/json":{"schema":{"type":"object","properties":{"data":{"type":"object","properties":{"id":{"type":"integer"}}}}}}}}}}},"/users/{id}":{"get":{"summary":"查询用户","parameters":[{"name":"id","in":"path","required":true,"schema":{"type":"integer"}}]}}}}'''
        payload = {"project": self.project.pk, "content": content}
        url = "/api/case_api/endpoint/import-swagger/"
        preview = self.client.post(url, payload, format="json")
        self.assertEqual(preview.status_code, 200, preview.data)
        self.assertEqual(Endpoint.objects.filter(project=self.project).count(), 1)
        self.assertEqual(Scenario.objects.filter(project=self.project).count(), 0)
        relations = preview.data["relations"]
        self.assertEqual(len(relations), 1)
        self.assertEqual(relations[0]["response_path"], "$.data.id")
        self.assertEqual(relations[0]["target_field"], "path")
        saved = self.client.post(url, {**payload, "save": True, "create_scenario": True, "scenario_name": "创建后查询", "relation_ids": [relations[0]["id"]]}, format="json")
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertEqual(saved.data["created"], 2)
        scenario = Scenario.objects.get(pk=saved.data["scenario_id"])
        steps = list(scenario.steps.order_by("order"))
        self.assertEqual([step.endpoint.method for step in steps], ["POST", "GET"])
        self.assertEqual(steps[0].extract[relations[0]["variable"]], {"mode": "jsonpath", "source": "json", "expression": "$.data.id", "index": 0, "processors": [{"type": "required"}]})
        self.assertEqual(steps[1].request_url, "/users/${" + relations[0]["variable"] + "}")
        self.assertEqual(scenario.flow_nodes.count(), 2)
        self.assertEqual(Endpoint.objects.get(project=self.project, url="/users/{id}").url, "/users/{id}")
        self.assertFalse(steps[0].continue_on_failure)
        repeated = self.client.post(url, {**payload, "save": True, "create_scenario": True, "scenario_name": "创建后查询（再次编排）", "relation_ids": [relations[0]["id"]]}, format="json")
        self.assertEqual(repeated.status_code, 200, repeated.data)
        self.assertEqual(repeated.data["created"], 0)
        self.assertEqual(repeated.data["skipped"], 2)
        self.assertTrue(Scenario.objects.filter(pk=repeated.data["scenario_id"]).exists())

    def test_swagger_rejects_unconfirmed_relation_without_importing(self):
        content = '''{"openapi":"3.0.3","paths":{"/items":{"post":{"responses":{"200":{"description":"ok","content":{"application/json":{"schema":{"type":"object","properties":{"id":{"type":"integer"}}}}}}}}},"/items/{id}":{"get":{}}}}'''
        response = self.client.post("/api/case_api/endpoint/import-swagger/", {
            "project": self.project.pk, "content": content, "save": True,
            "create_scenario": True, "relation_ids": ["not-a-previewed-relation"],
        }, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Endpoint.objects.filter(project=self.project, url="/items").exists())

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

    def test_recording_import_drops_volatile_headers_even_when_parse_is_bypassed(self):
        response = self.client.post(
            "/api/case_api/recording/import_records/",
            {
                "project": self.project.id,
                "module": self.module.id,
                "records": [{
                    "selected": True,
                    "name": "录制余额",
                    "method": "GET",
                    "url": "/wallet/recorded",
                    "headers": {
                        "x-timestamp": "1789716122",
                        "X-Nonce": "once-only",
                        "x-signature": "stale-signature",
                        "x-platform": "WEB",
                    },
                }],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        endpoint = Endpoint.objects.get(project=self.project, url="/wallet/recorded")
        self.assertEqual(endpoint.headers, {"x-platform": "WEB"})

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
