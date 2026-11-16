-- EatFresh 냉장고 식재료 테이블

CREATE TABLE IF NOT EXISTS ingredients (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    quantity      REAL    NOT NULL CHECK (quantity >= 0),
    unit          TEXT    NOT NULL CHECK (unit IN ('g', '개')),
    storage       TEXT    NOT NULL DEFAULT '냉장'
                          CHECK (storage IN ('냉장', '냉동', '실온')),
    purchase_date TEXT,
    expiry_date   TEXT
);