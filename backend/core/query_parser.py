import re

_STOP = {"on", "where", "join", "inner", "left", "right", "cross", "order",
         "group", "limit", "having", "using", "natural", "outer", "straight_join"}

_TABLE_RE = re.compile(r"\b(?:from|join)\s+`?(\w+)`?(?:\s+(?:as\s+)?`?(\w+)`?)?", re.I)
_JOIN_ON_RE = re.compile(r"\bon\s+`?(\w+)`?\.`?(\w+)`?\s*=\s*`?(\w+)`?\.`?(\w+)`?", re.I)
_CLAUSE_END = r"(?=\bgroup\s+by\b|\border\s+by\b|\blimit\b|\bhaving\b|$)"
_WHERE_RE = re.compile(r"\bwhere\b(.*?)" + _CLAUSE_END, re.I | re.S)
_ORDER_RE = re.compile(r"\border\s+by\b(.*?)(?=\blimit\b|$)", re.I | re.S)
_GROUP_RE = re.compile(r"\bgroup\s+by\b(.*?)(?=\bhaving\b|\border\s+by\b|\blimit\b|$)", re.I | re.S)
_COL = r"`?(?:(\w+)`?\.`?)?(\w+)`?"
_OPS = r"(=|>=|<=|<>|!=|>|<|between\b|in\b|like\b)"
_FUNC_RE = re.compile(r"^(\w+)\s*\(\s*" + _COL + r"\s*\)\s*" + _OPS + r"(.*)$", re.I | re.S)
_EXTRACT_RE = re.compile(r"^extract\s*\(\s*(\w+)\s+from\s+" + _COL + r"\s*\)\s*" + _OPS + r"(.*)$", re.I | re.S)
_STRFTIME_RE = re.compile(r"^strftime\s*\(\s*'([^']*)'\s*,\s*" + _COL + r"\s*\)\s*" + _OPS + r"(.*)$", re.I | re.S)
_INNER_FROM_RE = re.compile(r"\b(extract|substring|trim)\s*\(([^()]*?)\bfrom\b", re.I)
_STRFTIME_KIND ={"%y": "YEAR", "%y-%m-%d": "DATE"}
_LIKE_RE = re.compile(r"^" + _COL + r"\s+like\s+'([^']*)'", re.I)
_BETWEEN_RE = re.compile(r"^" + _COL + r"\s+between\b", re.I)
_IN_RE = re.compile(r"^" + _COL + r"\s+in\s*\(", re.I)
_CMP_RE = re.compile(r"^" + _COL + r"\s*(=|>=|<=|<>|!=|>|<)\s*(.+)$", re.I | re.S)
_IS_NULL_RE = re.compile(r"^" + _COL + r"\s+is\s+(not\s+)?null", re.I)
_COLREF_RE = re.compile(r"^`?(\w+)`?\.`?(\w+)`?$")


def _function_call(part: str):
    m = _EXTRACT_RE.match(part)
    if m:
        unit, prefix, column, op, value = m.groups()
        name = "YEAR" if unit.lower() == "year" else "EXTRACT"
        display = f"EXTRACT({unit.upper()} FROM {column})"
        return name, prefix, column, op, value, display
    m = _STRFTIME_RE.match(part)
    if m:
        fmt, prefix, column, op, value = m.groups()
        name = _STRFTIME_KIND.get(fmt.lower(), "STRFTIME")
        return name, prefix, column, op, value, f"strftime('{fmt}', {column})"
    m = _FUNC_RE.match(part)
    if m:
        func, prefix, column, op, value = m.groups()
        return func.upper(), prefix, column, op, value, f"{func.upper()}({column})"
    return None


def _clean(query: str) -> str:
    q = re.sub(r"--[^\n]*", " ", query)
    q = re.sub(r"/\*.*?\*/", " ", q, flags=re.S)
    q = q.strip().rstrip(";")
    return re.sub(r"\s+", " ", q).strip()


def _split_and(text: str) -> list:
    parts, depth, current, i = [], 0, "", 0
    lower = text.lower()
    in_between = False
    while i < len(text):
        ch = text[i]
        if ch == "'":
            end = text.find("'", i + 1)
            end = len(text) - 1 if end == -1 else end
            current += text[i:end + 1]
            i = end + 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if depth == 0 and lower.startswith("between", i) and (i == 0 or not lower[i - 1].isalnum()):
            in_between = True
        if depth == 0 and lower.startswith(" and ", i):
            if in_between:
                in_between = False
                current += text[i:i + 5]
            else:
                parts.append(current.strip())
                current = ""
            i += 5
            continue
        current += ch
        i += 1
    if current.strip():
        parts.append(current.strip())
    return parts


def _strip_parens(text: str) -> str:
    t = text.strip()
    while t.startswith("(") and t.endswith(")"):
        depth = 0
        balanced = True
        for idx, ch in enumerate(t):
            depth += ch == "("
            depth -= ch == ")"
            if depth == 0 and idx < len(t) - 1:
                balanced = False
                break
        if not balanced:
            break
        t = t[1:-1].strip()
    return t


class ParsedQuery(dict):
    pass


def parse_query(query: str, columns_by_table: dict = None) -> ParsedQuery:
    q = _clean(query)
    if not q.lower().startswith("select"):
        raise ValueError("Only SELECT queries are supported")

    tables, alias_map = [], {}
    for name, alias in _TABLE_RE.findall(_INNER_FROM_RE.sub(r"\1(\2 ", q)):
        if alias and alias.lower() in _STOP:
            alias = ""
        tables.append({"name": name, "alias": alias or name})
        alias_map[(alias or name).lower()] = name
        alias_map[name.lower()] = name

    columns_by_table = {k.lower(): {c.lower() for c in v} for k, v in (columns_by_table or {}).items()}

    def resolve(prefix, column):
        if prefix:
            return alias_map.get(prefix.lower(), prefix), column
        if len(tables) == 1:
            return tables[0]["name"], column
        for t in tables:
            if column.lower() in columns_by_table.get(t["name"].lower(), set()):
                return t["name"], column
        return None, column

    joins = []
    for a, ac, b, bc in _JOIN_ON_RE.findall(q):
        lt, lc = resolve(a, ac)
        rt, rc = resolve(b, bc)
        joins.append({"left": {"table": lt, "column": lc}, "right": {"table": rt, "column": rc}})

    conditions, functions, wildcards, unparsed = [], [], [], []
    has_or = False
    where = _WHERE_RE.search(q)
    if where:
        where_text = where.group(1).strip()
        if re.search(r"\bor\b", where_text, re.I):
            has_or = True
        for raw in _split_and(where_text):
            part = _strip_parens(raw)
            call = _function_call(part)
            if call:
                name, prefix, column, op, value, display = call
                t, c = resolve(prefix, column)
                functions.append({
                    "function": name, "table": t, "column": c, "text": part, "display": display,
                    "col_ref": f"{prefix}.{column}" if prefix else column,
                    "op": op.strip().upper(), "value": value.strip().strip("'"),
                })
                continue
            m = _LIKE_RE.match(part)
            if m:
                t, c = resolve(m.group(1), m.group(2))
                pattern = m.group(3)
                if pattern.startswith("%") or pattern.startswith("_"):
                    wildcards.append({"table": t, "column": c, "pattern": pattern})
                else:
                    conditions.append({"table": t, "column": c, "op": "LIKE", "kind": "range"})
                continue
            m = _BETWEEN_RE.match(part)
            if m:
                t, c = resolve(m.group(1), m.group(2))
                conditions.append({"table": t, "column": c, "op": "BETWEEN", "kind": "range"})
                continue
            m = _IN_RE.match(part)
            if m:
                t, c = resolve(m.group(1), m.group(2))
                conditions.append({"table": t, "column": c, "op": "IN", "kind": "equality"})
                continue
            m = _IS_NULL_RE.match(part)
            if m:
                t, c = resolve(m.group(1), m.group(2))
                conditions.append({"table": t, "column": c, "op": "IS NULL", "kind": "equality"})
                continue
            m = _CMP_RE.match(part)
            if m:
                t, c = resolve(m.group(1), m.group(2))
                op, value = m.group(3), m.group(4).strip()
                ref = _COLREF_RE.match(value)
                if ref and ref.group(1).lower() in alias_map:
                    rt, rc = resolve(ref.group(1), ref.group(2))
                    joins.append({"left": {"table": t, "column": c}, "right": {"table": rt, "column": rc}})
                    continue
                kind = "equality" if op == "=" else ("not_equal" if op in ("<>", "!=") else "range")
                conditions.append({"table": t, "column": c, "op": op, "kind": kind})
                continue
            unparsed.append(part)

    order_by = []
    m = _ORDER_RE.search(q)
    if m:
        for item in m.group(1).split(","):
            mm = re.match(r"^\s*" + _COL + r"(?:\s+(asc|desc))?\s*$", item, re.I)
            if mm:
                t, c = resolve(mm.group(1), mm.group(2))
                order_by.append({"table": t, "column": c, "direction": (mm.group(3) or "ASC").upper()})

    group_by = []
    m = _GROUP_RE.search(q)
    if m:
        for item in m.group(1).split(","):
            mm = re.match(r"^\s*" + _COL + r"\s*$", item)
            if mm:
                t, c = resolve(mm.group(1), mm.group(2))
                group_by.append({"table": t, "column": c})

    limit = None
    m = re.search(r"\blimit\s+(\d+)(?:\s*,\s*(\d+))?", q, re.I)
    if m:
        limit = int(m.group(2) or m.group(1))

    return ParsedQuery(
        query=q,
        tables=tables,
        alias_map=alias_map,
        joins=joins,
        conditions=conditions,
        functions=functions,
        leading_wildcards=wildcards,
        order_by=order_by,
        group_by=group_by,
        limit=limit,
        has_or=has_or,
        select_star=bool(re.match(r"select\s+\*", q, re.I)),
        unparsed=unparsed,
    )
