"""抽样统计。不把整表拉进 Python。"""

from __future__ import annotations

from dataclasses import dataclass

from tableprobe.sql import quote_ident

SAMPLE_LIMIT = 10_000


@dataclass(frozen=True)
class ColumnStat:
    name: str
    duckdb_type: str
    null_rate: float
    distinct_count: int
    non_null_count: int
    sample_rows: int
    is_primary_key: bool


@dataclass(frozen=True)
class ColumnProfile:
    """一列的画像。role 取维度、度量、时间、标识或未知。"""

    name: str
    duckdb_type: str
    null_rate: float
    distinct_count: int
    sample_rows: int
    role: str
    reason: str

    def __str__(self) -> str:
        return (
            f"{self.name}\t{self.duckdb_type}\t"
            f"空值率 {self.null_rate:.0%}\t"
            f"基数 {self.distinct_count}\t"
            f"抽样 {self.sample_rows} 行\t"
            f"{self.role}\t{self.reason}"
        )


def collect_stats(connection, columns: list[tuple[str, str, bool]]) -> list[ColumnStat]:
    """对最多 10000 行的抽样计算每列的空值率和基数。"""

    if not columns:
        return []

    pieces = ["COUNT(*) AS sample_rows"]
    for index, (name, _, _) in enumerate(columns):
        ident = quote_ident(name)
        pieces.append(f"COUNT({ident}) AS non_null_{index}")
        pieces.append(f"COUNT(DISTINCT {ident}) AS distinct_{index}")
    sql = (
        "SELECT "
        + ", ".join(pieces)
        + f" FROM (SELECT * FROM probe_table USING SAMPLE {SAMPLE_LIMIT} ROWS)"
    )
    row = connection.execute(sql).fetchone()
    sample_rows = int(row[0])
    stats: list[ColumnStat] = []
    for index, (name, duckdb_type, is_primary_key) in enumerate(columns):
        non_null = int(row[1 + index * 2])
        distinct = int(row[2 + index * 2])
        null_rate = 0.0 if sample_rows == 0 else (sample_rows - non_null) / sample_rows
        stats.append(
            ColumnStat(
                name=name,
                duckdb_type=duckdb_type,
                null_rate=null_rate,
                distinct_count=distinct,
                non_null_count=non_null,
                sample_rows=sample_rows,
                is_primary_key=is_primary_key,
            )
        )
    return stats
