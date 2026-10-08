import re
from xml.etree import ElementTree


BOUNDS_PATTERN = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def _truthy(value):
    return str(value or "").lower() == "true"


def _escape_uiautomator(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _xpath_literal(value):
    value = str(value)
    if '"' not in value:
        return f'"{value}"'
    if "'" not in value:
        return f"'{value}'"
    parts = value.split('"')
    return "concat(" + ", '\"', ".join(f'"{part}"' for part in parts) + ")"


def locator_candidates(attributes, xpath):
    candidates = []
    content_desc = attributes.get("content-desc", "").strip()
    resource_id = attributes.get("resource-id", "").strip()
    text = attributes.get("text", "").strip()
    class_name = attributes.get("class", "").strip()

    if content_desc:
        candidates.append({"type": "accessibility id", "label": "Accessibility ID", "value": content_desc, "stability": "high"})
    if resource_id:
        candidates.append({"type": "id", "label": "Resource ID", "value": resource_id, "stability": "high"})
    if text:
        candidates.append({
            "type": "-android uiautomator", "label": "UIAutomator 文本",
            "value": f'new UiSelector().text("{_escape_uiautomator(text)}")', "stability": "medium",
        })
    if class_name and text:
        candidates.append({
            "type": "-android uiautomator", "label": "UIAutomator 组合",
            "value": f'new UiSelector().className("{_escape_uiautomator(class_name)}").text("{_escape_uiautomator(text)}")',
            "stability": "medium",
        })
    if resource_id:
        candidates.append({
            "type": "xpath", "label": "XPath 属性", "value": f'//*[@resource-id={_xpath_literal(resource_id)}]',
            "stability": "medium",
        })
    if text:
        candidates.append({
            "type": "ocr_text", "label": "OCR 文字定位",
            "value": text, "stability": "medium",
        })
        candidates.append({
            "type": "image_text", "label": "图像文字识别",
            "value": text, "stability": "low",
        })
    if xpath:
        candidates.append({"type": "xpath", "label": "XPath 路径", "value": xpath, "stability": "low"})
    bounds = parse_bounds(attributes.get("bounds"))
    if bounds[2] > bounds[0] and bounds[3] > bounds[1]:
        center_x = round((bounds[0] + bounds[2]) / 2)
        center_y = round((bounds[1] + bounds[3]) / 2)
        candidates.append({
            "type": "coordinate", "label": "坐标定位",
            "value": f"{center_x},{center_y}", "stability": "low",
        })
    return candidates


def parse_bounds(value):
    match = BOUNDS_PATTERN.fullmatch(str(value or "").strip())
    return [int(part) for part in match.groups()] if match else [0, 0, 0, 0]


def parse_page_source(source):
    try:
        root = ElementTree.fromstring(source)
    except (ElementTree.ParseError, TypeError, ValueError) as exc:
        raise ValueError(f"页面结构 XML 解析失败：{exc}") from exc

    elements = []

    def walk(node, parent_id=None, depth=0, path="", sibling_index=1):
        node_id = f"node_{len(elements) + 1}"
        attrs = {str(key): str(value) for key, value in node.attrib.items()}
        class_name = attrs.get("class") or node.tag
        xpath = f"{path}/{class_name}[{sibling_index}]" if path else f"/{class_name}[1]"
        bounds = parse_bounds(attrs.get("bounds"))
        label = attrs.get("text") or attrs.get("content-desc") or attrs.get("resource-id", "").rsplit("/", 1)[-1] or class_name
        item = {
            "node_id": node_id,
            "parent_id": parent_id,
            "depth": depth,
            "label": label[:120],
            "class_name": class_name,
            "text": attrs.get("text", ""),
            "resource_id": attrs.get("resource-id", ""),
            "content_desc": attrs.get("content-desc", ""),
            "package": attrs.get("package", ""),
            "bounds": bounds,
            "clickable": _truthy(attrs.get("clickable")),
            "enabled": _truthy(attrs.get("enabled")),
            "displayed": not attrs.get("displayed") or _truthy(attrs.get("displayed")),
            "attributes": attrs,
            "xpath": xpath,
        }
        item["candidates"] = locator_candidates(attrs, xpath) if bounds[2] > bounds[0] and bounds[3] > bounds[1] else []
        elements.append(item)
        class_counts = {}
        for child in list(node):
            child_class = child.attrib.get("class") or child.tag
            class_counts[child_class] = class_counts.get(child_class, 0) + 1
            walk(child, node_id, depth + 1, xpath, class_counts[child_class])

    walk(root)
    return elements
