import statistics
import time

import psycopg2
import psycopg2.extras

from adapters.base import TIMEOUT_MS, BaseAdapter, check_create_index, check_ident, table_from_ddl
from core.benchmark import median_ms
from core.query_guard import check_select

CLONE_SCHEMA = "ic_clone"


def _q(name: str) -> str:
    return '"' + check_ident(name).lower() + '"'


class PostgresAdapter(BaseAdapter):
    name = "postgres"
    label = "PostgreSQL"

    def __init__(self):
        self.conn = None
        self.database = None
        self.schema = "public"
        self.clone_schema = None
        self.cloned_tables = set()

    def connect(self, config: dict) -> None:
        self.database = config["database"]
        self.schema = check_ident(config.get("schema") or "public").lower()
        self.conn = psycopg2.connect(
            host=config.get("host") or "localhost",
            port=int(config.get("port") or 5432),
            user=config.get("user") or "postgres",
            password=config.get("password") or "",
            dbname=self.database,
            connect_timeout=10,
            options=f"-c statement_timeout={TIMEOUT_MS}",
        )
        self.conn.autocommit = True
        self._set_path(self.schema)

    def close(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            finally:
                self.conn = None

    def _rows(self, sql: str, params=None) -> list:
        with self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def _exec(self, sql: str, params=None) -> None:
        with self.conn.cursor() as cur:
            cur.execute(sql, params)

    def _set_path(self, schema: str) -> None:
        self._exec(f"SET search_path TO {_q(schema)}")

    def _target(self, on_clone: bool) -> str:
        return self.clone_schema if on_clone and self.clone_schema else self.schema

    def _reltuples(self, schema: str, tables: list) -> dict:
        if not tables:
            return {}
        rows = self._rows(
            "SELECT c.relname AS name, c.reltuples::bigint AS n FROM pg_class c "
            "JOIN pg_namespace s ON s.oid = c.relnamespace "
            "WHERE s.nspname = %s AND c.relname = ANY(%s)",
            (schema, [t.lower() for t in tables]),
        )
        return {r["name"]: max(int(r["n"]), 0) for r in rows}

    def explain(self, query: str, on_clone: bool = False) -> dict:
        q = check_select(query)
        schema = self._target(on_clone)
        self._set_path(schema)
        try:
            with self.conn.cursor() as cur:
                cur.execute(f"EXPLAIN (FORMAT JSON) {q}")
                data = cur.fetchone()[0]
        finally:
            self._set_path(self.schema)
        plan = data[0]["Plan"]
        relations = set()

        def collect(node):
            if node.get("Relation Name"):
                relations.add(node["Relation Name"])
            for child in node.get("Plans", []):
                collect(child)

        collect(plan)
        return {"plan": plan, "table_rows": self._reltuples(schema, sorted(relations))}

    def run_timed(self, query: str, runs: int = 5, on_clone: bool = False) -> dict:
        q = check_select(query)
        self._set_path(self._target(on_clone))

        def run():
            with self.conn.cursor() as cur:
                cur.execute(q)
                return len(cur.fetchall())

        try:
            stats = median_ms(run, runs=runs)
        finally:
            self._set_path(self.schema)
        stats["rows_returned"] = stats.pop("result")
        return stats

    def list_tables(self) -> list:
        return self._rows(
            "SELECT c.relname AS name, GREATEST(c.reltuples, 0)::bigint AS approx_rows "
            "FROM pg_class c JOIN pg_namespace s ON s.oid = c.relnamespace "
            "WHERE s.nspname = %s AND c.relkind IN ('r', 'p') ORDER BY c.relname",
            (self.schema,),
        )

    def table_rows(self, table: str) -> int:
        return int(self._rows(f"SELECT COUNT(*) AS n FROM {_q(self.schema)}.{_q(table)}")[0]["n"])

    def list_columns(self, table: str) -> list:
        rows = self._rows(
            "SELECT column_name AS name FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
            (self.schema, check_ident(table).lower()),
        )
        return [r["name"] for r in rows]

    def list_indexes(self, table: str, on_clone: bool = False) -> list:
        rows = self._rows(
            "SELECT i.relname AS index_name, ix.indisunique AS is_unique, "
            "ix.indisprimary AS is_primary, a.attname AS column_name, k.ord "
            "FROM pg_index ix "
            "JOIN pg_class t ON t.oid = ix.indrelid "
            "JOIN pg_class i ON i.oid = ix.indexrelid "
            "JOIN pg_namespace s ON s.oid = t.relnamespace "
            "CROSS JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS k(attnum, ord) "
            "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum "
            "WHERE s.nspname = %s AND t.relname = %s "
            "ORDER BY i.relname, k.ord",
            (self._target(on_clone), check_ident(table).lower()),
        )
        indexes = {}
        for r in rows:
            item = indexes.setdefault(r["index_name"], {
                "name": r["index_name"], "columns": [],
                "unique": bool(r["is_unique"]), "primary": bool(r["is_primary"]),
            })
            item["columns"].append(r["column_name"])
        return list(indexes.values())

    def column_stats(self, table: str, column: str) -> dict:
        t, c = check_ident(table), check_ident(column)
        row = self._rows(
            f"SELECT COUNT(*) AS total, COUNT(DISTINCT {_q(c)}) AS distinct_values "
            f"FROM {_q(self.schema)}.{_q(t)}"
        )[0]
        total, distinct = int(row["total"]), int(row["distinct_values"])
        return {
            "table": t,
            "column": c,
            "total_rows": total,
            "distinct_values": distinct,
            "selectivity": round(distinct / total, 6) if total else 0,
        }

    def make_clone(self, tables: list) -> str:
        wanted = {check_ident(t).lower() for t in tables}
        if not self.clone_schema:
            self.clone_schema = CLONE_SCHEMA
            self._exec(f"DROP SCHEMA IF EXISTS {_q(self.clone_schema)} CASCADE")
            self._exec(f"CREATE SCHEMA {_q(self.clone_schema)}")
            self.cloned_tables = set()
        src, dst = _q(self.schema), _q(self.clone_schema)
        for t in sorted(wanted - self.cloned_tables):
            self._exec(f"CREATE TABLE {dst}.{_q(t)} (LIKE {src}.{_q(t)} INCLUDING ALL)")
            self._exec(f"INSERT INTO {dst}.{_q(t)} SELECT * FROM {src}.{_q(t)}")
            self._exec(f"ANALYZE {dst}.{_q(t)}")
            self.cloned_tables.add(t)
        return self.clone_schema

    def create_index(self, ddl: str, on_clone: bool = True) -> None:
        ddl = check_create_index(ddl)
        if on_clone and not self.clone_schema:
            raise RuntimeError("Create a clone first")
        schema = self._target(on_clone)
        self._set_path(schema)
        try:
            self._exec(ddl)
            table = table_from_ddl(ddl)
            if table:
                self._exec(f"ANALYZE {_q(schema)}.{_q(table)}")
        finally:
            self._set_path(self.schema)

    def drop_index(self, table: str, index_name: str, on_clone: bool = True) -> None:
        self._exec(f"DROP INDEX IF EXISTS {_q(self._target(on_clone))}.{_q(index_name)}")

    def measure_insert(self, table: str, n_rows: int = 10_000, on_clone: bool = True,
                       repeats: int = 3) -> float:
        schema = _q(self._target(on_clone))
        t = _q(table)
        tmp = _q(f"{check_ident(table)}_ic_insert_test")
        timings = []
        for _ in range(repeats):
            self._exec(f"DROP TABLE IF EXISTS {schema}.{tmp}")
            self._exec(f"CREATE TABLE {schema}.{tmp} (LIKE {schema}.{t} INCLUDING ALL)")
            start = time.perf_counter()
            self._exec(f"INSERT INTO {schema}.{tmp} SELECT * FROM {schema}.{t} LIMIT {int(n_rows)}")
            timings.append((time.perf_counter() - start) * 1000)
            self._exec(f"DROP TABLE {schema}.{tmp}")
        return round(statistics.median(timings), 2)

    def index_size(self, index_name: str, table: str = None, on_clone: bool = True) -> int:
        rows = self._rows(
            "SELECT pg_relation_size(c.oid) AS bytes FROM pg_class c "
            "JOIN pg_namespace s ON s.oid = c.relnamespace "
            "WHERE s.nspname = %s AND c.relname = %s AND c.relkind = 'i'",
            (self._target(on_clone), check_ident(index_name).lower()),
        )
        return int(rows[0]["bytes"]) if rows else 0

    def drop_clone(self) -> None:
        if self.clone_schema and self.conn is not None:
            self._exec(f"DROP SCHEMA IF EXISTS {_q(self.clone_schema)} CASCADE")
        self.clone_schema = None
        self.cloned_tables = set()
