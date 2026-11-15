# tableprobe 范围说明

仓库名是 `wanglaoshi-sql`。PyPI 包名是 `tableprobe`。这是一个供上课演示的 Python 库：把 CSV、Parquet、xlsx 的一个工作表、SQLite 的一张表、MySQL 的一张表，变成同一个 `Table` 对象，并回答行数、列数，以及每一列是维度、度量、时间，还是标识。

文档和示例用中文。调用要短，能在课堂上当场敲完。

Parquet 与 CSV、SQLite 同为第一版的本地来源，用 DuckDB 自带的 `read_parquet` 读取，不额外安装扩展，也不依赖 pyarrow。

## 这个库做什么

调用方面对的是「一张表」，不是「一个数据库连接」。连接只负责把表打开。

```python
from tableprobe import open_table

orders = open_table("sales.csv")
orders = open_table("sales.parquet")
orders = open_table("sqlite:///app.db", table="users")
orders = open_table("book.xlsx", sheet="Q1")
orders = open_table("mysql://user:pass@host:3306/shop", table="orders")

orders.row_count()
orders.column_count()
orders.profile()
orders.dimensions()
orders.measures()
orders.times()
orders.identifiers()
```

PyPI 上已有 [`wanglaoshi`](https://pypi.org/project/wanglaoshi/)（数据分析入门与竞赛工具包）。本库使用 `tableprobe`，不沿用那个名字。

## 和现成项目的分工

连接和查询已经有成熟实现，本库不重写驱动。

| 已有项目 | 它负责的部分 | 本库不重复的原因 |
| --- | --- | --- |
| [DuckDB](https://duckdb.org/) | 读取 CSV、Parquet、xlsx，挂载 SQLite、MySQL，并用同一套 SQL 做 `COUNT(*)`、`DESCRIBE` | 没有「维度 / 度量」这一层，调用方仍要写 SQL |
| [Ibis](https://github.com/ibis-project/ibis) | 用同一套 Python API 查询 MySQL、SQLite、DuckDB 等二十多个后端 | Excel 不是一等公民；列角色要调用方自己判断 |
| SQLAlchemy、`records` | 连接关系型数据库并执行 SQL | 不覆盖 CSV、Excel、Parquet |
| [Frictionless](https://pypi.org/project/frictionless/) | 描述并校验文件和 SQL 表的 schema | 有字段类型，没有分析语义 |
| [semql-introspect](https://pypi.org/project/semql-introspect/)、[Cantrip](https://pypi.org/project/cantrip/) | 从数仓 schema 推断度量、维度、时间维度 | 面向语义层代码生成，不读 Excel、CSV，也不回答「这张表有多少行」 |
| [Woodwork](https://woodwork.alteryx.com/) | 给已载入内存的 DataFrame 打 `numeric`、`category` 标签 | 不负责打开数据源 |

执行引擎只用 DuckDB。CSV 用 `read_csv_auto`，Parquet 用 `read_parquet`，xlsx 用 `read_xlsx`，SQLite 和 MySQL 用 `ATTACH`。五类来源最后都落成同一张视图。筛选、分组、聚合交给 Ibis 或 DuckDB。第一版没有 `head`、过滤、分组和画图。

## 第一版范围

五类来源：

- CSV
- Parquet
- xlsx 的一个工作表，且是第一行为列名的矩形表。没写 `sheet` 时用第一张工作表
- SQLite 的一张表。路径可以是 `.db`、`.sqlite`、`.sqlite3`，也可以是 `sqlite:///文件路径`，并且必须传入 `table`
- MySQL 的一张表。连接串是 `mysql://用户:密码@主机:端口/库名`，并且必须传入 `table`

接口：

- `row_count()`：精确行数，始终是 `COUNT(*)`
- `column_count()`：来自 `DESCRIBE` 的列数
- `profile()`：逐列的名字、DuckDB 类型、抽样空值率、抽样基数、抽样行数、角色和理由
- `dimensions()`、`measures()`、`times()`、`identifiers()`：按角色返回列名
- `set_role(column, role)`：只改当前对象。角色可以写 `维度`、`度量`、`时间`、`标识`，或对应的英文。理由改为「课堂上手工指定。」

空表（有列但 0 行）的 `profile()` 返回空列表，`column_count()` 仍返回列数。全空列的基数为 0，空值率为 1。

依赖按来源拆开。默认安装覆盖 CSV、Parquet、SQLite 和 xlsx 的读取代码；`pip install tableprobe[mysql]` 目前是预留标记，没有额外的 Python 包。xlsx 和 MySQL 第一次打开时，由 DuckDB 下载 `excel` 或 `mysql` 扩展，电脑需要能联网。

大表禁止为了分类做全表扫描。空值率和基数来自 `USING SAMPLE 10000 ROWS`，小表会覆盖全表，结果里仍写明抽样行数。行数使用精确 `COUNT(*)`。MySQL 大表上精确计数可能很慢；`information_schema` 中的行数是估算，不作为精确行数返回。

报错用中文。连接串和报错文本里的密码会打码。SQLite 能通过 `DESCRIBE` 看到主键时，该列标为标识。

## 第一版不做

- 自研数据库驱动、ORM、SQL 生成器
- 把整表载入内存再计数
- 跨表 JOIN、写回、ETL、画图
- xlsx 的多表头、合并单元格，以及旧版 `.xls`
- 在文档或介绍中承诺「支持所有数据库」

合并单元格、空列名和 `.xls` 直接给出中文错误。Postgres 可以后加：DuckDB 已经能挂载它，但未验证之前不写入支持列表。

## 列角色

列角色由库自动判断。判断会错，课堂上可以接受；`profile()` 仍给出一句中文理由。老师可以用 `set_role` 当场改一列，再看四个筛选方法的变化。

判断是纯函数，不连接数据库。先命中先停：

1. 列名是 `id`、以 `_id` 结尾，或含 `uuid` / `guid`，标为标识。SQLite 主键同样标为标识。
2. 日期或时间类型标为时间。
3. 列名像年份、邮编、编码、评分、等级（以及英文 `year`、`zip`、`code`、`rating`、`score`、`level`、`grade`），即使是数字也标为维度。
4. 数值列中，不重复值不超过 20，或不重复值占非空值不超过 5% 且非空值至少 20 个，标为维度；其余标为度量。
5. 布尔和字符串标为维度。
6. 其余标为未知，并写明类型。

年份、邮编、1–5 分的评分、`user_id` 即使是数字，也不标成度量。

## 已定

- 用途：上课演示。文档用中文，示例保持能当场敲完的长度。
- 列角色：自动判断。错了可以接受，理由要能讲出来，并可用 `set_role` 当场改正。
- 发布名：PyPI 包名 `tableprobe`，导入 `from tableprobe import open_table`。仓库名仍是 `wanglaoshi-sql`。
