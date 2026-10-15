import os

import pytest

from adapters.factory import get_adapter
from core.analyzer import analyze, test_suggestion as run_test

pytestmark = pytest.mark.skipif(not os.getenv("PG_PASSWORD"), reason="PG_PASSWORD is not set")

SCHEMA = "ic_pytest"
N_ORDERS = 50_000


def pg_config(**extra):
    return {
        "host": os.getenv("PG_HOST", "localhost"),
        "port": int(os.getenv("PG_PORT", 5432)),
        "user": os.getenv("PG_USER", "postgres"),
        "password": os.getenv("PG_PASSWORD", ""),
        "database": os.getenv("PG_TEST_DATABASE", "postgres"),
        **extra,
    }


@pytest.fixture(scope="module")
def db():
    setup = get_adapter("postgres")
    setup.connect(pg_config())
    setup._exec(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
    setup._exec(f"CREATE SCHEMA {SCHEMA}")
    setup._exec(f"CREATE TABLE {SCHEMA}.customers (customer_id INT PRIMARY KEY, name VARCHAR(100), "
                f"city VARCHAR(60))")
    setup._exec(f"CREATE TABLE {SCHEMA}.orders (order_id INT PRIMARY KEY, customer_id INT, "
                f"status VARCHAR(20), total_amount NUMERIC(10,2), order_date DATE)")
    setup._exec(f"INSERT INTO {SCHEMA}.customers SELECT g, 'Name ' || g, "
                f"(ARRAY['Karachi','Lahore','Multan','Quetta'])[1 + g % 4] "
                f"FROM generate_series(1, 2000) g")
    setup._exec(f"INSERT INTO {SCHEMA}.orders SELECT g, 1 + (g * 7919) % 2000, "
                f"(ARRAY['paid','shipped','pending'])[1 + g % 3], (g % 500) + 0.5, "
                f"DATE '2022-01-01' + (g % 1460) FROM generate_series(1, {N_ORDERS}) g")
    setup._exec(f"ANALYZE {SCHEMA}.customers")
    setup._exec(f"ANALYZE {SCHEMA}.orders")
    adapter = get_adapter("postgres")
    adapter.connect(pg_config(schema=SCHEMA))
    yield adapter
    adapter.drop_clone()
    adapter.close()
    setup._exec(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE")
    setup.close()


def test_metadata(db):
    tables = {t["name"]: t["approx_rows"] for t in db.list_tables()}
    assert tables["orders"] == N_ORDERS
    idx = db.list_indexes("orders")
    assert idx[0]["primary"] and idx[0]["columns"] == ["order_id"]
    assert db.column_stats("orders", "status")["distinct_values"] == 3


def test_full_scan_is_found_and_fixed_on_clone(db):
    analysis = analyze(db, "SELECT * FROM orders WHERE customer_id = 500")
    assert analysis["problems"][0]["rule_code"] == "R1"
    assert analysis["problems"][0]["message"].startswith("PostgreSQL reads all")
    suggestion = analysis["suggestions"][0]
    result = run_test(db, analysis, suggestion, runs=3)
    assert result["rows_before"] == N_ORDERS
    assert result["rows_after"] < 1000
    assert result["after_ms"] < result["before_ms"]
    assert result["index_size_kb"] > 0
    assert db.list_indexes("orders", on_clone=True)[0]["primary"]
    assert [i["name"] for i in db.list_indexes("orders")] == ["orders_pkey"]


def test_extract_rewrite_and_sort(db):
    analysis = analyze(db, "SELECT * FROM orders WHERE EXTRACT(YEAR FROM order_date) = 2025")
    assert analysis["problems"][0]["rule_code"] == "R3"
    assert analysis["suggestions"][0]["rewritten_query"].endswith("order_date < '2026-01-01'")
    sort = analyze(db, "SELECT * FROM orders WHERE status = 'shipped' AND order_date >= '2025-01-01' "
                       "ORDER BY order_date DESC LIMIT 50")
    assert {"R2", "R6"} <= {p["rule_code"] for p in sort["problems"]}


def test_drop_clone_removes_schema(db):
    db.make_clone(["orders"])
    db.drop_clone()
    rows = db._rows("SELECT 1 FROM pg_namespace WHERE nspname = 'ic_clone'")
    assert rows == []
