import re
from datetime import date, timedelta

MAX_SUGGESTIONS = 3
LOW_DISTINCT = 100
MAX_NAME = 64


def index_name(table: str, columns: list) -> str:
    name = f"idx_{table}_" + "_".join(columns)
    return name[:MAX_NAME]


def create_index_sql(table: str, columns: list) -> str:
    return f"CREATE INDEX {index_name(table, columns)} ON {table} ({', '.join(columns)})"


def _date_rewrite(query: str, function: dict):
    col = re.escape(function["column"])
    ref = r"((?:`?\w+`?\.)?`?" + col + r"`?)"
    if function["function"] == "YEAR":
        m = re.search(r"YEAR\s*\(\s*" + ref + r"\s*\)\s*=\s*'?(\d{4})'?", query, re.I)
        if not m:
            return None
        year = int(m.group(2))
        start, end = f"{year}-01-01", f"{year + 1}-01-01"
    elif function["function"] == "DATE":
        m = re.search(r"DATE\s*\(\s*" + ref + r"\s*\)\s*=\s*'(\d{4}-\d{2}-\d{2})'", query, re.I)
        if not m:
            return None
        day = date.fromisoformat(m.group(2))
        start, end = day.isoformat(), (day + timedelta(days=1)).isoformat()
    else:
        return None
    replacement = f"{m.group(1)} >= '{start}' AND {m.group(1)} < '{end}'"
    return query[:m.start()] + replacement + query[m.end():]


def _covered(existing: list, columns: list) -> bool:
    cols = [c.lower() for c in columns]
    for idx in existing:
        have = [c.lower() for c in idx["columns"]]
        if have[:len(cols)] == cols:
            return True
    return False


def suggest(parsed, problems: list, stats_fn=None, indexes_fn=None) -> dict:
    query = parsed["query"]
    stats_cache = {}
    notes = []

    def stats(table, column):
        key = (table, column.lower())
        if key not in stats_cache and stats_fn:
            stats_cache[key] = stats_fn(table, column)
        return stats_cache.get(key)

    def low_cardinality(table, column):
        s = stats(table, column)
        return bool(s and s["total_rows"] > 10_000 and s["distinct_values"] < LOW_DISTINCT)

    candidates = []

    def add(table, columns, reason, problem, kind="index", rewritten=None, priority=5):
        if not table or not columns:
            return
        key = (table.lower(), tuple(c.lower() for c in columns), kind)
        if any(c["key"] == key for c in candidates):
            return
        existing = indexes_fn(table) if indexes_fn else []
        if kind == "index" and _covered(existing, columns):
            notes.append(f"An index on {table} ({', '.join(columns)}) already exists.")
            return
        candidates.append({
            "key": key, "kind": kind, "table": table, "columns": list(columns),
            "index_name": index_name(table, columns),
            "ddl": create_index_sql(table, columns),
            "rewritten_query": rewritten, "reason": reason,
            "rule_code": problem["rule_code"] if problem else None,
            "priority": priority,
        })

    by_rule = {}
    for p in problems:
        by_rule.setdefault(p["rule_code"], []).append(p)

    for p in by_rule.get("R2", []):
        cols = p["columns"]
        add(p["table"], cols,
            f"Composite index ({', '.join(cols)}): equality columns first, then the range or "
            f"sort column, so one index serves the whole WHERE and ORDER BY.",
            p, priority=1)

    for p in by_rule.get("R3", []):
        rewritten = _date_rewrite(query, p)
        if rewritten:
            add(p["table"], [p["column"] if "column" in p else p["columns"][0]],
                f"Rewrite {p['function']}({p['columns'][0]}) as a date range so the column stays "
                f"visible, then index {p['columns'][0]}.",
                p, kind="rewrite", rewritten=rewritten, priority=1)
        else:
            notes.append(f"{p['function']}({p['columns'][0]}) cannot be rewritten automatically. "
                         f"Rewrite it by hand as a plain comparison on {p['columns'][0]}.")

    for p in by_rule.get("R1", []):
        for col in p.get("columns", []):
            if low_cardinality(p["table"], col):
                s = stats(p["table"], col)
                notes.append(f"Skipped a single index on {p['table']}.{col}: only "
                             f"{s['distinct_values']} different values in {s['total_rows']:,} rows.")
                continue
            add(p["table"], [col],
                f"Single-column index on {col} lets MySQL jump straight to the matching rows "
                f"instead of reading the whole '{p['table']}' table.",
                p, priority=2)

    for p in by_rule.get("R6", []):
        if any(c["table"] == p["table"] and c["columns"][-len(p["columns"]):] == p["columns"]
               for c in candidates):
            continue
        add(p["table"], p["columns"],
            f"Index on the ORDER BY column(s) {', '.join(p['columns'])} returns rows already sorted.",
            p, priority=3)

    for p in by_rule.get("R4", []):
        notes.append(f"LIKE '{p['pattern']}' cannot use a normal index. Consider a search that "
                     f"starts at the beginning of the text, or a FULLTEXT index.")

    candidates.sort(key=lambda c: (c["priority"], -len(c["columns"])))
    chosen = candidates[:MAX_SUGGESTIONS]
    for rank, c in enumerate(chosen, 1):
        c["rank"] = rank
        c.pop("key")
        c.pop("priority")

    low_card_problems = []
    for (table, col), s in stats_cache.items():
        if s and s["total_rows"] > 10_000 and s["distinct_values"] < LOW_DISTINCT:
            low_card_problems.append({
                "rule_code": "R5", "severity": "low", "table": table,
                "title": "Low selectivity column",
                "message": f"{table}.{s['column']} has only {s['distinct_values']} different values "
                           f"in {s['total_rows']:,} rows, so an index on it alone helps little. "
                           f"Use it only as the first part of a composite index.",
                "columns": [s["column"]],
            })

    return {"suggestions": chosen, "notes": notes, "extra_problems": low_card_problems}


def redundant_indexes(table: str, indexes: list) -> list:
    problems = []
    for a in indexes:
        if a["name"] == "PRIMARY":
            continue
        for b in indexes:
            if a is b or len(b["columns"]) <= len(a["columns"]):
                continue
            if [c.lower() for c in b["columns"][:len(a["columns"])]] == [c.lower() for c in a["columns"]]:
                problems.append({
                    "rule_code": "R7", "severity": "low", "table": table,
                    "title": "Redundant index",
                    "message": f"Index {a['name']} ({', '.join(a['columns'])}) is the start of "
                               f"{b['name']} ({', '.join(b['columns'])}). The shorter one can be "
                               f"dropped to save space and speed up writes.",
                    "columns": a["columns"], "drop_sql": f"DROP INDEX {a['name']} ON {table}",
                })
                break
    return problems
