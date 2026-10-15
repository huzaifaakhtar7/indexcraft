import os
import re
import sqlite3
import statistics
import tempfile
import time
import uuid
from pathlib import Path

from adapters.base import TIMEOUT_MS, BaseAdapter, check_create_index, check_ident, table_from_ddl
from core.benchmark import median_ms
from core.query_guard import check_select

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _q(name: str) -> str:
    return '"' + check_ident(name) + '"'


def resolve_path(database: str) -> Path:
    raw = (database or "").strip()
    if not raw:
        raise ValueError("Give the path of the SQLite .db file")
    candidates = [Path(raw)]
    if not Path(raw).is_absolute():
        candidates.append(DATA_DIR / raw)
        if not raw.lower().endswith(".db"):
            candidates += [Path(raw + ".db"), DATA_DIR / (raw + ".db")]
    for c in candidates:
        if c.is_file():
            return c.resolve()
    raise FileNotFoundError(f"SQLite file not found: {raw}")


def _open(path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


class SQLiteAdapter(BaseAdapter):
    name = "sqlite"
    label = "SQLite"

    def __init__(self):
        self.conn = None
        self.clone_conn = None
        self.path = None
        self.database = None
        self.clone_path = None
        self.cloned_tables = set()
        self._index_bytes = {}

    def connect(self, config: dict) -> None:
        self.path = resolve_path(config.get("database"))
        self.database = self.path.name
        self.conn = _open(self.path)
        self.conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchall()

    def close(self) -> None:
        self.drop_clone()
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def _db(self, on_clone: bool) -> sqlite3.Connection:
        return self.clone_conn if on_clone and self.clone_conn else self.conn

    def _rows(self, sql: str, params=(), on_clone: bool = False) -> list:
        return [dict(r) for r in self._db(on_clone).execute(sql, params).fetchall()]

    def _with_timeout(self, conn, fn):
        deadline = time.perf_counter() + TIMEOUT_MS / 1000
        conn.set_progress_handler(lambda: 1 if time.perf_counter() > deadline else 0, 10_000)
        try:
            return fn()
        except sqlite3.OperationalError as e:
            if "interrupted" in str(e).lower():
                raise TimeoutError(f"The query took longer than {TIMEOUT_MS // 1000} seconds") from e
            raise
        finally:
            conn.set_progress_handler(None, 0)

    def _stat_rows(self, conn, table: str):
        try:
            return conn.execute("SELECT idx, stat FROM sqlite_stat1 WHERE tbl = ?", (table,)).fetchall()
        except sqlite3.OperationalError:
            return []

    def _count(self, conn, table: str) -> int:
        for r in self._stat_rows(conn, table):
            if r["stat"]:
                return int(r["stat"].split()[0])
        return int(conn.execute(f"SELECT COUNT(*) FROM {_q(table)}").fetchone()[0])

    def explain(self, query: str, on_clone: bool = False) -> dict:
        q = check_select(query)
        conn = self._db(on_clone)
        rows = [tuple(r) for r in conn.execute(f"EXPLAIN QUERY PLAN {q}").fetchall()]
        tables = {t for (t,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")}
        mentioned = {t for t in tables if re.search(rf"\b{re.escape(t)}\b", q, re.IGNORECASE)}
        table_rows, index_stats = {}, {}
        for t in mentioned:
            table_rows[t] = self._count(conn, t)
            for r in self._stat_rows(conn, t):
                if r["idx"]:
                    index_stats[r["idx"]] = [int(x) for x in r["stat"].split() if x.isdigit()]
        return {"rows": rows, "table_rows": table_rows, "index_stats": index_stats}

    def run_timed(self, query: str, runs: int = 5, on_clone: bool = False) -> dict:
        q = check_select(query)
        conn = self._db(on_clone)

        def run():
            return len(conn.execute(q).fetchall())

        stats = self._with_timeout(conn, lambda: median_ms(run, runs=runs))
        stats["rows_returned"] = stats.pop("result")
        return stats

    def list_tables(self) -> list:
        names = [r["name"] for r in self._rows(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name")]
        return [{"name": n, "approx_rows": self._count(self.conn, n)} for n in names]

    def table_rows(self, table: str) -> int:
        return int(self.conn.execute(f"SELECT COUNT(*) FROM {_q(table)}").fetchone()[0])

    def list_columns(self, table: str) -> list:
        return [r["name"] for r in self._rows(f"PRAGMA table_info({_q(table)})")]

    def list_indexes(self, table: str, on_clone: bool = False) -> list:
        out = []
        for idx in self._rows(f"PRAGMA index_list({_q(table)})", on_clone=on_clone):
            cols = self._rows(f"PRAGMA index_info({_q(idx['name'])})", on_clone=on_clone)
            out.append({
                "name": idx["name"],
                "columns": [c["name"] for c in sorted(cols, key=lambda c: c["seqno"])],
                "unique": bool(idx["unique"]),
                "primary": idx["origin"] == "pk",
            })
        pk = [r["name"] for r in self._rows(f"PRAGMA table_info({_q(table)})", on_clone=on_clone)
              if r["pk"]]
        if pk and not any(i["primary"] for i in out):
            out.insert(0, {"name": "PRIMARY", "columns": pk, "unique": True, "primary": True})
        return out

    def column_stats(self, table: str, column: str) -> dict:
        t, c = check_ident(table), check_ident(column)
        row = self.conn.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT {_q(c)}) FROM {_q(t)}").fetchone()
        total, distinct = int(row[0]), int(row[1])
        return {
            "table": t,
            "column": c,
            "total_rows": total,
            "distinct_values": distinct,
            "selectivity": round(distinct / total, 6) if total else 0,
        }

    def _schema_sql(self, conn, table: str, prefix: str = "") -> tuple:
        master = f"{prefix}sqlite_master" if prefix else "sqlite_master"
        row = conn.execute(f"SELECT sql FROM {master} WHERE type = 'table' AND name = ?",
                           (table,)).fetchone()
        if not row:
            raise LookupError(f"Table '{table}' does not exist")
        indexes = [r[0] for r in conn.execute(
            f"SELECT sql FROM {master} WHERE type = 'index' AND tbl_name = ? AND sql IS NOT NULL",
            (table,))]
        return row[0], indexes

    def make_clone(self, tables: list) -> str:
        wanted = {check_ident(t) for t in tables}
        if not self.clone_conn:
            self.clone_path = Path(tempfile.gettempdir()) / f"ic_clone_{uuid.uuid4().hex[:8]}.db"
            self.clone_conn = _open(self.clone_path)
            self.cloned_tables = set()
        conn = self.clone_conn
        conn.execute("ATTACH DATABASE ? AS src", (str(self.path),))
        try:
            for t in sorted(wanted - self.cloned_tables):
                table_sql, index_sqls = self._schema_sql(conn, t, prefix="src.")
                conn.execute("BEGIN")
                conn.execute(table_sql)
                conn.execute(f"INSERT INTO main.{_q(t)} SELECT * FROM src.{_q(t)}")
                conn.execute("COMMIT")
                for sql in index_sqls:
                    conn.execute(sql)
                self.cloned_tables.add(t)
        finally:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            conn.execute("DETACH DATABASE src")
        conn.execute("ANALYZE")
        return str(self.clone_path)

    def _bytes(self, conn) -> int:
        pages = conn.execute("PRAGMA page_count").fetchone()[0]
        free = conn.execute("PRAGMA freelist_count").fetchone()[0]
        size = conn.execute("PRAGMA page_size").fetchone()[0]
        return (pages - free) * size

    def create_index(self, ddl: str, on_clone: bool = True) -> None:
        ddl = check_create_index(ddl)
        if on_clone and not self.clone_conn:
            raise RuntimeError("Create a clone first")
        conn = self._db(on_clone)
        before = self._bytes(conn)
        conn.execute(ddl)
        after = self._bytes(conn)
        name = re.match(r"^create\s+(?:unique\s+)?index\s+(?:if\s+not\s+exists\s+)?[\"`]?(\w+)",
                        ddl, re.IGNORECASE)
        if name:
            self._index_bytes[(on_clone, name.group(1).lower())] = max(after - before, 0)
        table = table_from_ddl(ddl)
        if table:
            conn.execute(f"ANALYZE {_q(table)}")

    def drop_index(self, table: str, index_name: str, on_clone: bool = True) -> None:
        self._db(on_clone).execute(f"DROP INDEX IF EXISTS {_q(index_name)}")
        self._index_bytes.pop((on_clone, index_name.lower()), None)

    def measure_insert(self, table: str, n_rows: int = 10_000, on_clone: bool = True,
                       repeats: int = 3) -> float:
        conn = self._db(on_clone)
        t = check_ident(table)
        tmp = f"{t}_ic_insert_test"
        table_sql, index_sqls = self._schema_sql(conn, t)
        create_tmp = re.sub(r"^\s*create\s+table\s+(?:if\s+not\s+exists\s+)?[\"`\[]?\w+[\"`\]]?",
                            f"CREATE TABLE {_q(tmp)}", table_sql, count=1, flags=re.IGNORECASE)
        index_tmp = []
        for i, sql in enumerate(index_sqls):
            sql = re.sub(r"^\s*create\s+(unique\s+)?index\s+(?:if\s+not\s+exists\s+)?[\"`]?\w+[\"`]?",
                         lambda m: f"CREATE {m.group(1) or ''}INDEX {_q(f'{tmp}_ix{i}')}",
                         sql, count=1, flags=re.IGNORECASE)
            sql = re.sub(r"\bon\s+[\"`]?\w+[\"`]?", f"ON {_q(tmp)}", sql, count=1, flags=re.IGNORECASE)
            index_tmp.append(sql)
        timings = []
        for _ in range(repeats):
            conn.execute(f"DROP TABLE IF EXISTS {_q(tmp)}")
            conn.execute(create_tmp)
            for sql in index_tmp:
                conn.execute(sql)
            start = time.perf_counter()
            conn.execute("BEGIN")
            conn.execute(f"INSERT INTO {_q(tmp)} SELECT * FROM {_q(t)} LIMIT {int(n_rows)}")
            conn.execute("COMMIT")
            timings.append((time.perf_counter() - start) * 1000)
            conn.execute(f"DROP TABLE {_q(tmp)}")
        return round(statistics.median(timings), 2)

    def index_size(self, index_name: str, table: str = None, on_clone: bool = True) -> int:
        key = (on_clone, check_ident(index_name).lower())
        if key in self._index_bytes:
            return self._index_bytes[key]
        try:
            row = self._db(on_clone).execute(
                "SELECT SUM(pgsize) FROM dbstat WHERE name = ?", (index_name,)).fetchone()
            return int(row[0] or 0)
        except sqlite3.OperationalError:
            return 0

    def drop_clone(self) -> None:
        if self.clone_conn is not None:
            self.clone_conn.close()
            self.clone_conn = None
        if self.clone_path:
            for suffix in ("", "-journal", "-wal", "-shm"):
                try:
                    os.remove(f"{self.clone_path}{suffix}")
                except FileNotFoundError:
                    pass
            self.clone_path = None
        self.cloned_tables = set()
        self._index_bytes = {k: v for k, v in self._index_bytes.items() if not k[0]}
