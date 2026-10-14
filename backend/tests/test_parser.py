from core.query_parser import parse_query


def test_simple_equality():
    p = parse_query("SELECT * FROM orders WHERE customer_id = 500")
    assert p["tables"][0]["name"] == "orders"
    assert p["conditions"][0]["column"] == "customer_id"
    assert p["conditions"][0]["kind"] == "equality"


def test_range_and_order():
    p = parse_query("SELECT * FROM orders WHERE status = 'paid' AND order_date >= '2025-01-01' ORDER BY order_date DESC LIMIT 5")
    kinds = {c["column"]: c["kind"] for c in p["conditions"]}
    assert kinds == {"status": "equality", "order_date": "range"}
    assert p["order_by"][0]["direction"] == "DESC"
    assert p["limit"] == 5


def test_function_and_wildcard():
    p = parse_query("SELECT * FROM orders WHERE YEAR(order_date) = 2025")
    assert p["functions"][0]["function"] == "YEAR"
    w = parse_query("SELECT * FROM customers WHERE name LIKE '%ali'")
    assert w["leading_wildcards"][0]["column"] == "name"


def test_join_alias():
    p = parse_query("SELECT o.order_id FROM orders o JOIN customers c ON c.customer_id = o.customer_id WHERE c.city = 'Lahore'")
    assert p["alias_map"]["o"] == "orders"
    assert p["joins"][0]["right"]["table"] == "orders"
    assert p["conditions"][0]["table"] == "customers"


def test_between_not_split():
    p = parse_query("SELECT * FROM orders WHERE order_date BETWEEN '2025-01-01' AND '2025-02-01' AND status = 'paid'")
    assert len(p["conditions"]) == 2
