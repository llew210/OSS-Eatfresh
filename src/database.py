import sqlite3

conn = sqlite3.connect("db/eatfresh.db")

file = open("db/schema.sql", encoding="utf-8")
sql = file.read()
file.close()

conn.executescript(sql)
conn.commit()
conn.close()

print("완료")
