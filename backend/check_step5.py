import os

from adapters.factory import get_adapter
from core.analyzer import diagnose

QUERIES = [
    "SELECT * FROM orders WHERE customer_id = 500",
    "SELECT * FROM orders WHERE status = 'shipped' AND order_date >= '2025-01-01' ORDER BY order_date DESC LIMIT 50",
    "SELECT * FROM orders WHERE YEAR(order_date) = 2025",
    "SELECT * FROM customers WHERE name LIKE '%ali'",
    "SELECT o.order_id, o.order_date, c.name FROM orders o JOIN customers c ON c.customer_id = o.customer_id WHERE c.city = 'Karachi'",
    "SELECT * FROM orders WHERE order_id = 10",
]


def main():
    db = get_adapter("mysql")
    db.connect({
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", "root"),
        "database": "shop",
    })

    for i, q in enumerate(QUERIES, 1):
        result = diagnose(db, q)
        print("=" * 78)
        print(f"Query {i}: {q}")
        print("-" * 78)
        for step in result["plan"]:
            print(f"  Plan: {step['table']:12s} {step['access_label']:18s} "
                  f"index={step['index_used']}  rows={step['rows_examined']:,}"
                  + ("  +filesort" if step["filesort"] else ""))
        if not result["problems"]:
            print("  OK  No problem found. This query already uses an index.")
        for p in result["problems"]:
            print(f"  [{p['rule_code']}] [{p['severity'].upper()}] {p['title']}")
            print(f"       {p['message']}")
    print("=" * 78)
    db.close()


if __name__ == "__main__":
    main()
