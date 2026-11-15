from pathlib import Path

import pytest

from tableprobe import open_table
from tableprobe.errors import TableProbeError

FIXTURES = Path(__file__).parent / "fixtures"
ORDERS = Path(__file__).parents[1] / "examples" / "orders.csv"


def test_profile_matches_column_count_and_records_sample_size():
    table = open_table(FIXTURES / "small.csv")
    profile = table.profile()
    assert table.column_count() == len(profile)
    assert {column.sample_rows for column in profile} == {2}
    assert [column.name for column in profile] == ["city", "amount"]


def test_empty_table_has_columns_but_an_empty_profile():
    table = open_table(FIXTURES / "empty.csv")
    assert table.row_count() == 0
    assert table.column_count() == 2
    assert table.profile() == []
    assert table.dimensions() == []


def test_all_null_column_has_full_null_rate_and_zero_cardinality():
    table = open_table(FIXTURES / "nulls.csv")
    note = next(column for column in table.profile() if column.name == "note")
    assert note.distinct_count == 0
    assert note.null_rate == pytest.approx(1)


def test_sqlite_primary_key_and_measure(tmp_path):
    import sqlite3

    database_path = tmp_path / "shop.db"
    database = sqlite3.connect(database_path)
    database.execute("CREATE TABLE products (sku INTEGER PRIMARY KEY, price INTEGER)")
    database.executemany(
        "INSERT INTO products VALUES (?, ?)",
        [(index, 1000 + index) for index in range(1, 31)],
    )
    database.commit()
    database.close()

    profile = {column.name: column for column in open_table(database_path, table="products").profile()}
    assert profile["sku"].role == "标识"
    assert "主键" in profile["sku"].reason
    assert profile["price"].role == "度量"


def test_set_role_updates_only_the_current_table():
    table = open_table(ORDERS)
    assert "金额" in table.measures()
    table.set_role("金额", "维度")
    assert "金额" in table.dimensions()
    assert "金额" not in table.measures()
    assert "金额" not in table.times()
    assert "金额" not in table.identifiers()
    amount = next(column for column in table.profile() if column.name == "金额")
    assert amount.reason == "课堂上手工指定。"
    region = next(column for column in table.profile() if column.name == "地区")
    assert region.reason != "课堂上手工指定。"

    table.set_role("金额", "time")
    assert table.times() == ["金额", "下单日期"]


def test_set_role_rejects_unknown_column_and_role():
    table = open_table(FIXTURES / "small.csv")
    with pytest.raises(TableProbeError, match="没有这一列"):
        table.set_role("missing", "维度")
    with pytest.raises(TableProbeError, match="角色只能是"):
        table.set_role("city", "标签")


def test_classroom_orders_have_the_expected_roles():
    profile = {column.name: column for column in open_table(ORDERS).profile()}
    assert profile["金额"].role == "度量"
    assert profile["地区"].role == "维度"
    assert profile["下单日期"].role == "时间"
    assert profile["user_id"].role == "标识"
    assert profile["年份"].role == "维度"
    assert profile["评分"].role == "维度"
    assert "列名像年份" in profile["年份"].reason
    assert "评分" in profile["评分"].reason
