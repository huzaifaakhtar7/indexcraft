import sqlite3

from data.generate_data import main, sizes


def counts(path):
    conn = sqlite3.connect(path)
    out = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
           for t in ["categories", "products", "customers", "orders", "order_items"]}
    first = conn.execute("SELECT * FROM orders WHERE order_id = 1").fetchone()
    conn.close()
    return out, first


def test_sqlite_load_is_complete_and_repeatable(tmp_path):
    a, b = tmp_path / "a.db", tmp_path / "b.db"
    main(["--db", "sqlite", "--scale", "0.002", "--sqlite-path", str(a)])
    main(["--db", "sqlite", "--scale", "0.002", "--sqlite-path", str(b)])
    rows_a, first_a = counts(a)
    rows_b, first_b = counts(b)
    assert rows_a == sizes(0.002) == {"categories": 50, "products": 1000, "customers": 200,
                                      "orders": 2000, "order_items": 4000}
    assert rows_a == rows_b and first_a == first_b
    assert len(first_a[4]) == 10
