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


def normalize_mysql(explain_rows: list, alias_map: dict = None) -> list:
    alias_map = alias_map or {}
    steps = []
    for row in explain_rows:
        r = {str(k).lower(): v for k, v in row.items()}
        alias = r.get("table") or ""
        access = r.get("type") or ""
        extra = r.get("extra") or ""
        steps.append({
            "table": alias_map.get(alias.lower(), alias),
            "alias": alias,
            "access": access,
            "access_label": ACCESS_LABELS.get(access, access),
            "full_scan": access == "ALL",
            "full_index_scan": access == "index",
            "index_used": r.get("key"),
            "possible_indexes": [k for k in (r.get("possible_keys") or "").split(",") if k],
            "rows_examined": int(r.get("rows") or 0),
            "filtered_pct": float(r.get("filtered") or 100),
            "filesort": "filesort" in extra.lower(),
            "temporary": "temporary" in extra.lower(),
            "extra": extra,
        })
    return steps
