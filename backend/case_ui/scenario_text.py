"""解析用户编写的中文 YAML 风格 UI 场景文本。

这里不是通用 YAML：允许「场景名称 / 场景ID / 描述」在同一行，
也允许步骤和断言在同一行。只识别白名单操作，不执行任意表达式。
"""

import re
from urllib.parse import urlparse


MAX_TEXT_LENGTH = 100_000
MAX_SCENARIOS = 50
MAX_STEPS = 200
SCENE_LINE = re.compile(r"^\s*-\s*场景名称\s*[:：]\s*(.*)$")
STEP_LINE = re.compile(r"^\s*-\s*(.*?)\s*$")
FIELD_SPLIT = re.compile(r"\s+(?=(?:场景ID|描述)\s*[:：])")
INLINE_ASSERT = re.compile(r"\s+断言\s*[:：]")
INLINE_SCREENSHOT = re.compile(r"\s+截图\s*[:：]\s*(true|false)\s*$", re.I)
MARKDOWN_LINK = re.compile(r"^\[([^]]+)\]\(([^)]+)\)$")
MASKED_SECRET = re.compile(r"^(?:\*{3,}|•{3,}|[＊]{3,})$")


def _field_value(text, label):
    match = re.fullmatch(rf"{label}\s*[:：]\s*(.*)", text)
    return match.group(1).strip() if match else None


def _step(text, line_number):
    if text.startswith("点击"):
        target = re.sub(r"^点击\s*[:：]?\s*", "", text).strip()
        if target.endswith("按钮"):
            target = target[:-2].strip()
        if not target or not all(part.strip() for part in target.split("--")):
            raise ValueError(f"第 {line_number} 行：点击元素不能为空，连续点击请用 -- 分隔。")
        return {"action": "click", "target": target, "value": ""}

    input_match = re.fullmatch(r"输入\s*(.+?)\s*[:：]\s*(.*)", text)
    if input_match:
        target, value = (part.strip() for part in input_match.groups())
        link = MARKDOWN_LINK.fullmatch(value)
        if link and link.group(2).startswith("mailto:"):
            value = link.group(2)[len("mailto:"):]
        value = value.replace(r"\@", "@")
        if not target or not value:
            raise ValueError(f"第 {line_number} 行：输入步骤需要元素名称和输入值。")
        return {"action": "input", "target": target, "value": value}

    upload_match = re.fullmatch(r"上传文件\s*(.+?)\s*[:：]\s*(.*)", text)
    if upload_match:
        target, file_ids_text = (part.strip() for part in upload_match.groups())
        if not target or not re.fullmatch(r"\d+(?:\s*[,，]\s*\d+)*", file_ids_text):
            raise ValueError(f"第 {line_number} 行：上传文件需要元素名称和已上传文件 ID，多个 ID 用逗号分隔。")
        file_ids = [int(item.strip()) for item in re.split(r"[,，]", file_ids_text)]
        if any(file_id <= 0 for file_id in file_ids) or len(set(file_ids)) != len(file_ids):
            raise ValueError(f"第 {line_number} 行：上传文件 ID 必须为不重复的正整数。")
        return {"action": "upload_file", "target": target, "value": "",
                "options": {"file_ids": file_ids}}

    extract_match = re.fullmatch(r"提取文本\s*(.+?)\s*[:：]\s*(.*)", text)
    if extract_match:
        target, variable = (part.strip() for part in extract_match.groups())
        if not target or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", variable):
            raise ValueError(f"第 {line_number} 行：提取文本需要元素名称和变量名（英文字母、数字、下划线，且不能以数字开头）。")
        return {"action": "save_text", "target": target, "value": variable}

    for label, action in (("清空输入", "clear"), ("勾选", "check")):
        match = re.fullmatch(rf"{label}\s*[:：]\s*(.*)", text)
        if match:
            target = match.group(1).strip()
            if not target:
                raise ValueError(f"第 {line_number} 行：{label}需要填写元素名称。")
            return {"action": action, "target": target, "value": ""}

    goto_match = re.fullmatch(r"打开页面\s*[:：]\s*(.*)", text)
    if goto_match:
        value = goto_match.group(1).strip()
        link = MARKDOWN_LINK.fullmatch(value)
        if link:
            value = link.group(2)
        parsed = urlparse(value)
        if not value or (parsed.scheme and parsed.scheme not in {"http", "https"}):
            raise ValueError(f"第 {line_number} 行：打开页面只支持 HTTP(S) 地址或相对路径。")
        return {"action": "goto", "target": value, "value": value}

    select_match = re.fullmatch(r"(?:选择|下拉选择)\s*(.+?)\s*[:：]\s*(.*)", text)
    if select_match:
        target, value = (part.strip() for part in select_match.groups())
        if not target or not value:
            raise ValueError(f"第 {line_number} 行：下拉选择需要元素名称和选项。")
        return {"action": "select", "target": target, "value": value}

    wait_match = re.fullmatch(r"固定等待\s*[:：]\s*(\d+(?:\.\d+)?)\s*(?:秒|s)?", text, re.I)
    if wait_match:
        seconds = float(wait_match.group(1))
        if not 0 < seconds <= 300:
            raise ValueError(f"第 {line_number} 行：固定等待须大于 0 秒且不超过 300 秒。")
        return {"action": "sleep", "target": "", "value": wait_match.group(1)}

    raise ValueError(f"第 {line_number} 行：不支持的步骤「{text}」。")


def parse_ui_scenarios(content):
    """返回可交给 PlaywrightStepSerializer 的场景列表。"""
    if not isinstance(content, str) or not content.strip():
        raise ValueError("请填写测试场景内容。")
    if len(content) > MAX_TEXT_LENGTH:
        raise ValueError("测试场景内容不能超过 100000 字符。")

    scenarios = []
    current = None
    in_steps = False
    for line_number, raw in enumerate(content.splitlines(), start=1):
        line = re.sub(
            r"\\([_*])", r"\1",
            raw.replace("\u00a0", " ").replace("\u200b", "")
            .replace("\u200c", "").replace("\u200d", "")
            .replace("\u2060", "").replace("\ufeff", ""),
        ).strip()
        if (not line or line.startswith("#") or re.fullmatch(r"测试场景\s*[:：]", line)
                or re.fullmatch(r"[-=_]{3,}", line)):
            continue
        scene_match = SCENE_LINE.fullmatch(line)
        if scene_match:
            if len(scenarios) >= MAX_SCENARIOS:
                raise ValueError("一次最多导入 50 个场景。")
            fields = FIELD_SPLIT.split(scene_match.group(1))
            name = fields[0].strip()
            meta = {}
            for field in fields[1:]:
                for label in ("场景ID", "描述"):
                    value = _field_value(field, label)
                    if value is not None:
                        meta[label] = value
                        break
                else:
                    raise ValueError(f"第 {line_number} 行：无法识别场景字段「{field}」。")
            if not name:
                raise ValueError(f"第 {line_number} 行：场景名称不能为空。")
            current = {"name": name, "scenario_id": meta.get("场景ID", ""),
                       "description": meta.get("描述", ""), "steps": []}
            scenarios.append(current)
            in_steps = False
            continue
        if current is None:
            raise ValueError(f"第 {line_number} 行：请先填写「- 场景名称: ...」。")
        for label, key in (("场景ID", "scenario_id"), ("描述", "description")):
            field_value = _field_value(line, label)
            if field_value is not None and not in_steps:
                current[key] = field_value
                break
        else:
            field_value = None
        if field_value is not None:
            continue
        screenshot_match = re.fullmatch(r"(?:-\s*)?截图\s*[:：]\s*(true|false)", line, re.I)
        if screenshot_match:
            if not current["steps"]:
                raise ValueError(f"第 {line_number} 行：截图配置必须写在要截图的步骤或断言之后。")
            current["steps"][-1].setdefault("options", {})["screenshot"] = (
                screenshot_match.group(1).lower() == "true"
            )
            continue
        if re.match(r"^(?:-\s*)?截图\s*[:：]", line):
            raise ValueError(f"第 {line_number} 行：截图只支持 true 或 false。")
        if re.fullmatch(r"(?:-\s*)?步骤\s*[:：]", line):
            in_steps = True
            continue
        if line.startswith("断言:") or line.startswith("断言："):
            assertion = re.sub(r"^断言\s*[:：]\s*", "", line).strip()
            if not assertion:
                raise ValueError(f"第 {line_number} 行：断言内容不能为空。")
            current["steps"].append({"action": "assert_text", "target": assertion, "value": assertion})
            continue
        match = STEP_LINE.fullmatch(line)
        if not match:
            visible_line = "[敏感内容]" if re.search(r"密码|password|token|secret", line, re.I) else line[:60]
            raise ValueError(
                f"第 {line_number} 行无法识别「{visible_line}」；"
                "步骤请以「- 」开头，或填写「步骤:」标题。"
            )
        in_steps = True
        step_text = match.group(1)
        inline_screenshot = INLINE_SCREENSHOT.search(step_text)
        if inline_screenshot:
            step_text = step_text[:inline_screenshot.start()].rstrip()
        parts = INLINE_ASSERT.split(step_text, maxsplit=1)
        current["steps"].append(_step(parts[0].strip(), line_number))
        if len(parts) == 2:
            assertion = parts[1].strip()
            if not assertion:
                raise ValueError(f"第 {line_number} 行：断言内容不能为空。")
            current["steps"].append({"action": "assert_text", "target": assertion, "value": assertion})
        if inline_screenshot:
            current["steps"][-1].setdefault("options", {})["screenshot"] = (
                inline_screenshot.group(1).lower() == "true"
            )
        if len(current["steps"]) > MAX_STEPS:
            raise ValueError(f"第 {line_number} 行：单个场景最多 200 个步骤。")

    if not scenarios:
        raise ValueError("未找到「- 场景名称: ...」场景。")
    for scene in scenarios:
        if not scene["steps"]:
            raise ValueError(f"场景「{scene['name']}」没有可执行步骤。")
    return scenarios


def validate_runnable_scenarios(scenarios):
    """预览允许脱敏文本；真正执行前才禁止把占位符当作密码输入。"""
    for scene in scenarios:
        for index, step in enumerate(scene["steps"], start=1):
            if step["action"] == "input" and MASKED_SECRET.fullmatch(step["value"]):
                raise ValueError(
                    f"场景「{scene['name']}」第 {index} 步仍是 *** 占位符，"
                    "请填写真实值或 ${变量名} 后再执行。"
                )
