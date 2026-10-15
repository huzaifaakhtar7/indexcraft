from core.query_parser import parse_query
from core.rules import run_rules


def plan(rows=100000, access="ALL", key=None, filesort=False):
    return [{"table": "orders", "alias": "orders", "access": access, "full_scan": access == "ALL",
             "index_used": key, "rows_examined": rows, "filesort": filesort}]


def codes(q, p):
    return [x["rule_code"] for x in run_rules(parse_query(q), p)]


def test_r1_full_scan():
    assert "R1" in codes("SELECT * FROM orders WHERE customer_id = 5", plan())


def test_r2_and_r6():
    c = codes("SELECT * FROM orders WHERE status = 'paid' AND order_date > '2025-01-01' ORDER BY order_date", plan(filesort=True))
    assert "R2" in c and "R6" in c


def test_r3_function():
    assert "R3" in codes("SELECT * FROM orders WHERE YEAR(order_date) = 2025", plan())


def test_small_table_ignored():
    assert codes("SELECT * FROM orders WHERE customer_id = 5", plan(rows=10)) == []


def test_messages_name_the_database():
    p = run_rules(parse_query("SELECT * FROM orders WHERE customer_id = 5"), plan(), "PostgreSQL")
    assert p[0]["message"].startswith("PostgreSQL reads all")
