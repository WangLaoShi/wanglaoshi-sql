"""列角色判断。这个模块不连接数据库。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# 先命中先停：标识、时间、列名维度、数值基数、布尔或文本、未知。
_IDENTIFIER_EXACT = {"id"}
_DIMENSION_TOKENS = {
    "year",
    "zip",
    "postal",
    "postcode",
    "zipcode",
    "code",
    "rating",
    "score",
    "level",
    "grade",
    "rank",
}
_DIMENSION_ZH = ("年份", "邮编", "编码", "评分", "等级")
_NUMERIC = {
    "TINYINT",
    "SMALLINT",
    "INTEGER",
    "INT",
    "BIGINT",
    "HUGEINT",
    "UTINYINT",
    "USMALLINT",
    "UINTEGER",
    "UBIGINT",
    "UHUGEINT",
    "FLOAT",
    "DOUBLE",
    "REAL",
    "DECIMAL",
    "NUMERIC",
}
_BOOLEAN = {"BOOLEAN", "BOOL", "LOGICAL"}
_STRING = {"VARCHAR", "CHAR", "BPCHAR", "TEXT", "STRING"}
_LOW_DISTINCT = 20
_LOW_RATIO = 0.05
_MIN_NON_NULL_FOR_RATIO = 20


class Role(StrEnum):
    DIMENSION = "dimension"
    MEASURE = "measure"
    TIME = "time"
    IDENTIFIER = "identifier"
    UNKNOWN = "unknown"


ROLE_LABELS = {
    Role.DIMENSION: "维度",
    Role.MEASURE: "度量",
    Role.TIME: "时间",
    Role.IDENTIFIER: "标识",
    Role.UNKNOWN: "未知",
}

_ROLE_ALIASES = {
    "dimension": Role.DIMENSION,
    "measure": Role.MEASURE,
    "time": Role.TIME,
    "identifier": Role.IDENTIFIER,
    "维度": Role.DIMENSION,
    "度量": Role.MEASURE,
    "时间": Role.TIME,
    "标识": Role.IDENTIFIER,
}

MANUAL_REASON = "课堂上手工指定。"


@dataclass(frozen=True)
class RoleDecision:
    role: Role
    reason: str


def parse_role(value: str) -> Role:
    key = value.strip()
    role = _ROLE_ALIASES.get(key) or _ROLE_ALIASES.get(key.lower())
    if role is None:
        raise ValueError(key)
    return role


def infer_role(
    name: str,
    duckdb_type: str,
    *,
    distinct_count: int,
    non_null_count: int,
    is_primary_key: bool = False,
) -> RoleDecision:
    """按固定顺序判断一列的角色。"""

    if _is_identifier_name(name):
        return RoleDecision(Role.IDENTIFIER, "列名像标识（id、_id、uuid 或 guid）。")
    if is_primary_key:
        return RoleDecision(Role.IDENTIFIER, "这一列是主键，当作标识。")

    base = _base_type(duckdb_type)
    if _is_temporal(base):
        return RoleDecision(Role.TIME, "这一列是日期或时间。")
    if _is_dimension_name(name):
        return RoleDecision(Role.DIMENSION, "列名像年份、邮编、编码、评分或等级，当作维度。")
    if base in _NUMERIC:
        if _low_cardinality(distinct_count, non_null_count):
            return RoleDecision(Role.DIMENSION, "数值列的不重复值很少，当作维度。")
        return RoleDecision(Role.MEASURE, "数值列可以做求和或平均，当作度量。")
    if base in _BOOLEAN:
        return RoleDecision(Role.DIMENSION, "布尔列当作维度。")
    if base in _STRING:
        return RoleDecision(Role.DIMENSION, "文本列当作维度。")
    return RoleDecision(Role.UNKNOWN, f"这个类型无法判断角色：{duckdb_type}。")


def _is_identifier_name(name: str) -> bool:
    lowered = name.lower()
    return (
        lowered in _IDENTIFIER_EXACT
        or lowered.endswith("_id")
        or "uuid" in lowered
        or "guid" in lowered
    )


def _is_dimension_name(name: str) -> bool:
    if any(token in name for token in _DIMENSION_ZH):
        return True
    parts = name.lower().replace("-", "_").split("_")
    return any(part in _DIMENSION_TOKENS for part in parts)


def _low_cardinality(distinct_count: int, non_null_count: int) -> bool:
    if distinct_count <= _LOW_DISTINCT:
        return True
    if non_null_count < _MIN_NON_NULL_FOR_RATIO or non_null_count == 0:
        return False
    return distinct_count / non_null_count <= _LOW_RATIO


def _base_type(duckdb_type: str) -> str:
    return duckdb_type.upper().split("(", 1)[0].strip()


def _is_temporal(base: str) -> bool:
    if base.startswith("TIMESTAMP") or base.startswith("DATETIME") or base.startswith("DATE"):
        return True
    return base == "TIME" or base.startswith("TIME ")
