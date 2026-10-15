import os
import random
import sqlite3
from datetime import date, timedelta

import pytest

from adapters.factory import get_adapter
from core.analyzer import analyze, test_suggestion as run_test

N_CUSTOMERS = 2_000
N_ORDERS = 30_000


def build_shop(path):
    rng = random.Random(7)
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, name TEXT, email TEXT,
                                city TEXT, signup_date TEXT);
        CREATE TABLE orders (order_id INTEGER PRIMARY KEY, customer_id INTEGER, status TEXT,
                             total_amount REAL, order_date TEXT);
    """)
    cities = ["Karachi", "Lahore", "Multan", "Quetta"]
    conn.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?)", [
        (i, f"Name {i}", f"c{i}@example.com", rng.choice(cities), "2021-01-01")
        for i in range(1, N_CUSTOMERS + 1)])
    start = date(2022, 1, 1)
    conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", [
        (i, rng.randint(1, N_CUSTOMERS), rng.choice(["paid", "shipped", "pending"]),
         round(rng.uniform(5, 500), 2), (start + timedelta(days=rng.randint(0, 1460))).isoformat())
        for i in range(1, N_ORDERS + 1)])
    conn.commit()
    conn.execute("ANALYZE")
    conn.close()


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "shop_test.db"
    build_shop(path)
    adapter = get_adapter("sqlite")
    adapter.connect({"database": str(path)})
    yield adapter
    adapter.close()


def test_connect_and_metadata(db):
    tables = {t["name"]: t["approx_rows"] for t in db.list_tables()}
    assert tables == {"customers": N_CUSTOMERS, "orders": N_ORDERS}
    assert "customer_id" in db.list_columns("orders")
    assert db.list_indexes("orders")[0]["primary"]
    assert db.column_stats("orders", "status")["distinct_values"] == 3


def test_missing_file_is_reported():
    with pytest.raises(FileNotFoundError):
        get_adapter("sqlite").connect({"database": "no_such_file.db"})


def test_full_scan_is_found_and_fixed_on_clone(db):
    analysis = analyze(db, "SELECT * FROM orders WHERE customer_id = 500")
    assert analysis["problems"][0]["rule_code"] == "R1"
    assert analysis["problems"][0]["message"].startswith("SQLite reads all")
    suggestion = analysis["suggestions"][0]
    assert suggestion["ddl"] == "CREATE INDEX idx_orders_customer_id ON orders (customer_id)"

    result = run_test(db, analysis, suggestion, runs=3)
    assert result["rows_before"] == N_ORDERS
    assert result["rows_after"] < 100
    assert result["after_ms"] < result["before_ms"]
    assert result["index_size_kb"] > 0
    assert result["insert_after_ms"] > 0
    assert "index lookup" in result["plan_after"]

    clone_path = db.clone_path
    assert os.path.exists(clone_path)
    db.drop_clone()
    assert not os.path.exists(clone_path)
    assert [i["name"] for i in db.list_indexes("orders")] == ["PRIMARY"]


def test_composite_and_sort(db):
    analysis = analyze(db, "SELECT * FROM orders WHERE status = 'shipped' AND order_date >= '2025-01-01' "
                           "ORDER BY order_date DESC LIMIT 50")
    codes = {p["rule_code"] for p in analysis["problems"]}
    assert {"R2", "R6"} <= codes
    assert analysis["suggestions"][0]["columns"] == ["status", "order_date"]


def test_strftime_rewrite(db):
    analysis = analyze(db, "SELECT * FROM orders WHERE strftime('%Y', order_date) = '2025'")
    s = analysis["suggestions"][0]
    assert s["rewritten_query"].endswith("order_date >= '2025-01-01' AND order_date < '2026-01-01'")
    result = run_test(db, analysis, s, runs=1)
    assert result["rows_after"] < result["rows_before"]
    db.drop_clone()


def test_join_on_unindexed_column(db):
    analysis = analyze(db, "SELECT o.order_id, c.name FROM orders o JOIN customers c "
                           "ON c.customer_id = o.customer_id WHERE c.city = 'Karachi'")
    assert any(p["rule_code"] == "R1" and p["table"] == "orders" for p in analysis["problems"])
    assert any(s["table"] == "orders" and s["columns"] == ["customer_id"] for s in analysis["suggestions"])


def test_apply_on_real_database(db):
    db.create_index("CREATE INDEX idx_orders_status ON orders (status)", on_clone=False)
    assert "idx_orders_status" in [i["name"] for i in db.list_indexes("orders")]
    with pytest.raises(ValueError):
        db.create_index("DROP TABLE orders", on_clone=False)
