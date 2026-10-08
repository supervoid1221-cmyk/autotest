"""UI 执行器共用的浏览器 Token 注入辅助函数。"""
import json
from urllib.parse import urlparse


def should_inject_environment_auth(base_url, navigation_targets):
    """仅当用例实际访问当前环境时才注入认证信息。

    相对地址会基于环境 base_url 打开；绝对地址只有与环境同源时
    才需要环境自动登录，避免外部网站用例被无关的环境登录失败阻断。
    """
    environment_url = urlparse(str(base_url or "").strip())
    if environment_url.scheme not in {"http", "https"} or not environment_url.netloc:
        return False

    environment_origin = (environment_url.scheme.lower(), environment_url.netloc.lower())
    for raw_target in navigation_targets or []:
        target = str(raw_target or "").strip()
        if not target:
            continue
        parsed_target = urlparse(target)
        if not parsed_target.scheme and not parsed_target.netloc:
            return True
        if (
            parsed_target.scheme.lower(),
            parsed_target.netloc.lower(),
        ) == environment_origin:
            return True
    return False


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
