from core.plan_normalizer import normalize


def test_postgres_seq_scan_uses_table_rows():
    explain = {
        "plan": {"Node Type": "Gather", "Plans": [
            {"Node Type": "Seq Scan", "Relation Name": "orders", "Alias": "orders",
             "Plan Rows": 4, "Filter": "(customer_id = 500)"}]},
        "table_rows": {"orders": 1_000_000},
    }
    step = normalize("postgres", explain)[0]
    assert step["full_scan"] and step["access"] == "ALL"
    assert step["rows_examined"] == 1_000_000
    assert not step["filesort"]


def test_postgres_sort_and_bitmap_index():
    explain = {"plan": {"Node Type": "Limit", "Plans": [
        {"Node Type": "Sort", "Plans": [
            {"Node Type": "Bitmap Heap Scan", "Relation Name": "orders", "Alias": "o",
             "Plan Rows": 12, "Recheck Cond": "(customer_id = 500)",
             "Plans": [{"Node Type": "Bitmap Index Scan", "Index Name": "idx_orders_customer_id"}]}]}]}}
    step = normalize("postgres", explain, {"o": "orders"})[0]
    assert step["table"] == "orders"
    assert step["access"] == "ref"
    assert step["index_used"] == "idx_orders_customer_id"
    assert step["rows_examined"] == 12
    assert step["filesort"]


def test_postgres_index_range():
    explain = {"plan": {"Node Type": "Index Scan", "Relation Name": "orders", "Alias": "orders",
                        "Index Name": "idx", "Plan Rows": 50,
                        "Index Cond": "((status)::text = 'paid'::text) AND (order_date >= '2025-01-01'::date)"}}
    assert normalize("postgres", explain)[0]["access"] == "range"


def test_sqlite_scan_and_temp_btree():
    explain = {"rows": [(2, 0, 0, "SCAN orders"), (9, 0, 0, "USE TEMP B-TREE FOR ORDER BY")],
               "table_rows": {"orders": 5000}}
    step = normalize("sqlite", explain)[0]
    assert step["full_scan"] and step["filesort"]
    assert step["rows_examined"] == 5000


def test_sqlite_search_uses_index_stats():
    explain = {"rows": [(3, 0, 0, "SEARCH o USING INDEX idx_orders_customer_id (customer_id=?)")],
               "table_rows": {"orders": 5000},
               "index_stats": {"idx_orders_customer_id": [5000, 10]}}
    step = normalize("sqlite", explain, {"o": "orders"})[0]
    assert step["table"] == "orders"
    assert step["access"] == "ref"
    assert step["index_used"] == "idx_orders_customer_id"
    assert step["rows_examined"] == 10


def test_sqlite_automatic_index_counts_as_full_scan():
    explain = {"rows": [(2, 0, 0, "SCAN c"),
                        (4, 0, 0, "SEARCH o USING AUTOMATIC COVERING INDEX (customer_id=?)")],
               "table_rows": {"orders": 5000, "customers": 500}}
    steps = normalize("sqlite", explain, {"o": "orders", "c": "customers"})
    assert [s["table"] for s in steps] == ["customers", "orders"]
    assert all(s["full_scan"] for s in steps)


def test_sqlite_rowid_lookup():
    explain = {"rows": [(2, 0, 0, "SEARCH orders USING INTEGER PRIMARY KEY (rowid=?)")],
               "table_rows": {"orders": 5000}}
    step = normalize("sqlite", explain)[0]
    assert step["access"] == "const" and step["rows_examined"] == 1
