import base64
import time

import requests

from .ocr_locator import locate_text


ELEMENT_KEY = "element-6066-11e4-a52e-4f735466cecf"


class AppiumError(RuntimeError):
    pass


class AppiumClient:
    def __init__(self, server_url, timeout=30):
        self.base_url = str(server_url).rstrip("/")
        self.timeout = timeout
        self.session_id = ""

    def request(self, method, path, payload=None):
        response = requests.request(method, f"{self.base_url}{path}", json=payload, timeout=self.timeout)
        try:
            body = response.json()
        except ValueError as exc:
            raise AppiumError(f"Appium 返回了非 JSON 响应（HTTP {response.status_code}）。") from exc
        value = body.get("value", body)
        if response.status_code >= 400 or (isinstance(value, dict) and value.get("error")):
            message = value.get("message") if isinstance(value, dict) else str(value)
            raise AppiumError(message or f"Appium 请求失败（HTTP {response.status_code}）。")
        return value

    def status(self):
        return self.request("GET", "/status")

    def start_session(self, capabilities):
        value = self.request("POST", "/session", {"capabilities": {"alwaysMatch": capabilities, "firstMatch": [{}]}})
        self.session_id = value.get("sessionId") or value.get("session_id") or ""
        if not self.session_id:
            raise AppiumError("Appium 未返回会话编号。")
        return value.get("capabilities") or value

    def attach(self, session_id):
        self.session_id = str(session_id or "")
        if not self.session_id:
            raise AppiumError("Appium 会话编号不能为空。")
        return self

    def close(self):
        if self.session_id:
            try:
                self.request("DELETE", f"/session/{self.session_id}")
            finally:
                self.session_id = ""

    def command(self, method, path, payload=None):
        if not self.session_id:
            raise AppiumError("Appium 会话尚未创建。")
        return self.request(method, f"/session/{self.session_id}{path}", payload)

    def element(self, using, value, timeout_ms=10000):
        deadline = time.monotonic() + max(0.5, timeout_ms / 1000)
        last_error = None
        if using == "text":
            using, value = "-android uiautomator", f'new UiSelector().text("{str(value).replace(chr(34), chr(92) + chr(34))}")'
        while time.monotonic() < deadline:
            try:
                result = self.command("POST", "/element", {"using": using, "value": value})
                return result.get(ELEMENT_KEY) or result.get("ELEMENT")
            except AppiumError as exc:
                last_error = exc
                time.sleep(0.4)
        raise AppiumError(f"元素定位失败：{last_error or value}")

    def elements(self, using, value):
        if using == "text":
            using, value = "-android uiautomator", f'new UiSelector().text("{str(value).replace(chr(34), chr(92) + chr(34))}")'
        result = self.command("POST", "/elements", {"using": using, "value": value}) or []
        return [item.get(ELEMENT_KEY) or item.get("ELEMENT") for item in result if isinstance(item, dict)]

    def screenshot(self):
        return base64.b64decode(self.command("GET", "/screenshot"))

    def page_source(self):
        return str(self.command("GET", "/source") or "")

    def current_activity(self):
        return str(self.command("GET", "/appium/device/current_activity") or "")

    def current_package(self):
        return str(self.command("GET", "/appium/device/current_package") or "")

    def tap(self, x, y):
        self.command("POST", "/actions", {"actions": [{
            "type": "pointer", "id": "finger1", "parameters": {"pointerType": "touch"},
            "actions": [
                {"type": "pointerMove", "duration": 0, "x": int(x), "y": int(y)},
                {"type": "pointerDown", "button": 0}, {"type": "pause", "duration": 80},
                {"type": "pointerUp", "button": 0},
            ],
        }]})

    def input_text(self, using, value, text, clear=False):
        if using in {"ocr_text", "image_text"}:
            match = self.locate_visual_text(using, value)
            self.tap(match["x"], match["y"])
            self.command("POST", "/keys", {"text": str(text), "value": list(str(text))})
            return
        element_id = self.element(using, value)
        if clear:
            self.command("POST", f"/element/{element_id}/clear", {})
        self.command("POST", f"/element/{element_id}/value", {"text": str(text), "value": list(str(text))})

    def click_element(self, using, value):
        if using in {"ocr_text", "image_text"}:
            match = locate_text(self.screenshot(), value, fuzzy=using == "image_text")
            self.tap(match["x"], match["y"])
            return match
        element_id = self.element(using, value)
        self.command("POST", f"/element/{element_id}/click", {})

    def locate_visual_text(self, using, value):
        if using not in {"ocr_text", "image_text"}:
            raise AppiumError("当前定位方式不是 OCR 或图像文字定位。")
        return locate_text(self.screenshot(), value, fuzzy=using == "image_text")

    def swipe(self, start_x, start_y, end_x, end_y, duration=500):
        self.command("POST", "/actions", {"actions": [{
            "type": "pointer", "id": "finger1", "parameters": {"pointerType": "touch"},
            "actions": [
                {"type": "pointerMove", "duration": 0, "x": int(start_x), "y": int(start_y)},
                {"type": "pointerDown", "button": 0},
                {"type": "pause", "duration": 120},
                {"type": "pointerMove", "duration": max(100, int(duration)), "x": int(end_x), "y": int(end_y)},
                {"type": "pointerUp", "button": 0},
            ],
        }]})
