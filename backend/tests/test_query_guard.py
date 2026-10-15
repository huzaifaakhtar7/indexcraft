import pytest

from core.query_guard import check_select


def test_plain_select_passes():
    assert check_select("SELECT * FROM orders WHERE customer_id = 500;") == \
        "SELECT * FROM orders WHERE customer_id = 500"


def test_semicolon_inside_string_is_fine():
    assert "a;b" in check_select("SELECT * FROM customers WHERE name = 'a;b'")


@pytest.mark.parametrize("query", [
    "DELETE FROM orders",
    "SELECT 1; DROP TABLE orders",
    "UPDATE orders SET status = 'x'",
    "SELECT * INTO backup FROM orders",
    "SELECT pg_sleep(100)",
    "SELECT * FROM orders FOR UPDATE",
    "",
])
def test_unsafe_queries_rejected(query):
    with pytest.raises(ValueError):
        check_select(query)
