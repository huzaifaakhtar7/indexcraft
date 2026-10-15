import re

ACCESS_LABELS = {
    "system": "single row",
    "const": "single row by key",
    "eq_ref": "one row per join by unique key",
    "ref": "index lookup",
    "fulltext": "fulltext index",
    "ref_or_null": "index lookup with NULL",
    "index_merge": "several indexes merged",
    "unique_subquery": "unique subquery lookup",
    "index_subquery": "subquery index lookup",
    "range": "index range scan",
    "index": "full index scan",
    "ALL": "full table scan",
}


def _step(table, alias, access, index_used=None, rows=0, filesort=False, temporary=False,
          extra="", possible=None, filtered=100.0):
    return {
        "table": table,
        "alias": alias,
        "access": access,
        "access_label": ACCESS_LABELS.get(access, access),
        "full_scan": access == "ALL",
        "full_index_scan": access == "index",
        "index_used": index_used,
        "possible_indexes": possible or [],
        "rows_examined": int(rows or 0),
        "filtered_pct": float(filtered),
        "filesort": filesort,
        "temporary": temporary,
        "extra": extra,
    }


def normalize_mysql(explain_rows: list, alias_map: dict = None) -> list:
    alias_map = alias_map or {}
    steps = []
    for row in explain_rows:
        r = {str(k).lower(): v for k, v in row.items()}
        alias = r.get("table") or ""
        access = r.get("type") or ""
        extra = r.get("extra") or ""
        steps.append(_step(
            alias_map.get(alias.lower(), alias), alias, access,
            index_used=r.get("key"),
            rows=r.get("rows"),
            filesort="filesort" in extra.lower(),
            temporary="temporary" in extra.lower(),
            extra=extra,
            possible=[k for k in (r.get("possible_keys") or "").split(",") if k],
            filtered=r.get("filtered") or 100,
        ))
    return steps


_PG_SCANS = {"Seq Scan", "Index Scan", "Index Only Scan", "Bitmap Heap Scan"}
_PG_SORTS = {"Sort", "Incremental Sort"}
_PG_GROUPS = {"HashAggregate", "GroupAggregate", "Aggregate", "Unique"}
_RANGE_OPS = re.compile(r"(<=|>=|<>|!=|<|>|~~|\bbetween\b|\bany\b)", re.IGNORECASE)


def _pg_bitmap_index(node):
    for child in node.get("Plans", []):
        if child.get("Node Type") == "Bitmap Index Scan":
            return child.get("Index Name")
        name = _pg_bitmap_index(child)
        if name:
            return name
    return None


def _pg_access(node):
    kind = node["Node Type"]
    if kind == "Seq Scan":
        return "ALL", None
    cond = node.get("Index Cond") or node.get("Recheck Cond") or ""
    index = node.get("Index Name") or _pg_bitmap_index(node)
    if not cond:
        return "index", index
    return ("range" if _RANGE_OPS.search(cond) else "ref"), index


def normalize_postgres(explain: dict, alias_map: dict = None) -> list:
    alias_map = alias_map or {}
    table_rows = {k.lower(): v for k, v in (explain.get("table_rows") or {}).items()}
    steps = []

    def walk(node, sorted_above, grouped_above):
        kind = node.get("Node Type", "")
        sort_here = sorted_above or kind in _PG_SORTS
        group_here = grouped_above or kind in _PG_GROUPS
        if kind in _PG_SCANS and node.get("Relation Name"):
            table = node["Relation Name"]
            alias = node.get("Alias") or table
            access, index = _pg_access(node)
            rows = node.get("Plan Rows", 0)
            if access in ("ALL", "index"):
                rows = max(table_rows.get(table.lower(), 0), rows)
            extra = kind
            if node.get("Filter"):
                extra += f"; Filter: {node['Filter']}"
            if node.get("Index Cond") or node.get("Recheck Cond"):
                extra += f"; Cond: {node.get('Index Cond') or node.get('Recheck Cond')}"
            if sort_here:
                extra += "; Sort"
            steps.append(_step(
                alias_map.get(alias.lower(), table), alias, access,
                index_used=index, rows=rows, filesort=sort_here, temporary=group_here,
                extra=extra,
            ))
        for child in node.get("Plans", []):
            walk(child, sort_here, group_here)

    walk(explain["plan"], False, False)
    return steps


_SQLITE_LINE = re.compile(
    r"^(SCAN|SEARCH)\s+(?:TABLE\s+)?(\w+)(?:\s+AS\s+(\w+))?"
    r"(?:\s+USING\s+(AUTOMATIC\s+PARTIAL\s+COVERING\s+INDEX|AUTOMATIC\s+COVERING\s+INDEX|"
    r"AUTOMATIC\s+INDEX|COVERING\s+INDEX|INDEX|INTEGER\s+PRIMARY\s+KEY|PRIMARY\s+KEY)"
    r"(?:\s+(\w+))?)?\s*(?:\((.*)\))?",
    re.IGNORECASE,
)


def _sqlite_rows(stats: list, cond: str, total: int) -> int:
    terms = [t.strip() for t in re.split(r"\band\b", cond or "", flags=re.IGNORECASE) if t.strip()]
    eq = sum(1 for t in terms if re.search(r"=\?$", t) and not re.search(r"[<>!]=\?$", t))
    has_range = any(re.search(r"(<|>)", t) for t in terms)
    if stats and len(stats) > eq:
        rows = stats[eq] if eq else stats[0]
    elif eq:
        rows = max(1, total // 10 ** eq)
    else:
        rows = total
    if has_range:
        rows = max(1, rows // 4)
    return int(rows)


def normalize_sqlite(explain: dict, alias_map: dict = None) -> list:
    alias_map = alias_map or {}
    table_rows = {k.lower(): v for k, v in (explain.get("table_rows") or {}).items()}
    index_stats = {k.lower(): v for k, v in (explain.get("index_stats") or {}).items()}
    details = [r[-1] if isinstance(r, (list, tuple)) else r["detail"] for r in explain["rows"]]
    filesort = any("TEMP B-TREE FOR ORDER BY" in d.upper() or "TEMP B-TREE FOR RIGHT PART OF ORDER BY"
                   in d.upper() for d in details)
    temporary = any("TEMP B-TREE FOR GROUP BY" in d.upper() or "TEMP B-TREE FOR DISTINCT" in d.upper()
                    for d in details)
    steps = []
    for d in details:
        m = _SQLITE_LINE.match(d.strip())
        if not m:
            continue
        verb, name, as_alias, using, index, cond = m.groups()
        verb = verb.upper()
        using = re.sub(r"\s+", " ", (using or "").upper())
        alias = as_alias or name
        table = alias_map.get(alias.lower(), alias_map.get(name.lower(), name))
        total = table_rows.get(table.lower(), 0)
        if using.startswith("AUTOMATIC"):
            access, index, rows = "ALL", None, total
        elif verb == "SCAN":
            access = "index" if index else "ALL"
            rows = total
        elif using in ("INTEGER PRIMARY KEY", "PRIMARY KEY"):
            ranged = bool(re.search(r"[<>]", cond or ""))
            access, index = ("range" if ranged else "const"), "PRIMARY"
            rows = max(1, total // 4) if ranged else 1
        else:
            ranged = bool(re.search(r"[<>]", cond or ""))
            access = "range" if ranged else "ref"
            rows = _sqlite_rows(index_stats.get((index or "").lower()), cond, total)
        steps.append(_step(table, alias, access, index_used=index, rows=rows,
                           filesort=filesort, temporary=temporary, extra=d))
    return steps


_NORMALIZERS = {
    "mysql": lambda explain, alias_map: normalize_mysql(explain["rows"], alias_map),
    "postgres": normalize_postgres,
    "sqlite": normalize_sqlite,
}


def normalize(db_type: str, explain: dict, alias_map: dict = None) -> list:
    if db_type not in _NORMALIZERS:
        raise ValueError(f"No plan normalizer for {db_type}")
    return _NORMALIZERS[db_type](explain, alias_map)
