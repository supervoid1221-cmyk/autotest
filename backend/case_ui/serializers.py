"""
@Filename:   serializers
@Time:        2023/8/3 20:23
@Describe:    ...
"""
import re

from rest_framework import serializers

from project.models import Project

from .models import Element, ElementModule, PlaywrightCase, PlaywrightStep, UiCase, UiStep, UiUploadedFile


SENSITIVE_OCR_TARGET = re.compile(r"password|passwd|pwd|token|secret|authorization|密码|密钥", re.I)


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = "__all__"  # 使用全部字段


class ElementSerializer(serializers.ModelSerializer):
    project_info = ProjectSerializer(source="project", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    module_name = serializers.CharField(source="module.name", read_only=True)
    creator_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = Element
        fields = "__all__"  # 使用全部字段
        extra_kwargs = {"created_by": {"read_only": True}}

    def validate(self, attrs):
        project = attrs.get("project", getattr(self.instance, "project", None))
        module = attrs.get("module", getattr(self.instance, "module", None))
        if module and project and module.project_id != project.id:
            raise serializers.ValidationError({"module": "所选模块不属于当前项目。"})
        return attrs


class ElementModuleSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    element_count = serializers.IntegerField(source="elements.count", read_only=True)

    class Meta:
        model = ElementModule
        fields = "__all__"


class UiCaseSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    creator_name = serializers.CharField(source="created_by.username", read_only=True)
    step_count = serializers.IntegerField(source="steps.count", read_only=True)

    class Meta:
        model = UiCase
        fields = "__all__"
        extra_kwargs = {"created_by": {"read_only": True}}

    def validate_tabs(self, value):
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError("至少需要保留一个 Tab。")
        normalized = []
        keys = set()
        for index, item in enumerate(value, start=1):
            if not isinstance(item, dict):
                raise serializers.ValidationError(f"第 {index} 个 Tab 格式不正确。")
            key = str(item.get("key") or "").strip()
            name = str(item.get("name") or "").strip()
            if not key:
                raise serializers.ValidationError(f"第 {index} 个 Tab 缺少唯一标识。")
            if key in keys:
                raise serializers.ValidationError("Tab 唯一标识不能重复。")
            if not name:
                raise serializers.ValidationError(f"第 {index} 个 Tab 未填写名称。")
            if len(key) > 64 or len(name) > 32:
                raise serializers.ValidationError("Tab 名称不能超过 32 个字，标识不能超过 64 个字。")
            keys.add(key)
            normalized.append({"key": key, "name": name, "order": index})
        return normalized


class UiStepSerializer(serializers.ModelSerializer):
    element_name = serializers.CharField(source="element.name", read_only=True)
    element_by = serializers.CharField(source="element.by", read_only=True)
    element_value = serializers.CharField(source="element.value", read_only=True)
    action_name = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = UiStep
        fields = "__all__"

    def validate(self, attrs):
        instance = self.instance
        ui_case = attrs.get("ui_case", getattr(instance, "ui_case", None))
        action = attrs.get("action", getattr(instance, "action", None))
        element = attrs.get("element", getattr(instance, "element", None))
        tab_key = str(attrs.get("tab_key", getattr(instance, "tab_key", "tab-1")) or "").strip()
        value = str(attrs.get("value", getattr(instance, "value", "")) or "").strip()

        element_actions = {
            UiStep.Action.CLICK, UiStep.Action.INPUT, UiStep.Action.UPLOAD_FILE, UiStep.Action.CLEAR,
            UiStep.Action.SAVE_TEXT, UiStep.Action.ASSERT_TEXT,
            UiStep.Action.ASSERT_VALUE, UiStep.Action.IFRAME_ENTER,
            UiStep.Action.SELECT,
        }
        value_actions = {
            UiStep.Action.GOTO, UiStep.Action.INPUT, UiStep.Action.SAVE_TEXT,
            UiStep.Action.ASSERT_TEXT, UiStep.Action.ASSERT_VALUE,
            UiStep.Action.SELECT, UiStep.Action.JS_CODE, UiStep.Action.SLEEP,
        }
        if action in element_actions and not element:
            raise serializers.ValidationError({"element": "该操作必须选择页面元素。"})
        if action in value_actions and not value:
            raise serializers.ValidationError({"value": "该操作必须填写操作值。"})
        if ui_case and element and element.project_id != ui_case.project_id:
            raise serializers.ValidationError({"element": "只能选择当前用例项目下的页面元素。"})
        if ui_case:
            tab_keys = {
                str(item.get("key")) for item in (ui_case.tabs or [])
                if isinstance(item, dict) and item.get("key")
            }
            if tab_key not in tab_keys:
                raise serializers.ValidationError({"tab_key": "所选 Tab 不存在或已被删除。"})
        if action == UiStep.Action.SLEEP:
            try:
                if float(value) < 0:
                    raise ValueError
            except ValueError:
                raise serializers.ValidationError({"value": "等待时间必须是大于或等于 0 的秒数。"})
        if action == UiStep.Action.UPLOAD_FILE:
            options = attrs.get("options", getattr(instance, "options", {})) or {}
            file_ids = options.get("file_ids", []) if isinstance(options, dict) else []
            if not isinstance(file_ids, list) or not file_ids:
                raise serializers.ValidationError({"options": "上传文件步骤至少需要选择一个文件。"})
            if ui_case and UiUploadedFile.objects.filter(project=ui_case.project, id__in=file_ids).count() != len(set(file_ids)):
                raise serializers.ValidationError({"options": "存在无权限、已删除或不属于当前项目的上传文件。"})
        return attrs


class PlaywrightCaseSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    creator_name = serializers.CharField(source="created_by.username", read_only=True)
    step_count = serializers.IntegerField(source="steps.count", read_only=True)

    class Meta:
        model = PlaywrightCase
        fields = "__all__"
        extra_kwargs = {"created_by": {"read_only": True}}

    def validate_default_timeout(self, value):
        if value < 100 or value > 300000:
            raise serializers.ValidationError("默认超时必须在 100～300000 毫秒之间。")
        return value


class PlaywrightStepSerializer(serializers.ModelSerializer):
    action_name = serializers.CharField(source="get_action_display", read_only=True)

    class Meta:
        model = PlaywrightStep
        fields = "__all__"

    def validate(self, attrs):
        instance = self.instance
        action = attrs.get("action", getattr(instance, "action", None))
        target = str(attrs.get("target", getattr(instance, "target", "")) or "").strip()
        value = str(attrs.get("value", getattr(instance, "value", "")) or "").strip()
        # 共用现有 UI 用例编辑器后，“打开页面”的地址位于操作值字段。
        # 同时兼容第一阶段已保存到 target 的历史数据。
        if action == PlaywrightStep.Action.GOTO and not target and value:
            attrs["target"] = value
            target = value
        if action == PlaywrightStep.Action.GOTO and not target:
            raise serializers.ValidationError({"target": "打开页面必须填写访问地址。"})
        if action != PlaywrightStep.Action.GOTO and action != PlaywrightStep.Action.SLEEP and not target:
            raise serializers.ValidationError({"target": "该操作必须填写页面元素描述。"})
        if action in {PlaywrightStep.Action.INPUT, PlaywrightStep.Action.SELECT,
                      PlaywrightStep.Action.ASSERT_TEXT, PlaywrightStep.Action.SAVE_TEXT,
                      PlaywrightStep.Action.SLEEP} and not value:
            raise serializers.ValidationError({"value": "该操作必须填写操作值。"})
        if attrs.get("locator_mode", getattr(instance, "locator_mode", "auto")) == "manual" and not str(
            attrs.get("fallback_value", getattr(instance, "fallback_value", "")) or ""
        ).strip():
            raise serializers.ValidationError({"fallback_value": "手动定位时必须填写备用定位表达式。"})
        fallback_type = str(
            attrs.get("fallback_type", getattr(instance, "fallback_type", "")) or ""
        ).lower()
        supported_fallback_types = {
            "id", "name", "class_name", "link_text", "css_selector", "xpath",
            # 仅用于兼容升级前已保存的用例。
            "css", "testid", "test_id", "role",
        }
        if fallback_type and fallback_type not in supported_fallback_types:
            raise serializers.ValidationError({"fallback_type": "不支持的手动兜底定位方式。"})
        options = attrs.get("options", getattr(instance, "options", {})) or {}
        if not isinstance(options, dict):
            raise serializers.ValidationError({"options": "扩展配置必须是对象。"})
        if options.get("ocr_fallback") not in (None, True, False):
            raise serializers.ValidationError({"options": "ocr_fallback 必须为布尔值。"})
        if str(options.get("ocr_language") or "auto").lower() not in {"auto", "zh", "en"}:
            raise serializers.ValidationError({"options": "OCR 语言仅支持自动、中文或英文。"})
        if bool(options.get("ocr_fallback")) and SENSITIVE_OCR_TARGET.search(target):
            raise serializers.ValidationError({"options": "密码、Token、密钥等敏感字段禁止启用 OCR 兜底。"})
        if action == PlaywrightStep.Action.UPLOAD_FILE:
            file_ids = options.get("file_ids", [])
            if not isinstance(file_ids, list) or not file_ids:
                raise serializers.ValidationError({"options": "上传文件步骤至少需要选择一个文件。"})
            case = attrs.get("case", getattr(instance, "case", None))
            if case and UiUploadedFile.objects.filter(project=case.project, id__in=file_ids).count() != len(set(file_ids)):
                raise serializers.ValidationError({"options": "存在无权限、已删除或不属于当前项目的上传文件。"})
        smart_locator = options.get("smart_locator", {})
        if smart_locator not in ({}, None) and not isinstance(smart_locator, dict):
            raise serializers.ValidationError({"options": "smart_locator 必须是对象。"})
        if isinstance(smart_locator, dict):
            aliases = smart_locator.get("aliases", [])
            if aliases not in (None, "") and not isinstance(aliases, (str, list)):
                raise serializers.ValidationError({"options": "smart_locator.aliases 必须是文本或文本数组。"})
            role = smart_locator.get("role", "")
            if role and not isinstance(role, str):
                raise serializers.ValidationError({"options": "smart_locator.role 必须是文本。"})
            environments = smart_locator.get("environments", {})
            if environments not in ({}, None) and not isinstance(environments, dict):
                raise serializers.ValidationError({"options": "smart_locator.environments 必须是按环境名称配置的对象。"})
            if isinstance(environments, dict) and any(not isinstance(item, dict) for item in environments.values()):
                raise serializers.ValidationError({"options": "smart_locator.environments 中每个环境配置必须是对象。"})
            table = smart_locator.get("table", {})
            if table not in ({}, None) and not isinstance(table, dict):
                raise serializers.ValidationError({"options": "smart_locator.table 必须是对象。"})
            if isinstance(table, dict) and table.get("title") is not None and not isinstance(table.get("title"), str):
                raise serializers.ValidationError({"options": "smart_locator.table.title 必须是文本。"})
            row = smart_locator.get("row", {})
            if row not in ({}, None) and not isinstance(row, dict):
                raise serializers.ValidationError({"options": "smart_locator.row 必须是对象。"})
            if isinstance(row, dict) and row:
                conditions = row.get("conditions", [])
                if not isinstance(conditions, list) or not conditions:
                    raise serializers.ValidationError({"options": "数据行定位至少需要一个条件。"})
                allowed_operators = {"equals", "contains", "not_equals", "starts_with", "regex"}
                for index, condition in enumerate(conditions, start=1):
                    if not isinstance(condition, dict):
                        raise serializers.ValidationError({"options": f"第 {index} 个数据行条件必须是对象。"})
                    if not str(condition.get("column") or "").strip():
                        raise serializers.ValidationError({"options": f"第 {index} 个数据行条件未填写列名。"})
                    if condition.get("operator", "equals") not in allowed_operators:
                        raise serializers.ValidationError({"options": f"第 {index} 个数据行条件的比较方式不支持。"})
                    if condition.get("value") is None or not str(condition.get("value")).strip():
                        raise serializers.ValidationError({"options": f"第 {index} 个数据行条件未填写期望值。"})
        return attrs


class UiUploadedFileSerializer(serializers.ModelSerializer):
    creator_name = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = UiUploadedFile
        fields = "__all__"
        extra_kwargs = {
            "created_by": {"read_only": True}, "stored_path": {"read_only": True},
            "original_name": {"read_only": True}, "size": {"read_only": True},
        }
