"""接口数据驱动（DDT）展开工具。

DDT 仅识别 ``$ddt{字段名}``，不会碰 ``${token}``、``{{token}}`` 和动态函数，
从而可与平台的环境认证、数据提取变量共存。
"""
from __future__ import annotations

import copy
import logging
import re
from typing import Any


logger = logging.getLogger(__name__)
DDT_PATTERN = re.compile(r"\$ddt\{([A-Za-z_]\w*)\}")


def _validate_parametrize(parametrize: Any) -> tuple[list[str], list[list[Any]]]:
    if not isinstance(parametrize, list) or len(parametrize) < 2:
        raise ValueError("数据驱动至少需要一行字段名和一行数据。")
    fields = parametrize[0]
    rows = parametrize[1:]
    if not isinstance(fields, list) or not fields or any(not isinstance(field, str) or not field.strip() for field in fields):
        raise ValueError("数据驱动第一行必须是非空字段名数组。")
    fields = [field.strip() for field in fields]
    if len(set(fields)) != len(fields):
        raise ValueError("数据驱动字段名不能重复。")
    if any(not isinstance(row, list) or len(row) != len(fields) for row in rows):
        raise ValueError("每一行数据的列数必须与字段名数量一致。")
    return fields, rows


def _replace(value: Any, row: dict[str, Any]) -> Any:
    """递归替换 DDT 占位符；占位符独占整个字符串时保留原始数据类型。"""
    if isinstance(value, dict):
        # 断言描述、数据提取变量名也可能包含 DDT 占位符，因此字典键和值
        # 都需要展开；JSON/YAML 的配置键统一保持字符串类型。
        return {
            str(_replace(key, row)) if isinstance(key, str) else key: _replace(item, row)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_replace(item, row) for item in value]
    if not isinstance(value, str):
        return value

    full_match = DDT_PATTERN.fullmatch(value)
    if full_match:
        return row.get(full_match.group(1), value)
    return DDT_PATTERN.sub(lambda match: str(row.get(match.group(1), match.group(0))), value)


def ddt(data: dict[str, Any]) -> list[dict[str, Any]]:
    """将包含 ``parametrize`` 的接口定义展开为多条独立接口定义。

    格式：
    ``[["memberId", "amount"], ["1001", 10], ["1002", 20]]``。
    """
    if "parametrize" not in data:
        return [copy.deepcopy(data)]
    fields, rows = _validate_parametrize(data.get("parametrize"))
    template = copy.deepcopy(data)
    template.pop("parametrize", None)
    base_name = str(template.get("test_name") or "数据驱动接口")
    result = []
    for index, values in enumerate(rows, start=1):
        row = dict(zip(fields, values))
        expanded = _replace(copy.deepcopy(template), row)
        expanded["test_name"] = f"{expanded.get('test_name') or base_name} [数据 {index}]"
        result.append(expanded)
        logger.info("数据驱动展开：%s，第 %s 行=%s", base_name, index, row)
    return result
