import sqlite3
from pathlib import Path

import duckdb
import pytest

from tableprobe import open_table
from tableprobe.errors import TableProbeError

FIXTURES = Path(__file__).parent / "fixtures"


def test_csv_parquet_and_sqlite_report_counts(tmp_path):
    csv_table = open_table(FIXTURES / "small.csv")
    assert csv_table.row_count() == 2
    assert csv_table.column_count() == 2

    parquet_path = tmp_path / "people.parquet"
    connection = duckdb.connect()
    connection.execute(
        "COPY (SELECT 1 AS id, 'a' AS city UNION ALL SELECT 2, 'b') "
        f"TO '{parquet_path}' (FORMAT parquet)"
    )
    connection.close()
    parquet_table = open_table(parquet_path)
    assert parquet_table.row_count() == 2
    assert parquet_table.column_count() == 2

    database_path = tmp_path / "app.db"
    database = sqlite3.connect(database_path)
    database.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    database.executemany("INSERT INTO users VALUES (?, ?)", [(1, "甲"), (2, "乙")])
    database.commit()
    database.close()
    sqlite_table = open_table(f"sqlite:///{database_path}", table="users")
    assert sqlite_table.row_count() == 2
    assert sqlite_table.column_count() == 2
    assert open_table(database_path, table="users").row_count() == 2


def test_sqlite_requires_a_table_name(tmp_path):
    database_path = tmp_path / "app.sqlite"
    sqlite3.connect(database_path).close()
    with pytest.raises(TableProbeError, match="必须传入 table"):
        open_table(database_path)


def test_missing_file_and_unknown_source(tmp_path):
    with pytest.raises(TableProbeError, match="找不到文件"):
        open_table(tmp_path / "missing.csv")
    with pytest.raises(TableProbeError, match="无法识别"):
        open_table("postgres://localhost/shop")


def test_context_manager_closes_the_table():
    with open_table(FIXTURES / "small.csv") as table:
        assert table.row_count() == 2
    with pytest.raises(TableProbeError, match="已经关闭"):
        table.row_count()
