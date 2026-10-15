from core.plan_normalizer import normalize
from core.query_parser import parse_query
from core.rules import SEVERITY_ORDER, run_rules
from core.scoring import score
from core.suggester import redundant_indexes, suggest
from core.write_cost import INSERT_ROWS, measure_write_cost


def diagnose(adapter, query: str) -> dict:
    first = parse_query(query)
    columns = {t["name"]: adapter.list_columns(t["name"]) for t in first["tables"]}
    parsed = parse_query(query, columns)
    explain = adapter.explain(parsed["query"])
    plan = normalize(adapter.name, explain, parsed["alias_map"])
    problems = run_rules(parsed, plan, adapter.label)
    return {"query": parsed["query"], "parsed": parsed, "plan": plan, "problems": problems}


def analyze(adapter, query: str) -> dict:
    result = diagnose(adapter, query)
    parsed = result["parsed"]
    indexes = {t["name"]: adapter.list_indexes(t["name"]) for t in parsed["tables"]}
    out = suggest(parsed, result["problems"],
                  stats_fn=adapter.column_stats,
                  indexes_fn=lambda t: indexes.get(t, []),
                  engine=adapter.label)
    problems = result["problems"] + out["extra_problems"]
    for table, idx in indexes.items():
        problems += redundant_indexes(table, idx, adapter.drop_index_sql)
    problems.sort(key=lambda p: (SEVERITY_ORDER[p["severity"]], p["rule_code"]))
    result["problems"] = problems
    result["suggestions"] = out["suggestions"]
    result["notes"] = out["notes"]
    result["rows_examined"] = sum(s["rows_examined"] for s in result["plan"])
    return result


def _plan_summary(adapter, query, on_clone, alias_map):
    plan = normalize(adapter.name, adapter.explain(query, on_clone=on_clone), alias_map)
    return {
        "rows_examined": sum(s["rows_examined"] for s in plan),
        "access": ", ".join(f"{s['table']}: {s['access_label']}" for s in plan),
        "steps": plan,
    }


def test_suggestion(adapter, analysis: dict, suggestion: dict, read_share: float = 0.9,
                    runs: int = 5) -> dict:
    parsed = analysis["parsed"]
    query = analysis["query"]
    tables = [t["name"] for t in parsed["tables"]]
    table = suggestion["table"]

    adapter.make_clone(tables)
    baseline = analysis.setdefault("_baseline", {})
    if "before" not in baseline:
        baseline["plan"] = _plan_summary(adapter, query, True, parsed["alias_map"])
        baseline["before"] = adapter.run_timed(query, runs=runs, on_clone=True)
    if table not in baseline.setdefault("insert", {}):
        baseline["insert"][table] = measure_write_cost(adapter, table)
    before_plan = baseline["plan"]
    before = baseline["before"]
    insert_before = baseline["insert"][table]

    adapter.create_index(suggestion["ddl"], on_clone=True)
    try:
        after_query = suggestion.get("rewritten_query") or query
        after_plan = _plan_summary(adapter, after_query, True, parsed["alias_map"])
        after = adapter.run_timed(after_query, runs=runs, on_clone=True)
        insert_after = measure_write_cost(adapter, table)
        size_bytes = adapter.index_size(suggestion["index_name"], table, on_clone=True)
    finally:
        adapter.drop_index(table, suggestion["index_name"], on_clone=True)

    scores = score(before["median_ms"], after["median_ms"], insert_before, insert_after,
                   INSERT_ROWS, read_share)
    return {
        "suggestion": suggestion,
        "query_after": after_query,
        "before_ms": before["median_ms"],
        "after_ms": after["median_ms"],
        "before_timings": before["timings_ms"],
        "after_timings": after["timings_ms"],
        "rows_before": before_plan["rows_examined"],
        "rows_after": after_plan["rows_examined"],
        "plan_before": before_plan["access"],
        "plan_after": after_plan["access"],
        "insert_rows": INSERT_ROWS,
        "insert_before_ms": insert_before,
        "insert_after_ms": insert_after,
        "index_size_kb": round(size_bytes / 1024),
        **scores,
    }


def rank_results(results: list) -> list:
    order = {"Recommended": 0, "Optional": 1, "Not worth it": 2}
    return sorted(results, key=lambda r: (order[r["verdict"]], -r["net_benefit_ms"]))
