import os
import sys
import time
from pathlib import Path

from adapters.factory import get_adapter
from core.analyzer import analyze, test_suggestion

DATA = Path(__file__).resolve().parent / "data"

DATABASES = {
    "mysql": ({"host": os.getenv("DB_HOST", "localhost"), "user": os.getenv("DB_USER", "root"),
               "password": os.getenv("DB_PASSWORD", "root"), "database": os.getenv("DB_NAME", "shop")},
              DATA / "sample_queries.sql"),
    "postgres": ({"host": os.getenv("PG_HOST", "localhost"), "user": os.getenv("PG_USER", "postgres"),
                  "password": os.getenv("PG_PASSWORD", ""), "database": os.getenv("PG_DATABASE", "shop")},
                 DATA / "sample_queries_postgres.sql"),
    "sqlite": ({"database": str(DATA / "shop.db")}, DATA / "sample_queries_sqlite.sql"),
}


def queries(path: Path) -> list:
    return [q.strip() for q in path.read_text(encoding="utf-8").split(";") if q.strip()]


def run(db_type: str) -> list:
    config, query_file = DATABASES[db_type]
    db = get_adapter(db_type)
    db.connect(config)
    rows = []
    try:
        for i, q in enumerate(queries(query_file), 1):
            analysis = analyze(db, q)
            codes = ",".join(sorted({p["rule_code"] for p in analysis["problems"]})) or "-"
            row = {"db": db.label, "n": i, "rules": codes, "fix": "-", "before": None, "after": None,
                   "speedup": None, "verdict": "no suggestion"}
            if analysis["suggestions"]:
                s = analysis["suggestions"][0]
                r = test_suggestion(db, analysis, s, runs=3)
                row.update(fix=f"{s['table']}({', '.join(s['columns'])})" + (" +rewrite" if s["rewritten_query"] else ""),
                           before=r["before_ms"], after=r["after_ms"], speedup=r["speedup"],
                           verdict=r["verdict"])
            rows.append(row)
            print(f"  {db.label:10s} Q{i}  {codes:12s} {row['fix']:36s} {row['verdict']}", flush=True)
    finally:
        db.drop_clone()
        db.close()
    return rows


def main():
    targets = sys.argv[1:] or list(DATABASES)
    started = time.time()
    results = []
    for db_type in targets:
        print(f"Running sample queries on {db_type}...", flush=True)
        results += run(db_type)
    print("\n" + "=" * 100)
    print(f"{'DB':10s} {'Q':3s} {'Rules':12s} {'Best fix':36s} {'Before':>10s} {'After':>10s} {'Speed':>8s}  Verdict")
    print("-" * 100)
    for r in results:
        before = f"{r['before']:.1f} ms" if r["before"] is not None else "-"
        after = f"{r['after']:.1f} ms" if r["after"] is not None else "-"
        speed = f"{r['speedup']}x" if r["speedup"] else "-"
        print(f"{r['db']:10s} Q{r['n']:<2d} {r['rules']:12s} {r['fix']:36s} {before:>10s} {after:>10s} "
              f"{speed:>8s}  {r['verdict']}")
    print(f"\nClones deleted. Real databases unchanged. Total time {time.time() - started:.0f}s")


if __name__ == "__main__":
    main()
