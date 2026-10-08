"""Swagger 关联建议：只用文档结构推断，不执行文档中的任何接口。"""
import re


def _normalized(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _related_paths(source, target):
    base = re.sub(r"/\{[^/{}]+\}", "", source.rstrip("/"))
    return bool(base and base != "/" and (target == base or target.startswith(base + "/")))


def suggest_relations(entries):
    candidates = []
    operation_ids = {item.get("operation_id"): index for index, item in enumerate(entries) if item.get("operation_id")}
    for source_index, source in enumerate(entries):
        fields = source.get("response_fields") or []
        for link in source.get("response_links") or []:
            target_index = operation_ids.get(link["operation_id"])
            if target_index is None or target_index == source_index:
                continue
            for target in entries[target_index].get("request_targets") or []:
                if target["key"] == link["key"]:
                    candidates.append((100, source_index, target_index, target, link["path"], "OpenAPI links 明确指定"))
        if source["method"] not in {"POST", "PUT", "PATCH"} or not fields:
            continue
        for target_index, target_entry in enumerate(entries):
            if target_index == source_index or not _related_paths(source["url"], target_entry["url"]):
                continue
            for target in target_entry.get("request_targets") or []:
                for field in fields:
                    if _normalized(field["name"]) != _normalized(target["key"]):
                        continue
                    score = 85 if target["field"] == "path" else 70
                    candidates.append((score, source_index, target_index, target, field["path"], "相同资源路径与响应字段匹配"))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))
    results, seen = [], set()
    for score, source_index, target_index, target, response_path, reason in candidates:
        key = (target_index, target["field"], target["key"])
        if key in seen:
            continue
        seen.add(key)
        variable = f"swagger_{source_index + 1}_{target_index + 1}_{re.sub(r'[^A-Za-z0-9_]', '_', target['key'])}"[:64]
        results.append({
            "id": f"{source_index}:{target_index}:{target['field']}:{target['key']}:{response_path}",
            "source": source_index, "target": target_index, "source_name": entries[source_index]["name"],
            "target_name": entries[target_index]["name"], "target_field": target["field"],
            "target_key": target["key"], "response_path": response_path,
            "variable": variable, "score": score, "reason": reason,
        })
        if len(results) >= 150:
            break
    return results


def selected_order(relations):
    """所选关联必须无环；返回可执行的步骤顺序。"""
    nodes = {item["source"] for item in relations} | {item["target"] for item in relations}
    pending = {node: set() for node in nodes}
    for item in relations:
        pending[item["target"]].add(item["source"])
    order = []
    while pending:
        ready = min((node for node, parents in pending.items() if not parents), default=None)
        if ready is None:
            raise ValueError("所选接口关联存在循环依赖，请取消其中一条。")
        order.append(ready)
        del pending[ready]
        for parents in pending.values():
            parents.discard(ready)
    return order
