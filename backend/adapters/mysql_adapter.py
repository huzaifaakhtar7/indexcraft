import statistics
import time

import mysql.connector

from adapters.base import TIMEOUT_MS, BaseAdapter, check_create_index, table_from_ddl
from adapters.base import check_ident as _check_ident
from core.benchmark import median_ms
from core.query_guard import check_select as _check_select


class MySQLAdapter(BaseAdapter):
    name = "mysql"
    label = "MySQL"

    def __init__(self):
        self.conn = None
        self.database = None
        self.clone_db = None
        self.cloned_tables = set()

    def connect(self, config: dict) -> None:
        self.database = _check_ident(config["database"])
        self.conn = mysql.connector.connect(
            host=config.get("host") or "localhost",
            port=int(config.get("port") or 3306),
            user=config.get("user") or "root",
            password=config.get("password") or "",
            database=self.database,
            autocommit=True,
            connection_timeout=10,
        )
        for sql in (f"SET SESSION max_execution_time = {TIMEOUT_MS}",
                    f"SET SESSION max_statement_time = {TIMEOUT_MS / 1000}"):
            try:
                self._exec(sql)
            except mysql.connector.Error:
                pass

    def close(self) -> None:
        if self.conn is not None:
            try:
                self.conn.close()
            finally:
                self.conn = None

    def _rows(self, sql: str, params=None) -> list:
        cur = self.conn.cursor(dictionary=True)
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        cur.close()
        return rows

    def _exec(self, sql: str, params=None) -> None:
        cur = self.conn.cursor()
        cur.execute(sql, params or ())
        if cur.with_rows:
            cur.fetchall()
        cur.close()

    def _use(self, database: str) -> None:
        self._exec(f"USE `{_check_ident(database)}`")

    def _target(self, on_clone: bool) -> str:
        return self.clone_db if on_clone and self.clone_db else self.database

    def explain(self, query: str, on_clone: bool = False) -> dict:
        q = _check_select(query)
        self._use(self._target(on_clone))
        try:
            rows = self._rows(f"EXPLAIN {q}")
        finally:
            self._use(self.database)
        return {"rows": rows}

    def run_timed(self, query: str, runs: int = 5, on_clone: bool = False) -> dict:
        q = _check_select(query)
        self._use(self._target(on_clone))

        def run():
            cur = self.conn.cursor()
            cur.execute(q)
            n = len(cur.fetchall())
            cur.close()
            return n

        try:
            stats = median_ms(run, runs=runs)
        finally:
            self._use(self.database)
        stats["rows_returned"] = stats.pop("result")
        return stats

    def list_tables(self) -> list:
        return self._rows(
            "SELECT table_name AS name, table_rows AS approx_rows "
            "FROM information_schema.tables "
            "WHERE table_schema = %s AND table_type = 'BASE TABLE' "
            "ORDER BY table_name",
            (self.database,),
        )

    def table_rows(self, table: str) -> int:
        row = self._rows(f"SELECT COUNT(*) AS n FROM `{_check_ident(table)}`")[0]
        return int(row["n"])

    def list_columns(self, table: str) -> list:
        rows = self._rows(
            "SELECT column_name AS name FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position",
            (self.database, _check_ident(table)),
        )
        return [r["name"] for r in rows]

    def list_indexes(self, table: str, on_clone: bool = False) -> list:
        rows = self._rows(
            "SELECT index_name, seq_in_index, column_name, non_unique "
            "FROM information_schema.statistics "
            "WHERE table_schema = %s AND table_name = %s "
            "ORDER BY index_name, seq_in_index",
            (self._target(on_clone), _check_ident(table)),
        )
        indexes = {}
        for r in rows:
            r = {k.lower(): v for k, v in r.items()}
            item = indexes.setdefault(
                r["index_name"],
                {"name": r["index_name"], "columns": [], "unique": not r["non_unique"],
                 "primary": r["index_name"] == "PRIMARY"},
            )
            item["columns"].append(r["column_name"])
        return list(indexes.values())

    def column_stats(self, table: str, column: str) -> dict:
        t = _check_ident(table)
        c = _check_ident(column)
        row = self._rows(
            f"SELECT COUNT(*) AS total, COUNT(DISTINCT `{c}`) AS distinct_values FROM `{t}`"
        )[0]
        total = int(row["total"])
        distinct = int(row["distinct_values"])
        return {
            "table": t,
            "column": c,
            "total_rows": total,
            "distinct_values": distinct,
            "selectivity": round(distinct / total, 6) if total else 0,
        }

    def make_clone(self, tables: list) -> str:
        wanted = {_check_ident(t) for t in tables}
        if not self.clone_db:
            self.clone_db = f"{self.database}_ic_clone"
            self._exec(f"DROP DATABASE IF EXISTS `{self.clone_db}`")
            self._exec(f"CREATE DATABASE `{self.clone_db}`")
            self.cloned_tables = set()
        for t in sorted(wanted - self.cloned_tables):
            self._exec(f"CREATE TABLE `{self.clone_db}`.`{t}` LIKE `{self.database}`.`{t}`")
            self._exec(f"INSERT INTO `{self.clone_db}`.`{t}` SELECT * FROM `{self.database}`.`{t}`")
            self._exec(f"ANALYZE TABLE `{self.clone_db}`.`{t}`")
            self.cloned_tables.add(t)
        return self.clone_db

    def create_index(self, ddl: str, on_clone: bool = True) -> None:
        ddl = check_create_index(ddl)
        if on_clone and not self.clone_db:
            raise RuntimeError("Create a clone first")
        self._use(self._target(on_clone))
        try:
            self._exec(ddl)
            table = table_from_ddl(ddl)
            if table:
                self._exec(f"ANALYZE TABLE `{_check_ident(table)}`")
        finally:
            self._use(self.database)

    def drop_index_sql(self, table: str, index_name: str) -> str:
        return f"DROP INDEX {index_name} ON {table}"

    def drop_index(self, table: str, index_name: str, on_clone: bool = True) -> None:
        self._exec(
            f"DROP INDEX `{_check_ident(index_name)}` ON "
            f"`{self._target(on_clone)}`.`{_check_ident(table)}`"
        )

    def measure_insert(self, table: str, n_rows: int = 10_000, on_clone: bool = True,
                       repeats: int = 3) -> float:
        db = self._target(on_clone)
        t = _check_ident(table)
        tmp = f"{t}_ic_insert_test"
        timings = []
        for _ in range(repeats):
            self._exec(f"DROP TABLE IF EXISTS `{db}`.`{tmp}`")
            self._exec(f"CREATE TABLE `{db}`.`{tmp}` LIKE `{db}`.`{t}`")
            start = time.perf_counter()
            self._exec(
                f"INSERT INTO `{db}`.`{tmp}` SELECT * FROM `{db}`.`{t}` LIMIT {int(n_rows)}"
            )
            timings.append((time.perf_counter() - start) * 1000)
            self._exec(f"DROP TABLE `{db}`.`{tmp}`")
        return round(statistics.median(timings), 2)

    def index_size(self, index_name: str, table: str = None, on_clone: bool = True) -> int:
        sql = (
            "SELECT SUM(stat_value) * @@innodb_page_size AS bytes "
            "FROM mysql.innodb_index_stats "
            "WHERE database_name = %s AND index_name = %s AND stat_name = 'size'"
        )
        params = [self._target(on_clone), _check_ident(index_name)]
        if table:
            sql += " AND table_name = %s"
            params.append(_check_ident(table))
        try:
            row = self._rows(sql, tuple(params))[0]
            return int(row["bytes"] or 0)
        except mysql.connector.Error:
            return 0

    def drop_clone(self) -> None:
        if self.clone_db:
            self._exec(f"DROP DATABASE IF EXISTS `{self.clone_db}`")
            self.clone_db = None
            self.cloned_tables = set()
