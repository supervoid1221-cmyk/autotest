"""UI 执行器共用的浏览器 Token 注入辅助函数。"""
import json
from urllib.parse import urlparse


def storage_init_script(payload):
    storage = payload.get("storage")
    if storage not in {"local_storage", "session_storage"}:
        return ""
    storage_name = "localStorage" if storage == "local_storage" else "sessionStorage"
    key = json.dumps(str(payload.get("key") or "token"), ensure_ascii=False)
    value = json.dumps(str(payload.get("value") or ""), ensure_ascii=False)
    return f"try {{ window.{storage_name}.setItem({key}, {value}); }} catch (error) {{}}"


def playwright_cookie(payload, base_url):
    if payload.get("storage") != "cookie":
        return None
    parsed = urlparse(str(base_url or ""))
    cookie = {
        "name": str(payload.get("key") or "token"),
        "value": str(payload.get("value") or ""),
        "path": str(payload.get("cookie_path") or "/"),
    }
    domain = str(payload.get("cookie_domain") or "").strip()
    if domain:
        cookie["domain"] = domain
    elif parsed.scheme in {"http", "https"} and parsed.netloc:
        cookie["url"] = f"{parsed.scheme}://{parsed.netloc}"
        cookie.pop("path", None)
    else:
        raise ValueError("Cookie Token 注入需要有效的环境基础地址或 Cookie 域。")
    return cookie


def inject_selenium_token(driver, payload, base_url):
    if not payload:
        return
    script = storage_init_script(payload)
    if script:
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": script})
        return
    cookie = playwright_cookie(payload, base_url)
    if not cookie:
        return
    params = {"name": cookie["name"], "value": cookie["value"], "path": cookie.get("path", "/")}
    if cookie.get("domain"):
        params["domain"] = cookie["domain"]
    else:
        params["url"] = cookie["url"]
    result = driver.execute_cdp_cmd("Network.setCookie", params)
    if result.get("success") is False:
        raise ValueError("浏览器 Cookie Token 注入失败。")
