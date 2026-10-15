from core.query_parser import parse_query
from core.rules import run_rules
from core.suggester import redundant_indexes, suggest
from tests.test_rules import plan


def rewrite(query):
    parsed = parse_query(query)
    out = suggest(parsed, run_rules(parsed, plan()))
    return [s["rewritten_query"] for s in out["suggestions"] if s["rewritten_query"]]


def test_year_rewrites_for_all_databases():
    expected = "order_date >= '2025-01-01' AND order_date < '2026-01-01'"
    for q in ["SELECT * FROM orders WHERE YEAR(order_date) = 2025",
              "SELECT * FROM orders WHERE EXTRACT(YEAR FROM order_date) = 2025",
              "SELECT * FROM orders WHERE strftime('%Y', order_date) = '2025'"]:
        assert rewrite(q) == [f"SELECT * FROM orders WHERE {expected}"]


def test_date_rewrite_keeps_alias():
    r = rewrite("SELECT * FROM orders o WHERE DATE(o.order_date) = '2025-03-15'")
    assert r == ["SELECT * FROM orders o WHERE o.order_date >= '2025-03-15' AND o.order_date < '2025-03-16'"]


def test_redundant_index_uses_given_drop_sql():
    idx = [{"name": "orders_pkey", "columns": ["order_id"], "primary": True},
           {"name": "a", "columns": ["status"]}, {"name": "b", "columns": ["status", "order_date"]}]
    found = redundant_indexes("orders", idx, lambda t, n: f"DROP INDEX {n}")
    assert [p["drop_sql"] for p in found] == ["DROP INDEX a"]
