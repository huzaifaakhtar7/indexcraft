import re

import sqlparse

_STRINGS = re.compile(r"'(?:[^']|'')*'")
_BLOCKED = re.compile(
    r"\b(into|insert|update|delete|drop|alter|create|truncate|grant|revoke|"
    r"copy|attach|detach|pragma|vacuum|load_file|sleep|pg_sleep|benchmark|"
    r"pg_terminate_backend|pg_cancel_backend|pg_read_file|pg_write_file|lo_import|lo_export)\b"
    r"|\bfor\s+(update|share)\b",
    re.IGNORECASE,
)


def check_select(query: str) -> str:
    if not query or not query.strip():
        raise ValueError("The query is empty")
    statements = [s for s in sqlparse.split(query) if s.strip().rstrip(";").strip()]
    if len(statements) != 1:
        raise ValueError("Only one statement is allowed")
    q = sqlparse.format(statements[0], strip_comments=True).strip().rstrip(";").strip()
    if not re.match(r"^select\b", q, re.IGNORECASE):
        raise ValueError("Only SELECT queries are allowed")
    without_strings = _STRINGS.sub("''", q)
    if ";" in without_strings:
        raise ValueError("Only one statement is allowed")
    m = _BLOCKED.search(without_strings)
    if m:
        raise ValueError(f"'{m.group(0).upper()}' is not allowed. Only a plain SELECT can be analyzed")
    return q
