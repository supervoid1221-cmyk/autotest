"""把 Swagger 2.0 / OpenAPI 3.x 文档转换为接口库条目。"""
import json
import re
from urllib.parse import urlsplit

import yaml

METHODS = {"get", "post", "put", "patch", "delete", "head", "options"}
SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key", "api-key", "token", "x-token"}
MAX_OPERATIONS = 500


def _module_name(operation, path):
    """优先使用 OpenAPI tag；无 tag 时按首个路径段归类。"""
    tags = operation.get("tags")
    if isinstance(tags, list):
        for tag in tags:
            if isinstance(tag, str) and tag.strip():
                return tag.strip()[:96]
    for segment in path.split("/"):
        if segment and not (segment.startswith("{") and segment.endswith("}")):
            return segment[:96]
    return "未分类"


def _schema_fields(document, schema, prefix="$", depth=0):
    schema = _resolve(document, schema)
    if not isinstance(schema, dict) or depth > 5:
        return []
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return []
    fields = []
    for name, child in list(properties.items())[:60]:
        if not isinstance(name, str):
            continue
        path = f"{prefix}.{name}" if re.fullmatch(r"[A-Za-z_$][\w$]*", name) else f"{prefix}[{json.dumps(name)}]"
        nested = _schema_fields(document, child, path, depth + 1)
        fields.extend(nested or [{"name": name, "path": path}])
    return fields[:100]


def _response_fields(document, operation):
    responses = operation.get("responses") or {}
    if not isinstance(responses, dict):
        return []
    for status_code, raw_response in responses.items():
        if not str(status_code).startswith("2"):
            continue
        response = _resolve(document, raw_response)
        if not isinstance(response, dict):
            continue
        schema = response.get("schema")
        if not schema and isinstance(response.get("content"), dict):
            content = response["content"]
            media = next((value for key, value in content.items() if "json" in key and isinstance(value, dict)), None)
            schema = media.get("schema") if media else None
        if schema:
            return _schema_fields(document, schema)
    return []


def _response_links(document, operation):
    links = []
    for raw_response in (operation.get("responses") or {}).values():
        response = _resolve(document, raw_response)
        if not isinstance(response, dict) or not isinstance(response.get("links"), dict):
            continue
        for raw_link in response["links"].values():
            link = _resolve(document, raw_link)
            if not isinstance(link, dict) or not isinstance(link.get("operationId"), str):
                continue
            for raw_key, expression in (link.get("parameters") or {}).items():
                if not isinstance(raw_key, str) or not isinstance(expression, str) or not expression.startswith("$response.body#/"):
                    continue
                path = "$" + "".join(f".{part.replace('~1', '/').replace('~0', '~')}" for part in expression[len("$response.body#/"):].split("/"))
                links.append({"operation_id": link["operationId"], "key": raw_key.split(".")[-1], "path": path})
    return links


def _resolve(document, value):
    for _ in range(8):
        if not isinstance(value, dict) or "$ref" not in value:
            return value
        ref = value["$ref"]
        if not isinstance(ref, str) or not ref.startswith("#/"):
            return {}
        node = document
        for part in ref[2:].split("/"):
            if not isinstance(node, dict):
                return {}
            node = node.get(part.replace("~1", "/").replace("~0", "~"))
        value = node
    return {}


def _example(document, schema, depth=0):
    schema = _resolve(document, schema)
    if not isinstance(schema, dict) or depth > 5:
        return None
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    for key in ("allOf", "oneOf", "anyOf"):
        if isinstance(schema.get(key), list) and schema[key]:
            if key == "allOf":
                merged = {}
                for item in schema[key]:
                    value = _example(document, item, depth + 1)
                    if isinstance(value, dict):
                        merged.update(value)
                return merged
            return _example(document, schema[key][0], depth + 1)
    if schema.get("type") == "array":
        return [_example(document, schema.get("items", {}), depth + 1)]
    if schema.get("type") == "object" or isinstance(schema.get("properties"), dict):
        return {key: _example(document, value, depth + 1) for key, value in schema.get("properties", {}).items()}
    return None


def parse_swagger(content):
    if not isinstance(content, str) or not content.strip() or len(content.encode("utf-8")) > 2 * 1024 * 1024:
        raise ValueError("请选择 2 MB 以内的 Swagger/OpenAPI 文档。")
    try:
        document = yaml.safe_load(content)
    except (yaml.YAMLError, ValueError) as exc:
        raise ValueError("文档不是有效的 JSON 或 YAML。") from exc
    if not isinstance(document, dict) or not isinstance(document.get("paths"), dict) or not (document.get("swagger") == "2.0" or str(document.get("openapi", "")).startswith("3.")):
        raise ValueError("仅支持 Swagger 2.0 或 OpenAPI 3.x，且文档必须包含 paths。")
    # 服务地址交给项目执行环境维护；只保留 Swagger 2 的 basePath 或
    # OpenAPI 3 的相对 server 前缀，绝不把文档里的主机绑定到接口。
    server = (document.get("servers") or [{}])[0] if isinstance(document.get("servers"), list) else {}
    server_url = server.get("url", "") if isinstance(server, dict) else ""
    prefix = document.get("basePath", "") if document.get("swagger") == "2.0" else urlsplit(server_url).path
    if not isinstance(prefix, str):
        prefix = ""
    entries = []
    for path, path_item in document["paths"].items():
        path_item = _resolve(document, path_item)
        if not isinstance(path, str) or not path.startswith("/") or not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if str(method).lower() not in METHODS or not isinstance(operation, dict):
                continue
            if len(entries) >= MAX_OPERATIONS:
                raise ValueError(f"单次最多导入 {MAX_OPERATIONS} 个接口。")
            url = "/" + "/".join(part for part in (prefix.strip("/"), path.lstrip("/")) if part)
            if len(url) > 255:
                raise ValueError(f"接口路径超过 255 个字符：{path[:80]}")
            parameters = [*_resolve(document, path_item.get("parameters", [])), *_resolve(document, operation.get("parameters", []))] if isinstance(path_item.get("parameters", []), list) and isinstance(operation.get("parameters", []), list) else []
            params, data, headers = {}, {}, {}
            body = {}
            body_type = "json"
            for raw_parameter in parameters:
                parameter = _resolve(document, raw_parameter)
                if not isinstance(parameter, dict) or not isinstance(parameter.get("name"), str):
                    continue
                name = parameter["name"]
                location = parameter.get("in")
                value = parameter.get("example", _example(document, parameter.get("schema", parameter)))
                if location == "query":
                    params[name] = value
                elif location == "header" and name.lower() not in SENSITIVE_HEADERS:
                    headers[name] = value if value is not None else ""
                elif location == "formData":
                    data[name] = value
                    body_type = "form_data" if "multipart/form-data" in operation.get("consumes", document.get("consumes", [])) else "data"
                elif location == "body":
                    body = value if isinstance(value, dict) else {}
            request_body = _resolve(document, operation.get("requestBody", {}))
            if isinstance(request_body, dict) and isinstance(request_body.get("content"), dict):
                media = request_body["content"]
                content_type = next((item for item in ("application/json", "application/x-www-form-urlencoded", "multipart/form-data") if item in media), None)
                if content_type:
                    spec = _resolve(document, media[content_type])
                    if isinstance(spec, dict):
                        sample = spec.get("example", _example(document, spec.get("schema", {})))
                        if isinstance(sample, dict):
                            body = sample
                            body_type = "json" if content_type == "application/json" else ("form_data" if content_type == "multipart/form-data" else "data")
            name = str(operation.get("summary") or operation.get("operationId") or f"{method.upper()} {path}").strip()[:32]
            targets = [{"field": "path", "key": key} for key in re.findall(r"\{([^{}]+)\}", url)]
            for field, values in (("params", params), ("data", data or (body if body_type != "json" else {})), ("json", body if body_type == "json" else {})):
                targets.extend({"field": field, "key": key} for key in values if isinstance(key, str))
            entries.append({"name": name or f"{method.upper()} {path}"[:32], "method": method.upper(), "url": url, "module_name": _module_name(operation, path), "operation_id": str(operation.get("operationId") or ""), "response_fields": _response_fields(document, operation), "response_links": _response_links(document, operation), "request_targets": targets, "params": params, "data": data or (body if body_type != "json" else {}), "json": body if body_type == "json" else {}, "headers": headers, "body_type": body_type})
    if not entries:
        raise ValueError("文档中没有可导入的 HTTP 接口。")
    # YAML 时间戳等标量可能不是 JSONField 支持的原生类型。
    return json.loads(json.dumps(entries, ensure_ascii=False, default=str))
