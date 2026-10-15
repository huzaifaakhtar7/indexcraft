import os

import pytest

from adapters.factory import get_adapter
from core.analyzer import analyze, test_suggestion as run_test

pytestmark = pytest.mark.skipif(not os.getenv("DB_PASSWORD"), reason="DB_PASSWORD is not set")

TEST_DB = "ic_pytest"
N_ORDERS = 30_000


@pytest.fixture(scope="module")
def db():
    config = {"host": os.getenv("DB_HOST", "localhost"), "user": os.getenv("DB_USER", "root"),
              "password": os.getenv("DB_PASSWORD", "")}
    adapter = get_adapter("mysql")
    adapter.connect({**config, "database": "mysql"})
    adapter._exec(f"DROP DATABASE IF EXISTS {TEST_DB}")
    adapter._exec(f"CREATE DATABASE {TEST_DB}")
    adapter.close()
    adapter.connect({**config, "database": TEST_DB})
    adapter._exec("CREATE TABLE orders (order_id INT PRIMARY KEY, customer_id INT, status VARCHAR(20), "
                  "total_amount DECIMAL(10,2), order_date DATE)")
    rows = [(i, 1 + (i * 7919) % 2000, ["paid", "shipped", "pending"][i % 3], 10.5,
             f"{2022 + i % 4}-{1 + i % 12:02d}-{1 + i % 28:02d}") for i in range(1, N_ORDERS + 1)]
    cur = adapter.conn.cursor()
    cur.executemany("INSERT INTO orders VALUES (%s, %s, %s, %s, %s)", rows)
    cur.close()
    adapter._exec("ANALYZE TABLE orders")
    yield adapter
    adapter.drop_clone()
    adapter._exec(f"DROP DATABASE IF EXISTS {TEST_DB}")
    adapter.close()


def test_full_scan_is_found_and_fixed_on_clone(db):
    analysis = analyze(db, "SELECT * FROM orders WHERE customer_id = 500")
    assert analysis["problems"][0]["message"].startswith("MySQL reads all")
    result = run_test(db, analysis, analysis["suggestions"][0], runs=3)
    assert result["rows_after"] < 1000
    assert result["after_ms"] < result["before_ms"]
    assert [i["name"] for i in db.list_indexes("orders")] == ["PRIMARY"]


def test_year_rewrite(db):
    analysis = analyze(db, "SELECT * FROM orders WHERE YEAR(order_date) = 2025")
    assert analysis["suggestions"][0]["rewritten_query"].endswith("order_date < '2026-01-01'")
