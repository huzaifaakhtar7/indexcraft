from datetime import datetime


def _fmt_ms(ms: float) -> str:
    return f"{ms / 1000:.2f} s" if ms >= 1000 else f"{ms:.2f} ms"


def build_report(analysis: dict, results: list, db_type: str = "mysql", db_name: str = "") -> str:
    lines = []
    lines.append("INDEXCRAFT REPORT")
    lines.append("=" * 60)
    lines.append(f"Date     : {datetime.now():%Y-%m-%d %H:%M}")
    lines.append(f"Database : {db_type} / {db_name}")
    lines.append(f"Query    : {analysis['query']}")
    lines.append("")

    lines.append("WHAT IS WRONG")
    if not analysis["problems"]:
        lines.append("  No problem found. The query already uses an index.")
    for p in analysis["problems"]:
        lines.append(f"  [{p['rule_code']}] {p['title']} ({p['severity']})")
        lines.append(f"      {p['message']}")
    lines.append("")

    lines.append("SUGGESTED FIXES")
    if not analysis["suggestions"]:
        lines.append("  No index suggestion for this query.")
    for s in analysis["suggestions"]:
        lines.append(f"  {s['rank']}. {s['ddl']};")
        if s.get("rewritten_query"):
            lines.append(f"     Rewritten query: {s['rewritten_query']}")
        lines.append(f"     Why: {s['reason']}")
    for n in analysis.get("notes", []):
        lines.append(f"  Note: {n}")
    lines.append("")

    if results:
        lines.append("MEASURED RESULTS (on a safe copy of the data)")
        for r in results:
            s = r["suggestion"]
            lines.append(f"  {s['ddl']}")
            lines.append(f"    Query time    : {_fmt_ms(r['before_ms'])} -> {_fmt_ms(r['after_ms'])}"
                         + (f"  ({r['speedup']}x faster)" if r.get("speedup") else ""))
            lines.append(f"    Rows examined : {r['rows_before']:,} -> {r['rows_after']:,}")
            lines.append(f"    Plan          : {r['plan_before']} -> {r['plan_after']}")
            lines.append(f"    INSERT {r['insert_rows']:,} rows: {_fmt_ms(r['insert_before_ms'])} -> "
                         f"{_fmt_ms(r['insert_after_ms'])}  ({r['write_loss_pct']}% slower)")
            lines.append(f"    Index size    : {r['index_size_kb']:,} KB")
            lines.append(f"    Net benefit   : {r['net_benefit_ms']} ms per operation "
                         f"({int(r['read_share'] * 100)}% reads / {int(r['write_share'] * 100)}% writes)")
            lines.append(f"    VERDICT       : {r['verdict']}")
            lines.append("")
        best = results[0]
        lines.append("RECOMMENDATION")
        if best["verdict"] == "Recommended":
            lines.append(f"  Apply: {best['suggestion']['ddl']};")
            if best["suggestion"].get("rewritten_query"):
                lines.append(f"  And use the rewritten query: {best['suggestion']['rewritten_query']}")
        else:
            lines.append("  None of the tested fixes is clearly worth it for this workload.")
    return "\n".join(lines)
