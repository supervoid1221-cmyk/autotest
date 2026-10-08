from copy import deepcopy


def _endpoint_request(endpoint, method=None, url=None, override=None):
    request = {
        "method": (method or endpoint.method or "GET").upper(),
        "url": url or endpoint.url,
        "headers": deepcopy(endpoint.headers or {}),
        "params": deepcopy(endpoint.params or {}),
        "data": deepcopy(endpoint.data or {}),
        "json": deepcopy(endpoint.json or {}),
    }
    override = deepcopy(override or {})
    if any(key in override for key in ("headers", "params", "data", "json")):
        for key in ("headers", "params", "data", "json"):
            if key in override:
                request[key].update(override.get(key) or {})
    elif override:
        field = "params" if request["method"] == "GET" else "json"
        request[field].update(override)
    return request


def build_endpoint_snapshot(endpoint):
    return {
        "source_type": "endpoint",
        "source_id": endpoint.id,
        "source_name": endpoint.name,
        "steps": [{
            "id": endpoint.id,
            "name": endpoint.name,
            "order": 1,
            "request": _endpoint_request(endpoint),
            "extract": deepcopy(endpoint.extract or {}),
            "validate": deepcopy(endpoint.validate or {}),
            "continue_on_failure": False,
        }],
    }


def build_scenario_snapshot(scenario):
    steps = []
    for step in scenario.steps.select_related("endpoint").order_by("order", "id"):
        endpoint = step.endpoint
        if not endpoint:
            continue
        request = _endpoint_request(
            endpoint,
            method=step.request_method,
            url=step.request_url,
            override=step.request_override,
        )
        steps.append({
            "id": step.id,
            "name": step.name or endpoint.name,
            "order": step.order,
            "request": request,
            "extract": deepcopy(step.extract or endpoint.extract or {}),
            "validate": deepcopy(step.validate or endpoint.validate or {}),
            "continue_on_failure": step.continue_on_failure,
        })
    return {"source_type": "scenario", "source_id": scenario.id, "source_name": scenario.name, "steps": steps}


def build_performance_snapshot(source_type, source_endpoint=None, source_scenario=None):
    if source_type == "endpoint":
        return build_endpoint_snapshot(source_endpoint)
    return build_scenario_snapshot(source_scenario)


def build_mixed_snapshot(items):
    groups = []
    for item in items:
        source_type = item["source_type"]
        snapshot = build_performance_snapshot(
            source_type,
            item.get("source_endpoint_object"),
            item.get("source_scenario_object"),
        )
        groups.append({
            "key": f"{source_type}-{snapshot['source_id']}",
            "name": snapshot["source_name"],
            "source_type": source_type,
            "source_id": snapshot["source_id"],
            "weight": item["weight"],
            "steps": snapshot["steps"],
        })
    return {"source_type": "mixed", "source_name": "混合业务", "groups": groups}
