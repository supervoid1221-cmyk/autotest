"""定位指纹的持久化与匹配。"""


FINGERPRINT_KEYS = ("tag", "type", "role", "id", "name", "testId", "ariaLabel", "placeholder", "value", "text")


def compact_fingerprint(element):
    return {key: element.get(key) for key in FINGERPRINT_KEYS if element.get(key) not in (None, "")}


def similarity(saved, actual):
    saved = saved or {}
    if not saved:
        return 0
    comparable = [key for key in FINGERPRINT_KEYS if saved.get(key)]
    if not comparable:
        return 0
    matches = sum(str(saved.get(key)) == str(actual.get(key)) for key in comparable)
    ratio = matches / len(comparable)
    return 25 if ratio == 1 else 12 if ratio >= 0.7 else 0


def load_for_step(step_id, environment_name):
    try:
        from case_ui.models import PlaywrightLocatorFingerprint
        record = PlaywrightLocatorFingerprint.objects.filter(
            step_id=step_id, environment_name=environment_name or ""
        ).only("fingerprint").first()
        return record.fingerprint if record else {}
    except Exception:
        # 兼容数据库还未完成迁移或单独运行执行器的场景。
        return {}


def remember_for_step(step_id, environment_name, resolution):
    element = (resolution or {}).get("element") or {}
    fingerprint = compact_fingerprint(element)
    reusable_locator = (resolution or {}).get("reusable_locator")
    if isinstance(reusable_locator, dict) and reusable_locator.get("type") and reusable_locator.get("value"):
        fingerprint["_locator"] = reusable_locator
    if not step_id or not fingerprint:
        return
    try:
        from django.db.models import F
        from case_ui.models import PlaywrightLocatorFingerprint
        defaults = {"fingerprint": fingerprint, "strategy": str(resolution.get("strategy") or "")}
        record, created = PlaywrightLocatorFingerprint.objects.get_or_create(
            step_id=step_id, environment_name=environment_name or "", defaults=defaults,
        )
        if not created:
            PlaywrightLocatorFingerprint.objects.filter(pk=record.pk).update(
                fingerprint=fingerprint, strategy=defaults["strategy"], success_count=F("success_count") + 1,
            )
    except Exception:
        return
