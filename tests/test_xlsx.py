from pathlib import Path

import duckdb
import pytest

from tableprobe import open_table
from tableprobe.errors import TableProbeError
from tableprobe.profile import ColumnProfile
from tests.xlsx_factory import worksheet, write_xlsx

FIELDS = [field.name for field in ColumnProfile.__dataclass_fields__.values()]


def test_xls_is_rejected_before_looking_for_the_file():
    with pytest.raises(TableProbeError, match="不支持旧版 .xls"):
        open_table("grades.xls")


def test_merged_cells_and_blank_headers_are_rejected(tmp_path):
    merged = tmp_path / "merged.xlsx"
    write_xlsx(merged, [("Q1", worksheet([["城市", "金额"], ["上海", "10"]], merges=["A1:B1"]))])
    with pytest.raises(TableProbeError, match="合并单元格"):
        open_table(merged)

    blank = tmp_path / "blank.xlsx"
    write_xlsx(blank, [("Q1", worksheet([["城市", None], ["上海", "10"]]))])
    with pytest.raises(TableProbeError, match="空列名"):
        open_table(blank)

    second = tmp_path / "second.xlsx"
    write_xlsx(
        second,
        [
            ("Q1", worksheet([["城市"], ["上海"]])),
            ("Q2", worksheet([["城市", "金额"], ["上海", "10"]], merges=["A1:A2"])),
        ],
    )
    with pytest.raises(TableProbeError, match="合并单元格"):
        open_table(second, sheet="Q2")
    with pytest.raises(TableProbeError, match="不存在"):
        open_table(second, sheet="Q3")


def test_rectangular_xlsx_matches_csv_profile_shape(tmp_path):
    connection = duckdb.connect()
    try:
        connection.execute("INSTALL excel")
        connection.execute("LOAD excel")
    except Exception as exc:
        pytest.skip(f"DuckDB excel 扩展不可用：{exc}")
    finally:
        connection.close()

    path = tmp_path / "orders.xlsx"
    write_xlsx(path, [("Q1", worksheet([["city", "amount"], ["上海", "12"]]))])
    assert open_table(path).row_count() == 1
    table = open_table(path, sheet="Q1")
    assert table.row_count() == 1
    assert table.column_count() == 2
    profile = table.profile()
    assert [column.name for column in profile] == ["city", "amount"]
    assert list(profile[0].__dataclass_fields__) == FIELDS
    csv_profile = open_table(Path(__file__).parent / "fixtures" / "small.csv").profile()
    assert list(csv_profile[0].__dataclass_fields__) == list(profile[0].__dataclass_fields__)
