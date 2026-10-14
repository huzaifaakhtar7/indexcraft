import os

from adapters.factory import get_adapter

QUERY = "SELECT * FROM orders WHERE customer_id = 500"
INDEX = "CREATE INDEX idx_orders_customer ON orders (customer_id)"


def show_explain(title, plan):
    print(f"\n{title}")
    for row in plan["rows"]:
        print(f"  table={row.get('table')}  type={row.get('type')}  "
              f"key={row.get('key')}  rows={row.get('rows')}")


def main():
    db = get_adapter("mysql")
    db.connect({
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", "root"),
        "database": "shop",
    })
    print("Connected to shop")

    print("\nTables:")
    for t in db.list_tables():
        print(f"  {t['name']:12s} ~{int(t['approx_rows'] or 0):,} rows")

    print(f"\nQuery: {QUERY}")
    show_explain("EXPLAIN on real database (before):", db.explain(QUERY))

    before = db.run_timed(QUERY, runs=5)
    print(f"\nBefore: median {before['median_ms']} ms  "
          f"(runs: {before['timings_ms']})  rows returned: {before['rows_returned']}")

    stats = db.column_stats("orders", "customer_id")
    print(f"\ncustomer_id: {stats['distinct_values']:,} distinct of "
          f"{stats['total_rows']:,}  selectivity {stats['selectivity']}")

    print("\nMaking a safe clone of orders (takes a little time)...")
    db.make_clone(["orders"])
    insert_before = db.measure_insert("orders", 10_000)

    db.create_index(INDEX, on_clone=True)
    print(f"Index created on clone: {INDEX}")
    show_explain("EXPLAIN on clone (after):", db.explain(QUERY, on_clone=True))

    after = db.run_timed(QUERY, runs=5, on_clone=True)
    insert_after = db.measure_insert("orders", 10_000)
    size = db.index_size("idx_orders_customer", "orders")

    speedup = before["median_ms"] / after["median_ms"] if after["median_ms"] else 0
    print("\n================ RESULT ================")
    print(f"Query time     : {before['median_ms']} ms  ->  {after['median_ms']} ms  "
          f"({speedup:.0f}x faster)")
    print(f"Insert 10k rows: {insert_before} ms  ->  {insert_after} ms")
    print(f"Index size     : {size / 1024 / 1024:.2f} MB")
    print("========================================")

    print("\nReal database indexes on orders (should be only PRIMARY):")
    print(" ", [i["name"] for i in db.list_indexes("orders")])

    db.drop_clone()
    db.close()
    print("\nClone deleted. Real database was never changed.")


if __name__ == "__main__":
    main()
