MIN_ROWS = 1000

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _cols(items, table):
    seen, out = set(), []
    for item in items:
        if item.get("table") == table and item["column"].lower() not in seen:
            seen.add(item["column"].lower())
            out.append(item["column"])
    return out


def _join_cols(parsed, table):
    cols = []
    for j in parsed["joins"]:
        for side in ("left", "right"):
            if j[side]["table"] == table:
                cols.append({"table": table, "column": j[side]["column"]})
    return _cols(cols, table)


def _problem(code, severity, table, title, message, **extra):
    return {"rule_code": code, "severity": severity, "table": table,
            "title": title, "message": message, **extra}


def r1_full_scan(parsed, plan, engine="MySQL"):
    out = []
    for step in plan:
        if not step["full_scan"] or step["rows_examined"] < MIN_ROWS:
            continue
        t = step["table"]
        eq = _cols([c for c in parsed["conditions"] if c["kind"] in ("equality",)], t)
        rng = _cols([c for c in parsed["conditions"] if c["kind"] == "range"], t)
        joins = _join_cols(parsed, t)
        cols = eq + [c for c in joins if c not in eq] + [c for c in rng if c not in eq]
        covered = any(f["table"] == t for f in parsed["functions"] + parsed["leading_wildcards"])
        if not cols and covered:
            continue
        if cols:
            out.append(_problem(
                "R1", "high", t, "Full table scan",
                f"{engine} reads all {step['rows_examined']:,} rows of '{t}' because no index "
                f"exists on {', '.join(cols)}. An index lets it jump straight to the matching rows.",
                columns=cols, rows_examined=step["rows_examined"]))
        else:
            out.append(_problem(
                "R1", "low", t, "Full table scan without a filter",
                f"The query has no usable filter on '{t}', so all {step['rows_examined']:,} rows "
                f"are read. An index cannot help unless a WHERE condition is added.",
                columns=[], rows_examined=step["rows_examined"]))
    return out


def r2_composite(parsed, plan, engine="MySQL"):
    out = []
    for step in plan:
        t = step["table"]
        if step["rows_examined"] < MIN_ROWS:
            continue
        eq = _cols([c for c in parsed["conditions"] if c["kind"] == "equality"], t)
        rng = _cols([c for c in parsed["conditions"] if c["kind"] == "range"], t)
        order = _cols(parsed["order_by"], t)
        if not eq or len(eq) + len(rng) + len(order) < 2:
            continue
        ordered = list(eq)
        if rng:
            ordered.append(rng[0])
        elif order:
            ordered += [c for c in order if c not in ordered]
        if step["index_used"] and not step["full_scan"] and not step["filesort"] and len(ordered) <= 1:
            continue
        out.append(_problem(
            "R2", "medium", t, "Several conditions need one combined index",
            f"The query filters '{t}' on {', '.join(eq + rng)}"
            + (f" and sorts by {', '.join(order)}" if order else "")
            + ". One composite index in the order (" + ", ".join(ordered)
            + ") serves them together: equality columns first, then the range or sort column.",
            columns=ordered, equality=eq, range=rng, order_by=order))
    return out


def r3_function_on_column(parsed, plan, engine="MySQL"):
    out = []
    for f in parsed["functions"]:
        out.append(_problem(
            "R3", "high", f["table"], "Function on a column",
            f"{f.get('display') or f['function'] + '(' + f['column'] + ')'} hides the column from "
            f"any index, so {engine} must calculate it for every row. Rewrite it as a plain range on {f['column']} "
            f"(for example {f['column']} >= '2025-01-01' AND {f['column']} < '2026-01-01').",
            columns=[f["column"]], column=f["column"], function=f["function"], text=f["text"],
            display=f.get("display"), col_ref=f.get("col_ref"), op=f.get("op"), value=f.get("value")))
    return out


def r4_leading_wildcard(parsed, plan, engine="MySQL"):
    out = []
    for w in parsed["leading_wildcards"]:
        out.append(_problem(
            "R4", "medium", w["table"], "Leading wildcard in LIKE",
            f"LIKE '{w['pattern']}' starts with a wildcard, so a normal index on {w['column']} "
            f"cannot be used. Search from the start of the text, or use a full-text search index.",
            columns=[w["column"]], pattern=w["pattern"]))
    return out


def r6_filesort(parsed, plan, engine="MySQL"):
    out = []
    for step in plan:
        if not step["filesort"] or step["rows_examined"] < MIN_ROWS:
            continue
        t = step["table"]
        order = _cols(parsed["order_by"], t)
        if not order:
            continue
        out.append(_problem(
            "R6", "medium", t, "Extra sorting step",
            f"{engine} sorts the rows of '{t}' after reading them. Adding {', '.join(order)} "
            f"to the end of the index returns rows already in order, so the sort disappears.",
            columns=order))
    return out


ALL_RULES = [r1_full_scan, r2_composite, r3_function_on_column, r4_leading_wildcard, r6_filesort]


def run_rules(parsed, plan, engine: str = "MySQL") -> list:
    problems = []
    for rule in ALL_RULES:
        problems.extend(rule(parsed, plan, engine))
    problems.sort(key=lambda p: (SEVERITY_ORDER[p["severity"]], p["rule_code"]))
    return problems
