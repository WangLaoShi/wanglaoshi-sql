"""一张表：精确行数、列数，以及抽样后的列角色。"""

from __future__ import annotations

import duckdb

from tableprobe.errors import TableProbeError, redact
from tableprobe.open import OpenRequest, view_sql
from tableprobe.profile import ColumnProfile, collect_stats
from tableprobe.roles import MANUAL_REASON, ROLE_LABELS, Role, infer_role, parse_role
from tableprobe.xlsx_check import prepare_sheet


class Table:
    """一个数据源里的一张表。一个对象持有一条 DuckDB 连接。"""

    def __init__(self, request: OpenRequest) -> None:
        self._request = request
        self._con = duckdb.connect()
        self._columns: list[tuple[str, str, bool]] = []
        self._overrides: dict[str, Role] = {}
        self._stats = None
        try:
            self._load()
        except Exception:
            self.close()
            raise

    def row_count(self) -> int:
        """精确行数，使用 COUNT(*)。"""

        row = self._execute("SELECT COUNT(*) FROM probe_table").fetchone()
        return int(row[0])

    def column_count(self) -> int:
        self._require_open()
        return len(self._columns)

    def profile(self) -> list[ColumnProfile]:
        """每列的类型、抽样空值率、抽样基数、抽样行数和角色。空表返回空列表。"""

        self._require_open()
        if self._stats is None:
            if self.row_count() == 0:
                self._stats = []
            else:
                try:
                    self._stats = collect_stats(self._con, self._columns)
                except TableProbeError:
                    raise
                except Exception as exc:
                    raise TableProbeError("读取数据失败：" + redact(str(exc))) from exc
        profiles: list[ColumnProfile] = []
        for stat in self._stats:
            if stat.name in self._overrides:
                role = self._overrides[stat.name]
                reason = MANUAL_REASON
            else:
                decision = infer_role(
                    stat.name,
                    stat.duckdb_type,
                    distinct_count=stat.distinct_count,
                    non_null_count=stat.non_null_count,
                    is_primary_key=stat.is_primary_key,
                )
                role = decision.role
                reason = decision.reason
            profiles.append(
                ColumnProfile(
                    name=stat.name,
                    duckdb_type=stat.duckdb_type,
                    null_rate=stat.null_rate,
                    distinct_count=stat.distinct_count,
                    sample_rows=stat.sample_rows,
                    role=ROLE_LABELS[role],
                    reason=reason,
                )
            )
        return profiles

    def set_role(self, column: str, role: str) -> None:
        """只改当前这个表对象上某一列的角色。"""

        self._require_open()
        if column not in {name for name, _, _ in self._columns}:
            raise TableProbeError(f"没有这一列：{column}")
        try:
            parsed = parse_role(role)
        except ValueError:
            raise TableProbeError("角色只能是维度、度量、时间或标识。") from None
        self._overrides[column] = parsed

    def dimensions(self) -> list[str]:
        return self._names(Role.DIMENSION)

    def measures(self) -> list[str]:
        return self._names(Role.MEASURE)

    def times(self) -> list[str]:
        return self._names(Role.TIME)

    def identifiers(self) -> list[str]:
        return self._names(Role.IDENTIFIER)

    def close(self) -> None:
        if self._con is not None:
            self._con.close()
            self._con = None

    def __enter__(self) -> Table:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def __repr__(self) -> str:
        if self._con is None:
            return "Table(已关闭)"
        return f"Table({self._request.label})"

    def _load(self) -> None:
        sheet_name = None
        if self._request.kind == "xlsx":
            sheet_name = prepare_sheet(self._request.path or "", self._request.sheet)
            self._ensure_extension("excel")
        elif self._request.kind == "mysql":
            self._ensure_extension("mysql")
        for statement in view_sql(self._request, sheet_name):
            self._execute(statement)
        described = self._execute("DESCRIBE probe_table").fetchall()
        columns: list[tuple[str, str, bool]] = []
        for row in described:
            name = "" if row[0] is None else str(row[0])
            if not name.strip():
                raise TableProbeError("这个表的第一行有空列名，不是矩形表。")
            columns.append((name, str(row[1]), row[3] == "PRI"))
        self._columns = columns

    def _ensure_extension(self, name: str) -> None:
        try:
            self._con.execute(f"INSTALL {name}")
            self._con.execute(f"LOAD {name}")
        except Exception as exc:
            raise TableProbeError(
                f"加载 DuckDB 的 {name} 扩展失败。上课时请先确认这台电脑能联网。"
                + redact(str(exc))
            ) from exc

    def _names(self, role: Role) -> list[str]:
        label = ROLE_LABELS[role]
        return [column.name for column in self.profile() if column.role == label]

    def _execute(self, sql: str):
        self._require_open()
        try:
            return self._con.execute(sql)
        except TableProbeError:
            raise
        except Exception as exc:
            raise TableProbeError("读取数据失败：" + redact(str(exc))) from exc

    def _require_open(self) -> None:
        if self._con is None:
            raise TableProbeError("这个表已经关闭。")
