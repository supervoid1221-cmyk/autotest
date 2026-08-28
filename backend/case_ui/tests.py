from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient
from types import SimpleNamespace
from unittest.mock import patch

from project.models import Project

from .models import Element, ElementModule, PlaywrightCase, PlaywrightStep, UiCase, UiStep
from .playwright_executor import (
    _extract_text,
    _extract_text_with_ocr,
    _input_text,
    _resolve_manual,
    _steps_for_tab,
    _steps_from_payload,
    _toggle_checked,
)
from .smart_locator.engine import (
    _exact_candidates,
    _prefer_creation_action,
    _score_index,
)
from .serializers import PlaywrightStepSerializer, UiCaseSerializer
from .smart_locator.fingerprints import load_for_step, remember_for_step, similarity
from .smart_locator.normalizer import semantic_terms


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
    def setUp(self):
        self.user = User.objects.create_user(username="element-editor")
        self.project = Project.objects.create(name="后台项目", pm=self.user)
        self.module = ElementModule.objects.create(project=self.project, name="登录页")
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
        other_module = ElementModule.objects.create(project=other_project, name="首页")

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

        response = self.client.delete(f"/api/case_ui/element-module/{self.module.id}/")

        self.assertEqual(response.status_code, 200)
        element.refresh_from_db()
        self.assertIsNone(element.module_id)
        self.assertEqual(response.data["unassigned_element_count"], 1)


class SmartLocatorConfigurationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="smart-locator")
        self.project = Project.objects.create(name="智能定位项目", pm=self.user)
        self.case = PlaywrightCase.objects.create(name="登录", project=self.project)

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
            serializer = PlaywrightStepSerializer(data={
                "case": self.case.id, "tab_key": "tab-1", "order": 1,
                "action": PlaywrightStep.Action.CLICK,
                "target": "创建用户", "value": "", "locator_mode": "manual",
                "fallback_type": fallback_type, "fallback_value": "create-user",
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
