import sqlite3

DB_PATH = "db/eatfresh.db"


def check_shortage(needs):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    shortages = []
    for need in needs:
        row = conn.execute(
            "SELECT SUM(quantity) AS total FROM ingredients WHERE name = ? AND unit = ?",
            (need["name"], need["unit"]),
        ).fetchone()

        have = row["total"] or 0
        if have < need["quantity"]:
            shortages.append({
                "name": need["name"],
                "need": need["quantity"],
                "have": have,
                "lack": need["quantity"] - have,
                "unit": need["unit"],
            })

    conn.close()
    return shortages


def complete_cooking(needs):
    shortages = check_shortage(needs)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    for need in needs:
        left = need["quantity"]

        rows = conn.execute(
            "SELECT id, quantity FROM ingredients "
            "WHERE name = ? AND unit = ? AND quantity > 0 "
            "ORDER BY expiry_date",
            (need["name"], need["unit"]),
        ).fetchall()

        for row in rows:
            if left <= 0:
                break
            use = min(row["quantity"], left)
            conn.execute(
                "UPDATE ingredients SET quantity = quantity - ? WHERE id = ?",
                (use, row["id"]),
            )
            left = left - use

    conn.commit()
    conn.close()

    return {"completed": True, "shortages": shortages}