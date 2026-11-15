import os

import pytest

from tableprobe import open_table
from tableprobe.errors import TableProbeError, redact
from tableprobe.profile import ColumnProfile


def test_redact_hides_passwords_in_urls_and_attach_errors():
    hidden = redact(
        'Failed parameters "host=127.0.0.1 user=teacher password=s3cret database=shop"'
    )
    assert "s3cret" not in hidden
    assert "s3cret" not in redact("mysql://teacher:s3cret@localhost/shop")


def test_mysql_requires_a_table_and_a_full_url():
    with pytest.raises(TableProbeError, match="必须传入 table"):
        open_table("mysql://teacher:s3cret@127.0.0.1:3306/shop")
    with pytest.raises(TableProbeError, match="连接串应为"):
        open_table("mysql://127.0.0.1/shop", table="orders")


def test_mysql_errors_do_not_include_the_password(monkeypatch):
    class Connection:
        def execute(self, sql):
            if sql.startswith("INSTALL") or sql.startswith("LOAD"):
                return self
            raise RuntimeError(sql)

        def close(self):
            return None

    monkeypatch.setattr("tableprobe.table.duckdb.connect", lambda: Connection())
    with pytest.raises(TableProbeError) as caught:
        open_table("mysql://teacher:s3cret@127.0.0.1:3306/shop", table="orders")
    assert "s3cret" not in str(caught.value)
    assert "***" in str(caught.value)


@pytest.mark.skipif(not os.environ.get("MYSQL_URL"), reason="未设置 MYSQL_URL")
def test_live_mysql_profile_has_the_same_fields_as_csv():
    table_name = os.environ.get("MYSQL_TABLE")
    if not table_name:
        pytest.skip("未设置 MYSQL_TABLE")
    table = open_table(os.environ["MYSQL_URL"], table=table_name)
    if table.row_count() == 0:
        assert table.profile() == []
        return
    profile = table.profile()
    assert len(profile) == table.column_count()
    assert list(profile[0].__dataclass_fields__) == list(ColumnProfile.__dataclass_fields__)
