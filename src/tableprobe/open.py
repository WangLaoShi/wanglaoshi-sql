"""打开一种数据源，并把它落成同一张 DuckDB 视图。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from tableprobe.errors import TableProbeError, redact
from tableprobe.sql import quote_ident, sql_literal


@dataclass(frozen=True)
class OpenRequest:
    kind: str
    label: str
    path: str | None = None
    table: str | None = None
    sheet: str | None = None
    mysql_host: str | None = None
    mysql_port: int | None = None
    mysql_user: str | None = None
    mysql_password: str | None = None
    mysql_database: str | None = None


def open_table(
    source: str | os.PathLike[str],
    *,
    table: str | None = None,
    sheet: str | None = None,
):
    """打开 CSV、Parquet、SQLite、xlsx 或 MySQL 里的一张表。"""

    request = parse_source(source, table=table, sheet=sheet)
    from tableprobe.table import Table

    return Table(request)


def parse_source(
    source: str | os.PathLike[str],
    *,
    table: str | None,
    sheet: str | None,
) -> OpenRequest:
    raw = os.fspath(source)
    if raw.startswith("mysql://"):
        return _parse_mysql(raw, table=table, sheet=sheet)
    if raw.startswith("sqlite:"):
        return _parse_sqlite_uri(raw, table=table, sheet=sheet)

    path = Path(raw).expanduser()
    suffix = path.suffix.lower()
    if suffix == ".xls":
        raise TableProbeError("不支持旧版 .xls，请另存为 .xlsx。")
    if suffix in {".csv", ".parquet", ".xlsx", ".db", ".sqlite", ".sqlite3"}:
        if not path.is_file():
            raise TableProbeError(f"找不到文件：{path}")
        resolved = str(path.resolve())
        if suffix == ".csv":
            _reject_table_and_sheet(table, sheet)
            return OpenRequest(kind="csv", label=resolved, path=resolved)
        if suffix == ".parquet":
            _reject_table_and_sheet(table, sheet)
            return OpenRequest(kind="parquet", label=resolved, path=resolved)
        if suffix == ".xlsx":
            if table:
                raise TableProbeError("只有 SQLite 和 MySQL 需要传入 table。")
            return OpenRequest(kind="xlsx", label=resolved, path=resolved, sheet=sheet)
        _require_table(table, "SQLite")
        if sheet is not None:
            raise TableProbeError("只有 xlsx 可以指定 sheet。")
        return OpenRequest(kind="sqlite", label=resolved, path=resolved, table=table)
    raise TableProbeError("无法识别这个数据源。支持 CSV、Parquet、SQLite、xlsx 和 MySQL。")


def mysql_attach_sql(request: OpenRequest) -> str:
    parts = [
        _mysql_token("host", request.mysql_host or ""),
        f"port={request.mysql_port}",
        _mysql_token("user", request.mysql_user or ""),
        _mysql_token("password", request.mysql_password or ""),
        _mysql_token("database", request.mysql_database or ""),
        "connect_timeout=5",
    ]
    return "ATTACH " + sql_literal(" ".join(parts)) + " AS src (TYPE mysql)"


def view_sql(request: OpenRequest, sheet_name: str | None = None) -> list[str]:
    """返回按顺序执行的 SQL。最后一张视图名固定为 probe_table。"""

    if request.kind == "csv":
        return [
            "CREATE VIEW probe_table AS SELECT * FROM read_csv_auto("
            + sql_literal(request.path or "")
            + ")"
        ]
    if request.kind == "parquet":
        return [
            "CREATE VIEW probe_table AS SELECT * FROM read_parquet("
            + sql_literal(request.path or "")
            + ")"
        ]
    if request.kind == "sqlite":
        return [
            "ATTACH "
            + sql_literal(request.path or "")
            + " AS src (TYPE sqlite)",
            "CREATE VIEW probe_table AS SELECT * FROM src." + quote_ident(request.table or ""),
        ]
    if request.kind == "xlsx":
        options = "header = true"
        if sheet_name:
            options += ", sheet = " + sql_literal(sheet_name)
        return [
            "CREATE VIEW probe_table AS SELECT * FROM read_xlsx("
            + sql_literal(request.path or "")
            + ", "
            + options
            + ")"
        ]
    return [
        mysql_attach_sql(request),
        "CREATE VIEW probe_table AS SELECT * FROM src." + quote_ident(request.table or ""),
    ]


def _parse_mysql(raw: str, *, table: str | None, sheet: str | None) -> OpenRequest:
    if sheet is not None:
        raise TableProbeError("只有 xlsx 可以指定 sheet。")
    _require_table(table, "MySQL")
    parsed = urlparse(raw)
    database = unquote(parsed.path.lstrip("/"))
    if (
        parsed.scheme != "mysql"
        or not parsed.hostname
        or not database
        or "/" in database
        or parsed.username is None
    ):
        raise TableProbeError("MySQL 连接串应为 mysql://用户:密码@主机:端口/库名。")
    password = unquote(parsed.password) if parsed.password is not None else ""
    user = unquote(parsed.username)
    host = parsed.hostname
    port = parsed.port or 3306
    label = f"mysql://{user}:***@{host}:{port}/{database}"
    return OpenRequest(
        kind="mysql",
        label=redact(label),
        table=table,
        mysql_host=host,
        mysql_port=port,
        mysql_user=user,
        mysql_password=password,
        mysql_database=database,
    )


def _parse_sqlite_uri(raw: str, *, table: str | None, sheet: str | None) -> OpenRequest:
    if not raw.startswith("sqlite:///"):
        raise TableProbeError("SQLite 连接串应为 sqlite:///文件路径。")
    if sheet is not None:
        raise TableProbeError("只有 xlsx 可以指定 sheet。")
    _require_table(table, "SQLite")
    file_path = Path(raw.removeprefix("sqlite:///")).expanduser()
    if not file_path.is_file():
        raise TableProbeError(f"找不到文件：{file_path}")
    resolved = str(file_path.resolve())
    return OpenRequest(kind="sqlite", label=resolved, path=resolved, table=table)


def _require_table(table: str | None, kind: str) -> None:
    if not table:
        raise TableProbeError(f"打开 {kind} 时必须传入 table。")


def _reject_table_and_sheet(table: str | None, sheet: str | None) -> None:
    if table:
        raise TableProbeError("只有 SQLite 和 MySQL 需要传入 table。")
    if sheet is not None:
        raise TableProbeError("只有 xlsx 可以指定 sheet。")


def _mysql_token(key: str, value: str) -> str:
    if any(character.isspace() or character in "'\"=" for character in value):
        label = {"host": "主机", "user": "用户名", "password": "密码", "database": "库名"}.get(
            key, key
        )
        raise TableProbeError(f"MySQL 的{label}里先不要使用空格、等号或引号。")
    return f"{key}={value}"
