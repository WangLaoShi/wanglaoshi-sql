# tableprobe

上课时用的表探查库。把 CSV、Parquet、SQLite、xlsx 和 MySQL 里的一张表收成同一个对象，然后回答三件事：有多少行、有多少列、每一列是维度、度量、时间还是标识。

```python
from tableprobe import open_table

orders = open_table("examples/orders.csv")
print(orders.row_count())
print(orders.column_count())
for column in orders.profile():
    print(column)
```

仓库里的 `python examples/demo.py` 就是这段调用。范围和取舍写在 [docs/spec.md](docs/spec.md)。

## 安装

发布到 PyPI 之后：

```bash
pip install tableprobe
```

在本仓库里试用：

```bash
pip install -e .
```

CSV、Parquet 和 SQLite 装完就能打开。xlsx 和 MySQL 第一次使用时，DuckDB 会下载对应扩展，电脑需要能联网。`pip install tableprobe[mysql]` 是预留的安装标记，目前没有额外的 Python 包。

CSV 请存成 UTF-8。

## 打开一张表

```python
from tableprobe import open_table

open_table("sales.csv")
open_table("sales.parquet")
open_table("sqlite:///app.db", table="users")
open_table("book.xlsx", sheet="Q1")          # 不写 sheet 就用第一张工作表
open_table("mysql://user:pass@host:3306/shop", table="orders")
```

SQLite 和 MySQL 必须传入 `table`。一个 `Table` 持有一条连接，用完可以 `close()`，也可以写在 `with` 里。

## 行数、列数和画像

`row_count()` 永远是精确的 `COUNT(*)`。`column_count()` 是列数。

`profile()` 的每一列有名字、类型、抽样空值率、抽样基数、抽样行数、角色和一句理由。空值率和基数最多只看 10000 行；小文件会看完全部行，结果里仍写着抽样行数，所以它不是另一套全表精确统计。MySQL 系统表里的估计行数不会拿来冒充 `row_count()`。

有列但一行都没有的表，`profile()` 返回空列表。某一列全是空值时，基数是 0，空值率是 1。

## 维度和度量

角色由库自动判断，错了可以接受。理由用来讲「为什么判成这样」。

| 角色 | 怎么看出来 |
| --- | --- |
| 标识 | 列名是 `id`、以 `_id` 结尾、含 `uuid` 或 `guid`，或者这一列是 SQLite 主键 |
| 时间 | 日期或时间类型 |
| 维度 | 文本、布尔、低基数的数字，以及列名像年份、邮编、编码、评分、等级 |
| 度量 | 其余适合求和或平均的数字 |
| 未知 | 对不上上面几条，理由里会写出类型 |

`dimensions()`、`measures()`、`times()` 和 `identifiers()` 按角色返回列名。课堂上要改一列：

```python
orders.set_role("金额", "维度")
orders.dimensions()
```

这一改只存在于当前这个对象，理由变成「课堂上手工指定。」

## 第一版不读什么

旧版 `.xls`、带合并单元格的工作表、第一行有空列名的表，都会直接用中文报错。不做查询、写回和画图。

报错里的 MySQL 密码会打成 `***`。
