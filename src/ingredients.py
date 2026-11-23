import sqlite3

DB_PATH = "db/eatfresh.db"


def get_ingredients():

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row


    rows = conn.execute(
        "SELECT * FROM ingredients WHERE quantity > 0 ORDER BY expiry_date"
    ).fetchall()


    conn.close()


    result = []
    for row in rows:
        result.append(dict(row))


    return result