import os
import sys
import time

from adapters.factory import get_adapter
from core.analyzer import analyze, rank_results, test_suggestion
from core.reporter import build_report
from history.store import HistoryStore

QUERIES = [
    "SELECT * FROM orders WHERE customer_id = 500",
    "SELECT * FROM orders WHERE status = 'shipped' AND order_date >= '2025-01-01' ORDER BY order_date DESC LIMIT 50",
    "SELECT * FROM orders WHERE YEAR(order_date) = 2025",
    "SELECT * FROM orders WHERE DATE(order_date) = '2025-03-15'",
]

TEST_ALL = "--all" in sys.argv


def main():
    config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "user": os.getenv("DB_USER", "root"),
        "password": os.getenv("DB_PASSWORD", "root"),
        "database": "shop",
    }
    db = get_adapter("mysql")
    db.connect(config)
    history = HistoryStore(config)
    started = time.time()

    try:
        for i, q in enumerate(QUERIES, 1):
            print("=" * 78)
            print(f"Query {i}: {q}")
            print("=" * 78)

            analysis = analyze(db, q)
            run_id = history.save_run("mysql", config["database"], analysis["query"])
            problem_ids = history.save_problems(run_id, analysis["problems"])
            history.save_suggestions(run_id, analysis["suggestions"], problem_ids)

            print("Problems:")
            for p in analysis["problems"]:
                print(f"  [{p['rule_code']}] {p['title']}")
            print("Suggestions:")
            for s in analysis["suggestions"]:
                print(f"  {s['rank']}. {s['ddl']}")
                if s.get("rewritten_query"):
                    print(f"     rewrite -> {s['rewritten_query']}")
            for n in analysis["notes"]:
                print(f"  note: {n}")

            to_test = analysis["suggestions"] if TEST_ALL else analysis["suggestions"][:1]
            results = []
            for s in to_test:
                print(f"\nTesting on clone: {s['ddl']} ...")
                r = test_suggestion(db, analysis, s, read_share=0.9)
                history.save_test_result(s["suggestion_id"], r)
                results.append(r)
                print(f"  time   {r['before_ms']} ms -> {r['after_ms']} ms   ({r['speedup']}x)")
                print(f"  rows   {r['rows_before']:,} -> {r['rows_after']:,}")
                print(f"  insert {r['insert_before_ms']} ms -> {r['insert_after_ms']} ms "
                      f"(+{r['write_loss_pct']}%)   size {r['index_size_kb']:,} KB")
                print(f"  VERDICT: {r['verdict']}   (net benefit {r['net_benefit_ms']} ms)")

            results = rank_results(results)
            if results:
                history.update_baseline(run_id, results[0]["before_ms"])
            history.save_report(run_id, build_report(analysis, results, "mysql", config["database"]))
            print(f"\nSaved as run #{run_id} in indexcraft_meta")

        print("\n" + "=" * 78)
        print("HISTORY DATABASE (indexcraft_meta)")
        print("=" * 78)
        print("Recent runs:")
        for r in history.list_runs(limit=5):
            print(f"  #{r['run_id']:<3} {str(r['created_at']):19s}  problems={r['problems']}  "
                  f"suggestions={r['suggestions']}  best={r['best_verdict']}")
        print("\nAverage speed-up per rule (JOIN + GROUP BY):")
        for r in history.speedup_by_rule():
            print(f"  {r['rule_code']}: {r['cases']} case(s), avg {r['avg_speedup']}x faster")

        last = history.list_runs(limit=1)[0]
        print("\n" + history.get_run(last["run_id"])["report"]["report_text"])
    finally:
        db.drop_clone()
        db.close()
        history.close()
        print(f"\nClone deleted. Real database unchanged. Total time {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
