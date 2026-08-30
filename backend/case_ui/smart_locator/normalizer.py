"""文本标准化和语义别名解析。"""
import re
import unicodedata

from .dictionaries import DEFAULT_SEMANTICS


def normalize(value):
    value = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    return re.sub(r"[\s_\-:/：()（）,.，。]+", "", value)


def semantic_terms(target, configuration=None):
    """返回输入描述的别名、语义类型及由用户配置的扩展词。"""
    configuration = configuration or {}
    target = str(target or "").strip()
    terms = [target] if target else []
    normalized_target = normalize(target)
    types = []

    for name, definition in DEFAULT_SEMANTICS.items():
        aliases = definition.get("aliases", [])
        if normalized_target and any(normalize(alias) == normalized_target for alias in aliases):
            terms.extend(aliases)
            types.extend(definition.get("input_types", []))

    aliases = configuration.get("aliases", [])
    if isinstance(aliases, str):
        aliases = [aliases]
    if isinstance(aliases, list):
        terms.extend(str(item).strip() for item in aliases if str(item).strip())
    configured_types = configuration.get("input_types", [])
    if isinstance(configured_types, str):
        configured_types = [configured_types]
    if isinstance(configured_types, list):
        types.extend(str(item).strip().lower() for item in configured_types if str(item).strip())

    # 保持顺序且按标准化结果去重。
    unique = []
    seen = set()
    for term in terms:
        key = normalize(term)
        if key and key not in seen:
            seen.add(key)
            unique.append(term)
    return unique, list(dict.fromkeys(types))


def semantic_context_tokens(target, configuration=None):
    """获取当前语义可用于消歧的上下文词，例如关闭动作的 modal/dialog。"""
    configuration = configuration or {}
    normalized_target = normalize(target)
    tokens = []
    for definition in DEFAULT_SEMANTICS.values():
        aliases = definition.get("aliases", [])
        if normalized_target and any(normalize(alias) == normalized_target for alias in aliases):
            tokens.extend(definition.get("context_tokens", []))
    configured = configuration.get("context_tokens", [])
    if isinstance(configured, str):
        configured = [configured]
    if isinstance(configured, list):
        tokens.extend(configured)
    return list(dict.fromkeys(str(token) for token in tokens if str(token).strip()))
