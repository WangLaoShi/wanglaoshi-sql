from pathlib import Path

from tableprobe import open_table

orders = open_table(Path(__file__).with_name("orders.csv"))
print(orders.row_count())
print(orders.column_count())
for column in orders.profile():
    print(column)
