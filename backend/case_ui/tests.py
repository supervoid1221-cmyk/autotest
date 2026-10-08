from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from types import SimpleNamespace
from unittest.mock import Mock, patch

from project.models import Environment, Module, Project

from .models import Element, PlaywrightCase, PlaywrightScenarioFile, PlaywrightStep, UiCase, UiStep
from .recording import normalize_ui_recording
from .scenario_text import parse_ui_scenarios
from .playwright_executor import (
    _capture_step_screenshot,
    _click_targets,
    _execute_click_targets,
    _ensure_checked,
    _extract_text,
    _extract_text_with_ocr,
    _input_text,
    _resolve_manual,
    _resolve_upload_input,
    _resolve_open_dropdown_option,
    _steps_for_tab,
    _steps_from_payload,
    _toggle_checked,
)
from .smart_locator.engine import (
    _ambiguity_message,
    _exact_candidates,
    _prefer_creation_action,
    _score_index,
)
from .serializers import PlaywrightStepSerializer, UiCaseSerializer
from .smart_locator.fingerprints import load_for_step, remember_for_step, similarity
from .smart_locator.normalizer import semantic_terms
from .smart_locator.engine import SmartLocatorError


class ScenarioFileTests(TestCase):
    CONTENT = """测试场景:
# ============================================
# 场景1: 新增文件服务器配置
# ============================================
- 场景名称: 新增文件服务器配置 场景ID: FILE_SERVER_CREATE    描述: 验证添加配置
  步骤:
  - 点击：IP管理--批量质量检测
  - 输入账号：自动化测试服务器
  - 打开页面：[http://localhost:8089/login](http://localhost:8089/login)  断言: 保存成功
"""

    def setUp(self):
        self.user = User.objects.create_user(username="scenario-editor")
        self.project = Project.objects.create(name="场景项目", pm=self.user)
        self.environment = Environment.objects.create(project=self.project, name="Test", base_url="http://localhost:8089")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_parse_original_chinese_layout_and_inline_assertion(self):
        scene = parse_ui_scenarios(self.CONTENT)[0]
        self.assertEqual(scene["scenario_id"], "FILE_SERVER_CREATE")
        self.assertEqual([step["action"] for step in scene["steps"]],
                         ["click", "input", "goto", "assert_text"])
        self.assertEqual(scene["steps"][0]["target"], "IP管理--批量质量检测")
        self.assertEqual(scene["steps"][2]["value"], "http://localhost:8089/login")

    def test_fullwidth_steps_header_on_line_eight_is_accepted(self):
        content = "\n".join([
            "测试场景：", "", "# ============================================", "",
            "# 场景1", "", "- 场景名称: 示例 场景ID: EXAMPLE 描述: 示例",
            "  步骤：", "  - 点击：IP管理--批量质量检测",
        ])
        response = self.client.post(
            "/api/case_ui/playwright-scenario-file/preview/",
            {"content": content}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["scenarios"][0]["steps"][0]["target"], "IP管理--批量质量检测")

    def test_separate_metadata_and_implicit_steps_are_accepted(self):
        content = "\n".join([
            "测试场景:", "# 场景1", "- 场景名称: 新增文件服务器配置",
            "  场景ID: FILE\\_SERVER\\_CREATE", "  描述: 验证配置", "======",
            "  - 点击：IP管理--批量质量检测",
        ])
        scene = parse_ui_scenarios(content)[0]
        self.assertEqual(scene["scenario_id"], "FILE_SERVER_CREATE")
        self.assertEqual(scene["description"], "验证配置")
        self.assertEqual(scene["steps"][0]["target"], "IP管理--批量质量检测")

    def test_preview_error_uses_detail_for_complete_message(self):
        response = self.client.post(
            "/api/case_ui/playwright-scenario-file/preview/",
            {"content": self.CONTENT.replace("点击：IP管理--批量质量检测", "未知动作：元素")},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("不支持的步骤", response.data["detail"])

    def test_preview_accepts_masked_password_but_run_rejects_it(self):
        masked_content = self.CONTENT.replace("输入账号：自动化测试服务器", "输入密码：\\*\\*\\*")
        preview = self.client.post(
            "/api/case_ui/playwright-scenario-file/preview/",
            {"content": masked_content}, format="json",
        )
        self.assertEqual(preview.status_code, 200, preview.data)
        scenario_file = PlaywrightScenarioFile.objects.create(
            project=self.project, filename="masked.yaml", content=masked_content,
            environment_name="Test",
        )
        run = self.client.post(
            f"/api/case_ui/playwright-scenario-file/{scenario_file.pk}/run/", {}, format="json",
        )
        self.assertEqual(run.status_code, 400, run.data)
        self.assertIn("占位符", run.data["detail"])

    def test_unknown_action_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "不支持的步骤"):
            parse_ui_scenarios(self.CONTENT.replace("点击：IP管理--批量质量检测", "执行脚本：print(1)"))

    def test_fixed_wait_is_parsed_with_bounded_seconds(self):
        content = self.CONTENT.replace("点击：IP管理--批量质量检测", "固定等待: 2")
        response = self.client.post(
            "/api/case_ui/playwright-scenario-file/preview/",
            {"content": content}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["scenarios"][0]["steps"][0], {
            "action": "sleep", "target": "", "value": "2",
        })
        for seconds in ("0", "301"):
            with self.subTest(seconds=seconds), self.assertRaisesRegex(ValueError, "不超过 300 秒"):
                parse_ui_scenarios(content.replace("固定等待: 2", f"固定等待: {seconds}"))

    def test_extended_yaml_steps_are_parsed(self):
        content = "\n".join([
            "测试场景:", "- 场景名称: 文件处理", "  步骤:",
            "  - 勾选：同意协议", "  - 上传文件 附件：12，13",
            "  - 清空输入：搜索框", "  - 提取文本 订单号：order_id",
        ])
        steps = parse_ui_scenarios(content)[0]["steps"]
        self.assertEqual([step["action"] for step in steps],
                         ["check", "upload_file", "clear", "save_text"])
        self.assertEqual(steps[1]["options"], {"file_ids": [12, 13]})
        self.assertEqual(steps[3]["value"], "order_id")

    def test_extended_yaml_steps_reject_invalid_values(self):
        base = "测试场景:\n- 场景名称: 文件处理\n  步骤:\n  - {}\n"
        for step, error in (("上传文件 附件：../../secret", "已上传文件 ID"),
                            ("上传文件 附件：12,12", "不重复"),
                            ("提取文本 订单号：1invalid", "变量名"),
                            ("清空输入：", "元素名称"),
                            ("勾选：", "元素名称")):
            with self.subTest(step=step), self.assertRaisesRegex(ValueError, error):
                parse_ui_scenarios(base.format(step))

    def test_screenshot_config_attaches_to_previous_assertion(self):
        content = ("测试场景:\n- 场景名称: 登录\n  步骤:\n"
                   "  - 点击：登录\n  断言: 登录成功\n  截图： true\n")
        preview = self.client.post(
            "/api/case_ui/playwright-scenario-file/preview/", {"content": content}, format="json",
        )
        self.assertEqual(preview.status_code, 200, preview.data)
        steps = preview.data["scenarios"][0]["steps"]
        self.assertEqual(steps[-1]["action"], "assert_text")
        self.assertEqual(steps[-1]["options"], {"screenshot": True})
        self.assertNotIn("options", steps[0])

    def test_screenshot_config_rejects_invalid_position_and_value(self):
        base = "测试场景:\n- 场景名称: 登录\n  步骤:\n{}"
        with self.assertRaisesRegex(ValueError, "步骤或断言之后"):
            parse_ui_scenarios(base.format("  截图：true\n  - 点击：登录\n"))
        with self.assertRaisesRegex(ValueError, "true 或 false"):
            parse_ui_scenarios(base.format("  - 点击：登录\n  截图：yes\n"))
        steps = parse_ui_scenarios(base.format("  - 点击：登录\n  截图：false\n"))[0]["steps"]
        self.assertFalse(steps[0]["options"]["screenshot"])

    def test_two_scenes_and_inline_assertion_screenshot_keep_scene_boundaries(self):
        content = (
            "测试场景:\n"
            "- 场景名称: 登录\n  场景ID: LOGIN\n  步骤:\n"
            "  - 打开页面：[http://localhost:8089/login](http://localhost:8089/login)\n"
            "  - 输入邮箱：[admin@example.local](mailto:admin@example.local)\n"
            "  - 输入密码：example\\@2026\n  - 点击：登录\n"
            "  断言: 登录成功\n  截图：true\n"
            "- 场景名称: 发布公告\n  场景ID: NOTICE\n"
            "  - 点击：公告\n  - 点击：保存 断言: 成功 截图：true\n"
        )
        scenes = parse_ui_scenarios(content)
        self.assertEqual([scene["name"] for scene in scenes], ["登录", "发布公告"])
        self.assertEqual(scenes[0]["steps"][1]["value"], "admin@example.local")
        self.assertEqual(scenes[0]["steps"][2]["value"], "example@2026")
        self.assertEqual([step["action"] for step in scenes[1]["steps"]], ["click", "click", "assert_text"])
        self.assertEqual(scenes[1]["steps"][-1]["target"], "成功")
        self.assertTrue(scenes[1]["steps"][-1]["options"]["screenshot"])

    def test_file_can_be_created_and_edited_without_converting_to_case(self):
        response = self.client.post(
            "/api/case_ui/playwright-scenario-file/",
            {"project": self.project.pk, "filename": "FILE_SERVER_CREATE.yaml",
             "content": self.CONTENT, "environment_name": "Test"}, format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        scenario_file = PlaywrightScenarioFile.objects.get(pk=response.data["id"])
        self.assertEqual(scenario_file.content, self.CONTENT)
        self.assertFalse(PlaywrightCase.objects.filter(project=self.project).exists())
        edited = self.CONTENT.replace("自动化测试服务器", "编辑后的服务器")
        update = self.client.patch(
            f"/api/case_ui/playwright-scenario-file/{scenario_file.pk}/",
            {"content": edited}, format="json",
        )
        self.assertEqual(update.status_code, 200, update.data)
        scenario_file.refresh_from_db()
        self.assertEqual(scenario_file.content, edited)

    @patch("case_ui.playwright_executor.execute_playwright_case", return_value={"passed": True, "steps": []})
    def test_run_reads_saved_file_directly(self, execute):
        scenario_file = PlaywrightScenarioFile.objects.create(
            project=self.project, filename="FILE_SERVER_CREATE.yaml",
            content=self.CONTENT, environment_name="Test",
        )
        response = self.client.post(
            f"/api/case_ui/playwright-scenario-file/{scenario_file.pk}/run/", {}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["passed"])
        self.assertEqual(execute.call_args.args[0]["steps"][0]["target"], "IP管理--批量质量检测")
        self.assertFalse(PlaywrightCase.objects.filter(project=self.project).exists())

    @patch("case_ui.playwright_executor.execute_playwright_case")
    def test_run_two_scenes_uses_one_browser_execution(self, execute):
        content = ("测试场景:\n- 场景名称: 登录\n  步骤:\n  - 打开页面：/login\n"
                   "  - 点击：登录\n- 场景名称: 发布公告\n  - 点击：公告\n")
        execute.return_value = {
            "passed": True,
            "steps": [{"passed": True, "id": index} for index in range(3)],
        }
        scenario_file = PlaywrightScenarioFile.objects.create(
            project=self.project, filename="sequential.yaml", content=content, environment_name="Test",
        )
        response = self.client.post(
            f"/api/case_ui/playwright-scenario-file/{scenario_file.pk}/run/", {}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["passed"])
        self.assertEqual([item["name"] for item in response.data["scenarios"]], ["登录", "发布公告"])
        self.assertEqual([len(item["report"]["steps"]) for item in response.data["scenarios"]], [2, 1])
        execute.assert_called_once()
        self.assertEqual([step["action"] for step in execute.call_args.args[0]["steps"]],
                         ["goto", "click", "click"])

    @patch("case_ui.playwright_executor.execute_playwright_case")
    def test_run_returns_inline_screenshot_report(self, execute):
        execute.return_value = {
            "passed": True, "steps": [{"detail": {"screenshot": {
                "path": "data:image/png;base64,cG5n", "label": "步骤截图",
            }}}],
        }
        content = "测试场景:\n- 场景名称: 登录\n  步骤:\n  - 点击：登录\n  截图：true\n"
        scenario_file = PlaywrightScenarioFile.objects.create(
            project=self.project, filename="screenshot.yaml", content=content, environment_name="Test",
        )
        response = self.client.post(
            f"/api/case_ui/playwright-scenario-file/{scenario_file.pk}/run/", {}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(execute.call_args.args[0]["steps"][0]["options"]["screenshot"])
        self.assertFalse(execute.call_args.kwargs["raise_on_failure"])
        self.assertTrue(response.data["scenarios"][0]["report"]["steps"][0]["detail"]["screenshot"]["path"].startswith("data:image/png;base64,"))

    @patch("case_ui.playwright_executor.execute_playwright_case", return_value={"passed": True, "steps": []})
    @patch("case_ui.file_utils.resolve_uploaded_file")
    def test_run_passes_uploaded_file_ids_to_executor(self, resolve_file, execute):
        content = "测试场景:\n- 场景名称: 上传\n  步骤:\n  - 上传文件 附件：12\n"
        scenario_file = PlaywrightScenarioFile.objects.create(
            project=self.project, filename="upload.yaml", content=content, environment_name="Test",
        )
        response = self.client.post(
            f"/api/case_ui/playwright-scenario-file/{scenario_file.pk}/run/", {}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        resolve_file.assert_called_once_with(12, self.project.pk)
        self.assertEqual(execute.call_args.args[0]["steps"][0]["options"],
                         {"file_ids": [12], "source_format": "scenario_text"})

    @patch("case_ui.playwright_executor.execute_playwright_case")
    @patch("case_ui.file_utils.resolve_uploaded_file", side_effect=ValueError("上传文件不存在"))
    def test_run_rejects_missing_uploaded_file_before_execution(self, resolve_file, execute):
        content = "测试场景:\n- 场景名称: 上传\n  步骤:\n  - 上传文件 附件：12\n"
        scenario_file = PlaywrightScenarioFile.objects.create(
            project=self.project, filename="missing-upload.yaml", content=content, environment_name="Test",
        )
        response = self.client.post(
            f"/api/case_ui/playwright-scenario-file/{scenario_file.pk}/run/", {}, format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("上传文件不存在", response.data["detail"])
        execute.assert_not_called()

    def test_convert_yaml_scenes_to_independent_smart_cases(self):
        content = ("测试场景:\n- 场景名称: 登录 场景ID: LOGIN 描述: 验证登录\n"
                   "  步骤:\n  - 打开页面：/login\n  - 点击：登录\n  断言: 登录成功\n  截图：true\n"
                   "- 场景名称: 查看首页 场景ID: HOME\n  步骤:\n  - 点击：首页\n")
        scenario_file = PlaywrightScenarioFile.objects.create(
            project=self.project, filename="convert.yaml", content=content,
            environment_name="Test", browser="firefox", run_mode="headed",
        )
        response = self.client.post(
            f"/api/case_ui/playwright-scenario-file/{scenario_file.pk}/convert-to-smart-case/",
            {}, format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual([item["scenario_id"] for item in response.data["cases"]], ["LOGIN", "HOME"])
        cases = list(PlaywrightCase.objects.filter(project=self.project).order_by("id"))
        self.assertEqual([case.name for case in cases], ["登录", "查看首页"])
        self.assertEqual(cases[0].description, "验证登录")
        self.assertEqual((cases[0].browser, cases[0].run_mode, cases[0].environment_name),
                         ("firefox", "headed", "Test"))
        self.assertEqual(cases[0].tabs, [{"key": "tab-1", "name": "场景步骤", "order": 1}])
        self.assertEqual(cases[0].source_yaml_file_id, scenario_file.pk)
        self.assertEqual(cases[0].source_yaml_scene_key, "id:LOGIN")
        steps = list(cases[0].steps.all())
        self.assertEqual([step.action for step in steps], ["goto", "click", "assert_text"])
        self.assertEqual(steps[-1].options, {"screenshot": True, "source_format": "scenario_text"})
        scenario_file.refresh_from_db()
        self.assertEqual(scenario_file.content, content)

    def test_repeated_convert_updates_bound_case_and_steps_without_duplicate(self):
        scenario_file = PlaywrightScenarioFile.objects.create(
            project=self.project, filename="repeat.yaml", created_by=self.user,
            content="测试场景:\n- 场景名称: 登录\n  场景ID: LOGIN\n  - 点击：登录\n",
            environment_name="Test",
        )
        url = f"/api/case_ui/playwright-scenario-file/{scenario_file.pk}/convert-to-smart-case/"
        first = self.client.post(url, {}, format="json")
        self.assertEqual(first.status_code, 201, first.data)
        case_id = first.data["cases"][0]["id"]
        scenario_file.content = ("测试场景:\n- 场景名称: 登录新版\n  场景ID: LOGIN\n"
                                 "  - 打开页面：/login\n  - 点击：登录\n  断言: 登录成功\n")
        scenario_file.save(update_fields=["content"])
        second = self.client.post(url, {}, format="json")
        self.assertEqual(second.status_code, 200, second.data)
        self.assertEqual(second.data["created_count"], 0)
        self.assertEqual(second.data["updated_count"], 1)
        self.assertEqual(second.data["cases"][0]["id"], case_id)
        self.assertEqual(PlaywrightCase.objects.filter(project=self.project).count(), 1)
        case = PlaywrightCase.objects.get(pk=case_id)
        self.assertEqual(case.name, "登录新版")
        self.assertEqual(list(case.steps.order_by("order").values_list("action", flat=True)),
                         ["goto", "click", "assert_text"])

    def test_repeated_convert_adopts_unambiguous_legacy_case(self):
        scenario_file = PlaywrightScenarioFile.objects.create(
            project=self.project, filename="legacy.yaml", created_by=self.user,
            content="测试场景:\n- 场景名称: 登录\n  场景ID: LOGIN\n  - 点击：新登录\n",
        )
        legacy = PlaywrightCase.objects.create(
            project=self.project, name="登录", created_by=self.user,
            tabs=[{"key": "tab-1", "name": "场景步骤", "order": 1}],
        )
        PlaywrightStep.objects.create(
            case=legacy, order=1, action="click", target="旧登录",
            options={"source_format": "scenario_text"},
        )
        response = self.client.post(
            f"/api/case_ui/playwright-scenario-file/{scenario_file.pk}/convert-to-smart-case/",
            {}, format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["cases"][0]["id"], legacy.pk)
        legacy.refresh_from_db()
        self.assertEqual(legacy.source_yaml_file_id, scenario_file.pk)
        self.assertEqual(list(legacy.steps.values_list("target", flat=True)), ["新登录"])

    def test_convert_rejects_existing_name_without_partial_creation(self):
        PlaywrightCase.objects.create(project=self.project, name="已存在")
        content = ("测试场景:\n- 场景名称: 新场景\n  步骤:\n  - 点击：开始\n"
                   "- 场景名称: 已存在\n  步骤:\n  - 点击：保存\n")
        scenario_file = PlaywrightScenarioFile.objects.create(
            project=self.project, filename="duplicate.yaml", content=content,
        )
        response = self.client.post(
            f"/api/case_ui/playwright-scenario-file/{scenario_file.pk}/convert-to-smart-case/",
            {}, format="json",
        )
        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(list(PlaywrightCase.objects.filter(project=self.project).values_list("name", flat=True)),
                         ["已存在"])

    def test_convert_rolls_back_when_a_step_is_invalid(self):
        content = ("测试场景:\n- 场景名称: 第一场景\n  步骤:\n  - 点击：开始\n"
                   "- 场景名称: 第二场景\n  步骤:\n  - 上传文件 附件：999999\n")
        scenario_file = PlaywrightScenarioFile.objects.create(
            project=self.project, filename="invalid-upload.yaml", content=content,
        )
        response = self.client.post(
            f"/api/case_ui/playwright-scenario-file/{scenario_file.pk}/convert-to-smart-case/",
            {}, format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertFalse(PlaywrightCase.objects.filter(project=self.project).exists())


class RecordingNormalizationTests(TestCase):
    def test_duplicate_transport_event_is_imported_only_once(self):
        event = {
            "eventId": "login-click-1",
            "action": "click",
            "timestamp": 1,
            "tabKey": "tab-1",
            "target": "登录",
            "element": {
                "tag": "button",
                "type": "submit",
                "role": "button",
                "text": "登录",
                "css": 'button[type="submit"]',
            },
        }

        result = normalize_ui_recording({"events": [event, dict(event)]})

        self.assertEqual(len(result["steps"]), 1)
        self.assertEqual(result["steps"][0]["target"], "登录")

    def test_submit_button_uses_own_text_instead_of_password_field_label(self):
        result = normalize_ui_recording({
            "events": [
                {
                    "action": "click",
                    "timestamp": 1,
                    "tabKey": "tab-1",
                    "element": {
                        "tag": "input",
                        "type": "password",
                        "role": "textbox",
                        "label": "密码",
                        "css": 'input[type="password"]',
                    },
                },
                {
                    "action": "input",
                    "timestamp": 2,
                    "tabKey": "tab-1",
                    "value": "secret",
                    "element": {
                        "tag": "input",
                        "type": "password",
                        "role": "textbox",
                        "label": "密码",
                        "css": 'input[type="password"]',
                    },
                },
                {
                    "action": "click",
                    "timestamp": 3,
                    "tabKey": "tab-1",
                    "element": {
                        "tag": "button",
                        "type": "submit",
                        "role": "button",
                        "label": "密码",
                        "text": "登录",
                        "css": 'button[type="submit"]',
                    },
                },
            ],
        })

        self.assertEqual(len(result["steps"]), 2)
        self.assertEqual(result["steps"][0]["action"], "input")
        self.assertEqual(result["steps"][0]["target"], "密码")
        self.assertEqual(result["steps"][1]["action"], "click")
        self.assertEqual(result["steps"][1]["target"], "登录")
        self.assertEqual(
            result["steps"][1]["options"]["smart_locator"]["aliases"][0],
            "登录",
        )

    def test_submit_button_never_falls_back_to_password_nearby_label(self):
        result = normalize_ui_recording({
            "events": [{
                "action": "click",
                "timestamp": 1,
                "tabKey": "tab-1",
                "target": "登录",
                "element": {
                    "tag": "button",
                    "type": "submit",
                    "role": "button",
                    "label": "密码",
                    "nearbyLabels": [{"text": "密码", "distance": 20}],
                    "css": 'button[type="submit"]',
                },
            }],
        })

        self.assertEqual(result["steps"][0]["target"], "登录")
        self.assertNotIn(
            "密码",
            result["steps"][0]["options"]["smart_locator"]["aliases"],
        )

    def test_custom_select_still_uses_field_label_after_own_text_priority(self):
        result = normalize_ui_recording({
            "events": [
                {
                    "action": "click",
                    "timestamp": 1,
                    "tabKey": "tab-1",
                    "element": {
                        "tag": "button",
                        "type": "button",
                        "role": "button",
                        "ariaLabel": "Select option",
                        "label": "平台",
                        "text": "Anthropic",
                        "css": 'button[aria-label="Select option"]',
                    },
                },
                {
                    "action": "click",
                    "timestamp": 2,
                    "tabKey": "tab-1",
                    "element": {
                        "tag": "div",
                        "role": "option",
                        "text": "OpenAI",
                    },
                },
            ],
        })

        self.assertEqual(len(result["steps"]), 1)
        self.assertEqual(result["steps"][0]["action"], "select")
        self.assertEqual(result["steps"][0]["target"], "平台")
        self.assertEqual(result["steps"][0]["value"], "OpenAI")


class UiCaseTabTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="ui-editor")
        self.project = Project.objects.create(name="UI 项目", pm=self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.ui_case = UiCase.objects.create(
            name="后台登录",
            project=self.project,
            tabs=[
                {"key": "login", "name": "登录页", "order": 1},
                {"key": "deposit", "name": "充值页", "order": 2},
            ],
        )

    def test_create_ui_case_records_creator(self):
        response = self.client.post(
            "/api/case_ui/case/",
            {"name": "创建人用例", "project": self.project.id},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        created = UiCase.objects.get(pk=response.data["id"])
        self.assertEqual(created.created_by, self.user)
        self.assertEqual(response.data["creator_name"], self.user.username)

    def test_case_serializer_normalizes_tab_order(self):
        serializer = UiCaseSerializer(
            instance=self.ui_case,
            data={
                "name": self.ui_case.name,
                "project": self.project.id,
                "description": "",
                "browser": "chrome",
                "run_mode": "headless",
                "enabled": True,
                "tabs": [
                    {"key": "login", "name": "登录页", "order": 99},
                    {"key": "deposit", "name": "充值页", "order": 30},
                ],
            },
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        saved = serializer.save()
        self.assertEqual([item["order"] for item in saved.tabs], [1, 2])

    def test_sync_steps_persists_tab_membership_and_global_order(self):
        response = self.client.post(
            f"/api/case_ui/case/{self.ui_case.id}/sync-steps/",
            {
                "steps": [
                    {
                        "action": "goto", "value": "/login",
                        "tab_key": "login", "order": 1, "ui_case": self.ui_case.id,
                        "element": None, "options": {}, "continue_on_failure": False,
                    },
                    {
                        "action": "goto", "value": "/deposit",
                        "tab_key": "deposit", "order": 2, "ui_case": self.ui_case.id,
                        "element": None, "options": {}, "continue_on_failure": False,
                    },
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            list(UiStep.objects.filter(ui_case=self.ui_case).values_list("tab_key", "order")),
            [("login", 1), ("deposit", 2)],
        )

    def test_sync_steps_rejects_deleted_tab(self):
        response = self.client.post(
            f"/api/case_ui/case/{self.ui_case.id}/sync-steps/",
            {
                "steps": [{
                    "action": "goto", "value": "/missing",
                    "tab_key": "missing", "order": 1, "ui_case": self.ui_case.id,
                    "element": None, "options": {}, "continue_on_failure": False,
                }]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("tab_key", response.data)


class ElementModuleTests(TestCase):
    """UI 元素侧的目录行为。目录本身由 project.Module 提供，三个模块共享。"""

    def setUp(self):
        self.user = User.objects.create_user(username="element-editor")
        self.project = Project.objects.create(name="后台项目", pm=self.user)
        self.module = Module.objects.create(project=self.project, name="登录页")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_create_element_records_creator(self):
        response = self.client.post(
            "/api/case_ui/element/",
            {
                "project": self.project.id, "module": self.module.id,
                "name": "创建人元素", "by": "ID", "value": "creator-element",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        created = Element.objects.get(pk=response.data["id"])
        self.assertEqual(created.created_by, self.user)
        self.assertEqual(response.data["creator_name"], self.user.username)

    def test_element_list_supports_project_module_locator_and_search_filters(self):
        target = Element.objects.create(
            project=self.project, module=self.module, name="登录按钮",
            by="CSS_SELECTOR", value="#login-button",
        )
        Element.objects.create(
            project=self.project, module=self.module, name="用户名", by="XPATH", value="//*[@id='email']",
        )

        response = self.client.get(
            "/api/case_ui/element/",
            {"project": self.project.id, "module": self.module.id, "by": "CSS_SELECTOR", "search": "login"},
        )

        self.assertEqual(response.status_code, 200)
        items = response.data.get("list", response.data) if isinstance(response.data, dict) else response.data
        self.assertEqual([item["id"] for item in items], [target.id])
        self.assertEqual(items[0]["module_name"], "登录页")

    def test_element_rejects_module_from_another_project(self):
        other_project = Project.objects.create(name="其他项目", pm=self.user)
        other_module = Module.objects.create(project=other_project, name="首页")

        response = self.client.post(
            "/api/case_ui/element/",
            {
                "project": self.project.id, "module": other_module.id,
                "name": "错误元素", "by": "ID", "value": "submit",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("module", response.data)

    def test_delete_module_can_keep_elements_as_unassigned(self):
        element = Element.objects.create(
            project=self.project, module=self.module, name="登录按钮", by="ID", value="login",
        )

        response = self.client.delete(f"/api/project/module/{self.module.id}/")

        self.assertEqual(response.status_code, 200)
        element.refresh_from_db()
        self.assertIsNone(element.module_id)
        self.assertEqual(response.data["counts"]["ui_element_count"], 1)
        self.assertFalse(response.data["cascade"])


class SmartLocatorConfigurationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="smart-locator")
        self.project = Project.objects.create(name="智能定位项目", pm=self.user)
        self.case = PlaywrightCase.objects.create(name="登录", project=self.project)

    def test_upload_file_locator_accepts_labeled_hidden_input(self):
        page = Mock()
        file_inputs = Mock()
        file_inputs.first = Mock()
        page.locator.return_value = file_inputs
        labeled = Mock()
        labeled.count.return_value = 1
        input_locator = Mock()
        input_locator.evaluate.return_value = True
        labeled.nth.return_value = input_locator
        page.get_by_label.return_value = labeled

        locator, resolution = _resolve_upload_input(page, SimpleNamespace(target="附件"), 1000)

        self.assertIs(locator, input_locator)
        self.assertEqual(resolution["strategy"], "file_input_label")
        file_inputs.first.wait_for.assert_called_once_with(state="attached", timeout=1000)
        input_locator.is_visible.assert_not_called()

    def test_yaml_check_keeps_already_checked_input_checked(self):
        locator = Mock()
        locator.get_attribute.return_value = None
        locator.is_checked.return_value = True

        self.assertEqual(_ensure_checked(locator, 1000), {
            "checked_before": True, "checked_after": True,
        })
        locator.uncheck.assert_not_called()
        locator.check.assert_not_called()

    def test_direct_yaml_screenshot_is_returned_inline_without_writing_to_disk(self):
        page = Mock()
        page.screenshot.return_value = b"png-bytes"
        screenshot = _capture_step_screenshot(page, None, None, "passed")
        self.assertEqual(screenshot, "data:image/png;base64,cG5nLWJ5dGVz")
        self.assertNotIn("path", page.screenshot.call_args.kwargs)

    @patch("case_ui.playwright_executor._wait_for_commit_click", return_value={"commit_click": False})
    @patch("case_ui.playwright_executor.wait_for_ui_transition", return_value={})
    @patch("case_ui.playwright_executor.start_ui_transition_watch", return_value=None)
    @patch("case_ui.playwright_executor._remember_runtime_anchor")
    @patch("case_ui.playwright_executor._resolve")
    def test_click_targets_are_resolved_and_clicked_in_order(
        self, resolve, _anchor, _watch, _transition, _commit,
    ):
        clicked = []
        def resolved(_page, step, _timeout):
            locator = Mock()
            locator.click.side_effect = lambda **_kwargs: clicked.append(step.target)
            return locator, {"strategy": "semantic", "element": {}}
        resolve.side_effect = resolved
        step = SimpleNamespace(
            id=12, action="click", target="IP管理--测试连接", locator_mode="auto",
            fallback_value="", options={}, environment_name="Test",
        )

        detail = _execute_click_targets(Mock(), step, 5000)

        self.assertEqual(clicked, ["IP管理", "测试连接"])
        self.assertEqual(detail["click_count"], 2)
        self.assertEqual([item["target"] for item in detail["clicks"]], clicked)
        self.assertEqual([call.args[1].target for call in resolve.call_args_list], clicked)
        self.assertTrue(all(call.args[1].id is None for call in resolve.call_args_list))

    def test_open_dropdown_option_requires_unique_visible_match(self):
        page = Mock()
        box = {"x": 300, "y": 470, "width": 400, "height": 40}
        page.evaluate.return_value = {"count": 1}
        locator, resolution = _resolve_open_dropdown_option(page, box, "展示中")
        self.assertIs(locator, page.locator.return_value)
        self.assertEqual(resolution["strategy"], "opened_dropdown_exact_text")
        page.evaluate.return_value = {"count": 2}
        self.assertIsNone(_resolve_open_dropdown_option(page, box, "展示中"))

    @patch("case_ui.playwright_executor._wait_for_commit_click", return_value={})
    @patch("case_ui.playwright_executor.wait_for_ui_transition", return_value={})
    @patch("case_ui.playwright_executor.start_ui_transition_watch", return_value=None)
    @patch("case_ui.playwright_executor._remember_runtime_anchor")
    @patch("case_ui.playwright_executor._resolve_open_dropdown_option")
    @patch("case_ui.playwright_executor._resolve")
    def test_multi_click_uses_visible_dropdown_option_after_smart_locator_miss(
        self, resolve, dropdown, _anchor, _watch, _transition, _commit,
    ):
        trigger, option = Mock(), Mock()
        trigger.bounding_box.return_value = {"x": 300, "y": 470, "width": 400, "height": 40}
        resolve.side_effect = [
            (trigger, {"strategy": "semantic", "element": {}}),
            SmartLocatorError("未找到与“展示中”匹配且可操作的元素。"),
        ]
        dropdown.return_value = (option, {"strategy": "opened_dropdown_exact_text", "element": {}})
        step = SimpleNamespace(
            id=12, action="click", target="草稿--展示中", locator_mode="auto",
            fallback_value="", options={}, environment_name="Test",
        )
        detail = _execute_click_targets(Mock(), step, 5000)
        dropdown.assert_called_once_with(resolve.call_args_list[1].args[0],
                                         trigger.bounding_box.return_value, "展示中")
        option.click.assert_called_once_with(timeout=5000)
        self.assertEqual(detail["click_count"], 2)
        self.assertEqual(detail["resolution"]["strategy"], "opened_dropdown_exact_text")

    @patch("case_ui.playwright_executor._resolve")
    def test_multi_click_stops_at_failing_element(self, resolve):
        resolve.side_effect = [
            (Mock(), {"strategy": "semantic", "element": {}}),
            ValueError("未找到元素"),
        ]
        step = SimpleNamespace(
            id=12, action="click", target="IP管理--测试连接--确认", locator_mode="auto",
            fallback_value="", options={}, environment_name="Test",
        )
        with patch("case_ui.playwright_executor._remember_runtime_anchor"), patch(
            "case_ui.playwright_executor.start_ui_transition_watch"
        ), patch("case_ui.playwright_executor.wait_for_ui_transition", return_value={}), patch(
            "case_ui.playwright_executor._wait_for_commit_click", return_value={}
        ):
            with self.assertRaisesRegex(RuntimeError, "第 2/3 个点击元素“测试连接”失败"):
                _execute_click_targets(Mock(), step, 5000)
        self.assertEqual(resolve.call_count, 2)

    def test_multi_click_rejects_empty_target_and_shared_fallback(self):
        with self.assertRaisesRegex(ValueError, "不能为空"):
            _click_targets("IP管理--")
        serializer = PlaywrightStepSerializer(data={
            "case": self.case.id, "tab_key": "tab-1", "order": 1,
            "action": "click", "target": "IP管理--测试连接",
            "locator_mode": "manual", "fallback_type": "css_selector",
            "fallback_value": "#ip-management", "options": {},
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn("连续点击不能共用", str(serializer.errors["target"]))

    def test_api_records_playwright_case_creator(self):
        client = APIClient()
        client.force_authenticate(self.user)

        response = client.post(
            "/api/case_ui/playwright-case/",
            {"name": "创建人测试", "project": self.project.id},
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        created = PlaywrightCase.objects.get(id=response.data["id"])
        self.assertEqual(created.created_by, self.user)
        self.assertEqual(response.data["creator_name"], self.user.username)

    @patch("case_ui.playwright_executor.execute_playwright_case")
    def test_run_tab_executes_only_requested_tab(self, execute_mock):
        self.case.tabs = [
            {"key": "login", "name": "登录页", "order": 1},
            {"key": "users", "name": "用户管理", "order": 2},
        ]
        self.case.save(update_fields=["tabs"])
        client = APIClient()
        client.force_authenticate(self.user)
        execute_mock.return_value = {
            "case_id": self.case.id, "tab_key": "users", "passed": True, "steps": [],
        }

        response = client.post(
            f"/api/case_ui/playwright-case/{self.case.id}/run-tab/",
            {"tab_key": "users"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["tab_name"], "用户管理")
        execute_mock.assert_called_once_with(self.case, tab_key="users")

    @patch("case_ui.playwright_executor.execute_playwright_case")
    def test_run_tab_rejects_unknown_tab(self, execute_mock):
        client = APIClient()
        client.force_authenticate(self.user)

        response = client.post(
            f"/api/case_ui/playwright-case/{self.case.id}/run-tab/",
            {"tab_key": "missing"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("tab_key", response.data)
        execute_mock.assert_not_called()

    def test_semantic_terms_expand_configurable_common_terms(self):
        terms, input_types = semantic_terms("邮箱", {"aliases": ["登录邮箱"]})
        self.assertIn("email", terms)
        self.assertIn("登录邮箱", terms)
        self.assertEqual(input_types, ["email"])

    def test_runtime_steps_keep_their_tab_keys(self):
        steps = _steps_from_payload({"steps": [
            {"id": 1, "action": "goto", "tab_key": "login", "value": "/login"},
            {"id": 2, "action": "click", "tab_key": "accounts", "target": "创建账号"},
        ]})

        self.assertEqual([step.tab_key for step in steps], ["login", "accounts"])

    def test_runtime_can_filter_steps_to_one_tab(self):
        steps = _steps_from_payload({"steps": [
            {"id": 1, "action": "goto", "tab_key": "login", "value": "/login"},
            {"id": 2, "action": "click", "tab_key": "users", "target": "创建用户"},
            {"id": 3, "action": "input", "tab_key": "users", "target": "邮箱", "value": "demo@example.com"},
        ]})

        selected, tab_key = _steps_for_tab(steps, "users")

        self.assertEqual(tab_key, "users")
        self.assertEqual([step.id for step in selected], [2, 3])

    def test_check_action_toggles_current_checkbox_state(self):
        class Locator:
            def __init__(self, checked):
                self.checked = checked

            def is_checked(self, timeout):
                return self.checked

            def check(self, timeout):
                self.checked = True

            def uncheck(self, timeout):
                self.checked = False

        unchecked = Locator(False)
        checked = Locator(True)

        self.assertEqual(_toggle_checked(unchecked, 1000), {
            "checked_before": False, "checked_after": True,
        })
        self.assertTrue(unchecked.checked)
        self.assertEqual(_toggle_checked(checked, 1000), {
            "checked_before": True, "checked_after": False,
        })
        self.assertFalse(checked.checked)

    def test_input_text_respects_clear_before_input(self):
        class Locator:
            def __init__(self, value):
                self.value = value

            def fill(self, value, timeout):
                self.value = value

            def click(self, timeout):
                pass

            def press_sequentially(self, value, timeout):
                self.value += value

        cleared = Locator("旧值")
        appended = Locator("旧值")

        _input_text(cleared, "新值", 1000, True)
        _input_text(appended, "新值", 1000, False)

        self.assertEqual(cleared.value, "新值")
        self.assertEqual(appended.value, "旧值新值")

    def test_save_text_reads_form_control_value_instead_of_inner_text(self):
        class Locator:
            def __init__(self, tag, value, text):
                self.tag, self.value, self.text = tag, value, text

            def evaluate(self, _script):
                return self.tag

            def input_value(self, timeout):
                self_owner.assertEqual(timeout, 1000)
                return self.value

            def inner_text(self, timeout):
                self_owner.assertEqual(timeout, 1000)
                return self.text

        self_owner = self
        self.assertEqual(_extract_text(Locator("input", "353.591.374-87", ""), 1000), "353.591.374-87")
        self.assertEqual(_extract_text(Locator("span", "", "生成并复制"), 1000), "生成并复制")

    @patch("case_ui.playwright_executor._ocr_image", return_value=("识别出的验证码", ""))
    @patch("case_ui.playwright_executor._capture_ocr_screenshot", return_value="screenshots/ocr.png")
    def test_save_text_uses_ocr_only_after_empty_dom_result(self, capture, ocr):
        class Locator:
            def evaluate(self, _script):
                return "span"

            def inner_text(self, timeout):
                self_owner.assertEqual(timeout, 1000)
                return ""

        self_owner = self
        step = SimpleNamespace(
            target="验证码图片",
            options={"ocr_fallback": True, "ocr_language": "zh"},
        )

        value, detail = _extract_text_with_ocr(Locator(), step, 1, 2, 1000)

        self.assertEqual(value, "识别出的验证码")
        self.assertEqual(detail["extraction_source"], "ocr")
        self.assertEqual(detail["ocr_status"], "recognized")
        self.assertEqual(detail["ocr_screenshot"]["path"], "screenshots/ocr.png")
        capture.assert_called_once()
        ocr.assert_called_once_with("screenshots/ocr.png", "zh")

    @patch("case_ui.playwright_executor._capture_ocr_screenshot")
    def test_save_text_never_uses_ocr_for_sensitive_target(self, capture):
        class Locator:
            def evaluate(self, _script):
                return "span"

            def inner_text(self, timeout):
                return ""

        step = SimpleNamespace(target="登录密码", options={"ocr_fallback": True})
        value, detail = _extract_text_with_ocr(Locator(), step, 1, 2, 1000)

        self.assertEqual(value, "")
        self.assertEqual(detail["ocr_status"], "skipped_sensitive")
        capture.assert_not_called()

    def test_click_prefers_exact_visible_menu_text_over_icon_accessible_name(self):
        class Locator:
            def locator(self, _selector):
                return self

        class Page:
            def locator(self, *_args, **_kwargs):
                return Locator()

            def get_by_text(self, *_args, **_kwargs):
                return Locator()

            def get_by_role(self, *_args, **_kwargs):
                return Locator()

            def get_by_test_id(self, *_args, **_kwargs):
                return Locator()

        candidates = _exact_candidates(Page(), "click", "公告", {})

        self.assertEqual(
            [candidate.strategy for candidate in candidates[:6]],
            ["input_value_button", "button_value", "onclick_text", "text_clickable_ancestor", "role_link", "role_button"],
        )

    def test_click_index_recognises_native_button_value(self):
        class Page:
            def locator(self, selector):
                return selector

        index = [{
            "index": "copy", "tag": "input", "type": "button", "role": "",
            "value": "生成并复制", "text": "", "disabled": False, "editable": False,
            "nearbyLabels": [],
        }]

        ranked = _score_index(Page(), index, "click", "生成并复制", {}, None, [])

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["strategy"], "indexed_control_value")

    def test_click_index_recognises_text_only_onclick_control(self):
        class Page:
            def locator(self, selector):
                return selector

        index = [{
            "index": "copy", "tag": "span", "type": "", "role": "", "text": "生成并复制",
            "value": "", "clickable": True, "disabled": False, "editable": False,
            "nearbyLabels": [],
        }]

        ranked = _score_index(Page(), index, "click", "生成并复制", {}, None, [])

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["strategy"], "indexed_text")

    def test_duplicate_creation_buttons_prefer_top_toolbar_action(self):
        ranked = [
            {"score": 101, "info": {"tag": "button", "text": "创建公告", "x": 1200, "y": 130}},
            {"score": 101, "info": {"tag": "button", "text": "创建公告", "x": 700, "y": 620}},
        ]

        self.assertIs(_prefer_creation_action(ranked, "创建公告"), ranked[0])
        self.assertIsNone(_prefer_creation_action([
            {"score": 101, "info": {"tag": "button", "text": "更多", "x": 1200, "y": 300}},
            {"score": 101, "info": {"tag": "button", "text": "更多", "x": 1200, "y": 500}},
        ], "更多"))

    def test_ambiguity_message_describes_each_matching_element_in_plain_language(self):
        message = _ambiguity_message("测试连接", [
            {
                "score": 101,
                "info": {
                    "tag": "button", "text": "测试连接", "x": 1008, "y": 97,
                    "region": "page_top", "nearbyLabels": [{"text": "IP管理"}],
                },
            },
            {
                "score": 101,
                "info": {
                    "tag": "button", "text": "测试连接", "x": 1175, "y": 283,
                    "inTableRow": True, "rowText": "host-proxy-7897 HTTP 257ms 测试连接",
                },
            },
        ])

        self.assertIn("共有 2 个匹配元素", message)
        self.assertIn("第一个：页面顶部的按钮「测试连接」", message)
        self.assertIn("第二个：表格行内的按钮「测试连接」", message)
        self.assertIn("所在行「host-proxy-7897 HTTP 257ms 测试连接」", message)
        self.assertEqual(message.count("\n"), 3)
        self.assertIn("。\n第一个：", message)
        self.assertIn("；\n第二个：", message)
        self.assertIn("；\n请补充元素所在区域", message)
        self.assertNotIn("indexed_text", message)
        self.assertNotIn("分）", message)

    def test_nearest_exact_field_label_beats_distant_secondary_label(self):
        class Page:
            def locator(self, selector):
                return selector

        index = [
            {"index": "title", "tag": "input", "type": "text", "role": "", "disabled": False,
             "editable": False, "nearbyLabels": [
                 {"text": "标题", "vertical": 6, "horizontalGap": 0, "distance": 6, "valid": True},
             ]},
            {"index": "content", "tag": "textarea", "type": "", "role": "", "disabled": False,
             "editable": False, "nearbyLabels": [
                 {"text": "内容（支持 Markdown）", "vertical": 6, "horizontalGap": 0, "distance": 6, "valid": True},
                 {"text": "标题", "vertical": 42, "horizontalGap": 0, "distance": 42, "valid": True},
             ]},
        ]

        ranked = _score_index(Page(), index, "input", "标题", {}, None, [])

        self.assertEqual(ranked[0]["info"]["index"], "title")
        self.assertEqual(ranked[0]["strategy"], "indexed_label_below")
        self.assertGreaterEqual(ranked[0]["score"] - ranked[1]["score"], 15)

    def test_primary_field_label_beats_recorded_nearby_alias(self):
        class Page:
            def locator(self, selector):
                return selector

        index = [
            {"index": "username", "tag": "input", "type": "text", "role": "", "disabled": False,
             "editable": False, "placeholder": "请输入用户名（选填）", "nearbyLabels": [
                 {"text": "用户名", "vertical": 6, "horizontalGap": 0, "distance": 6, "valid": True},
                 {"text": "密码", "vertical": 46, "horizontalGap": 0, "distance": 46, "valid": True},
             ]},
            {"index": "password", "tag": "input", "type": "text", "role": "", "disabled": False,
             "editable": False, "placeholder": "请输入密码", "nearbyLabels": [
                 {"text": "密码", "vertical": 6, "horizontalGap": 0, "distance": 6, "valid": True},
             ]},
        ]

        ranked = _score_index(
            Page(), index, "input", "用户名", {"aliases": ["密码"]}, None, [],
        )

        self.assertEqual(ranked[0]["info"]["index"], "username")
        self.assertGreaterEqual(ranked[0]["score"] - ranked[1]["score"], 15)

    def test_text_assertion_ignores_elements_below_the_message(self):
        class Page:
            def locator(self, selector):
                return selector

        message = "登录成功！欢迎回来。"
        index = [
            {"index": "content", "tag": "div", "type": "", "role": "", "disabled": False,
             "editable": False, "text": "余额 API 密钥 今日请求", "nearbyLabels": [
                 {"text": message, "vertical": 22, "horizontalGap": 0, "distance": 22, "valid": True},
             ]},
            {"index": "toast", "tag": "p", "type": "", "role": "", "disabled": False,
             "editable": False, "text": message, "nearbyLabels": []},
        ]

        ranked = _score_index(Page(), index, "assert_text", message, {}, None, [])

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["info"]["index"], "toast")
        self.assertEqual(ranked[0]["strategy"], "indexed_text")

    def test_environment_locator_overrides_are_accepted(self):
        serializer = PlaywrightStepSerializer(data={
            "case": self.case.id, "tab_key": "tab-1", "order": 1,
            "action": PlaywrightStep.Action.INPUT,
            "target": "账号", "value": "demo", "locator_mode": "auto",
            "fallback_type": "css", "fallback_value": "",
            "options": {"smart_locator": {
                "aliases": ["用户名称"],
                "environments": {"Test": {"test_id": "login-account"}},
            }},
            "continue_on_failure": False,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_selenium_classic_manual_locator_types_are_accepted(self):
        for fallback_type in (
            "id", "name", "class_name", "link_text", "css_selector", "xpath"
        ):
            fallback_value = "//button[@id='create-user']" if fallback_type == "xpath" else "create-user"
            serializer = PlaywrightStepSerializer(data={
                "case": self.case.id, "tab_key": "tab-1", "order": 1,
                "action": PlaywrightStep.Action.CLICK,
                "target": "创建用户", "value": "", "locator_mode": "manual",
                "fallback_type": fallback_type, "fallback_value": fallback_value,
                "options": {}, "continue_on_failure": False,
            })
            self.assertTrue(serializer.is_valid(), {fallback_type: serializer.errors})

    def test_selenium_classic_manual_locator_types_resolve_in_executor(self):
        class Locator:
            def wait_for(self, **kwargs):
                return None

            def count(self):
                return 1

        class Page:
            def __init__(self):
                self.calls = []

            def locator(self, selector):
                self.calls.append(("locator", selector))
                return Locator()

            def get_by_role(self, role, **kwargs):
                self.calls.append(("role", role, kwargs))
                return Locator()

        cases = {
            "id": ("locator", '[id="create-user"]'),
            "name": ("locator", '[name="create-user"]'),
            "class_name": ("locator", "xpath=//*[contains("),
            "link_text": ("role", "link"),
            "css_selector": ("locator", "button.primary"),
            "xpath": ("locator", "xpath=//button"),
        }
        values = {
            "id": "create-user", "name": "create-user", "class_name": "primary",
            "link_text": "创建用户", "css_selector": "button.primary", "xpath": "//button",
        }
        for locator_type, expected in cases.items():
            page = Page()
            step = SimpleNamespace(
                locator_mode="manual", fallback_type=locator_type,
                fallback_value=values[locator_type],
            )
            _, resolution = _resolve_manual(page, step, 1000)
            self.assertEqual(resolution["strategy"], f"manual:{locator_type}")
            self.assertEqual(page.calls[0][0], expected[0])
            self.assertTrue(str(page.calls[0][1]).startswith(expected[1]))

    def test_table_row_locator_configuration_is_accepted(self):
        serializer = PlaywrightStepSerializer(data={
            "case": self.case.id, "tab_key": "tab-1", "order": 1,
            "action": PlaywrightStep.Action.SELECT,
            "target": "更多", "value": "删除", "locator_mode": "auto",
            "fallback_type": "css", "fallback_value": "",
            "options": {"smart_locator": {
                "table": {"title": "用户列表"},
                "row": {"conditions": [
                    {"column": "用户", "operator": "equals", "value": "${created_email}"},
                    {"column": "用户名", "operator": "contains", "value": "lucas"},
                ]},
            }},
            "continue_on_failure": False,
        })

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_table_row_locator_rejects_incomplete_condition(self):
        serializer = PlaywrightStepSerializer(data={
            "case": self.case.id, "tab_key": "tab-1", "order": 1,
            "action": PlaywrightStep.Action.SELECT,
            "target": "更多", "value": "删除", "locator_mode": "auto",
            "fallback_type": "css", "fallback_value": "",
            "options": {"smart_locator": {
                "row": {"conditions": [{"column": "", "operator": "equals", "value": "lucas"}]},
            }},
            "continue_on_failure": False,
        })

        self.assertFalse(serializer.is_valid())
        self.assertIn("options", serializer.errors)

    def test_fingerprint_only_rewards_stable_element_attributes(self):
        saved = {"tag": "input", "type": "email", "name": "email"}
        self.assertEqual(similarity(saved, {"tag": "input", "type": "email", "name": "email"}), 25)
        self.assertEqual(similarity(saved, {"tag": "input", "type": "text", "name": "account"}), 0)

    def test_successful_resolution_persists_reusable_locator(self):
        step = PlaywrightStep.objects.create(
            case=self.case, tab_key="tab-1", order=1,
            action=PlaywrightStep.Action.INPUT, target="邮箱", value="demo@example.com",
        )
        remember_for_step(step.id, "Dev", {
            "strategy": "indexed_placeholder",
            "element": {"tag": "input", "type": "email", "placeholder": "请输入邮箱"},
            "reusable_locator": {"type": "placeholder", "value": "请输入邮箱"},
        })

        fingerprint = load_for_step(step.id, "Dev")
        self.assertEqual(fingerprint["placeholder"], "请输入邮箱")
        self.assertEqual(fingerprint["_locator"], {
            "type": "placeholder", "value": "请输入邮箱",
        })
