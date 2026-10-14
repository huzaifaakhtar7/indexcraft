import re
import time

import mysql.connector

from adapters.base import BaseAdapter
from core.benchmark import median_ms

_IDENT = re.compile(r"^[A-Za-z0-9_]+$")


def _check_ident(name: str) -> str:
    if not _IDENT.match(name or ""):
        raise ValueError(f"Invalid name: {name}")
    return name


def _check_select(query: str) -> str:
    q = query.strip().rstrip(";").strip()
    if ";" in q:
        raise ValueError("Only one statement is allowed")
    if not q.lower().startswith("select"):
        raise ValueError("Only SELECT queries are allowed")
    return q


class MySQLAdapter(BaseAdapter):
    name = "mysql"

    def __init__(self):
        self.conn = None
        self.database = None
        self.clone_db = None

    def connect(self, config: dict) -> None:
        self.database = _check_ident(config["database"])
        self.conn = mysql.connector.connect(
            host=config.get("host", "localhost"),
            port=int(config.get("port", 3306)),
            user=config.get("user", "root"),
            password=config.get("password", ""),
            database=self.database,
            autocommit=True,
        )

    def close(self) -> None:
        if self.conn is not None:
            self.conn.close()
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

    def explain(self, query: str, on_clone: bool = False) -> dict:
        q = _check_select(query)
        self._use(self.clone_db if on_clone and self.clone_db else self.database)
        rows = self._rows(f"EXPLAIN {q}")
        self._use(self.database)
        return {"rows": rows}

    def run_timed(self, query: str, runs: int = 5, on_clone: bool = False) -> dict:
        q = _check_select(query)
        self._use(self.clone_db if on_clone and self.clone_db else self.database)

        def run():
            cur = self.conn.cursor()
            cur.execute(q)
            n = len(cur.fetchall())
            cur.close()
            return n

        stats = median_ms(run, runs=runs)
        self._use(self.database)
        stats["rows_returned"] = stats.pop("result")
        return stats

    def list_tables(self) -> list:
        rows = self._rows(
            "SELECT table_name AS name, table_rows AS approx_rows "
            "FROM information_schema.tables "
            "WHERE table_schema = %s AND table_type = 'BASE TABLE' "
            "ORDER BY table_name",
            (self.database,),
        )
        return rows

    def list_indexes(self, table: str, on_clone: bool = False) -> list:
        db = self.clone_db if on_clone and self.clone_db else self.database
        rows = self._rows(
            "SELECT index_name, seq_in_index, column_name, non_unique "
            "FROM information_schema.statistics "
            "WHERE table_schema = %s AND table_name = %s "
            "ORDER BY index_name, seq_in_index",
            (db, _check_ident(table)),
        )
        indexes = {}
        for r in rows:
            r = {k.lower(): v for k, v in r.items()}
            item = indexes.setdefault(
                r["index_name"],
                {"name": r["index_name"], "columns": [], "unique": not r["non_unique"]},
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
        self.clone_db = f"{self.database}_ic_clone"
        self._exec(f"DROP DATABASE IF EXISTS `{self.clone_db}`")
        self._exec(f"CREATE DATABASE `{self.clone_db}`")
        for table in tables:
            t = _check_ident(table)
            self._exec(f"CREATE TABLE `{self.clone_db}`.`{t}` LIKE `{self.database}`.`{t}`")
            self._exec(f"INSERT INTO `{self.clone_db}`.`{t}` SELECT * FROM `{self.database}`.`{t}`")
            self._exec(f"ANALYZE TABLE `{self.clone_db}`.`{t}`")
        return self.clone_db

    def create_index(self, ddl: str, on_clone: bool = True) -> None:
        if not ddl.strip().lower().startswith("create index"):
            raise ValueError("Only CREATE INDEX statements are allowed")
        if on_clone and not self.clone_db:
            raise RuntimeError("Create a clone first")
        self._use(self.clone_db if on_clone else self.database)
        self._exec(ddl.strip().rstrip(";"))
        table = re.search(r"\bon\s+`?([A-Za-z0-9_]+)`?", ddl, re.IGNORECASE)
        if table:
            self._exec(f"ANALYZE TABLE `{table.group(1)}`")
        self._use(self.database)

    def drop_index(self, table: str, index_name: str, on_clone: bool = True) -> None:
        db = self.clone_db if on_clone and self.clone_db else self.database
        self._exec(
            f"DROP INDEX `{_check_ident(index_name)}` ON `{db}`.`{_check_ident(table)}`"
        )

    def measure_insert(self, table: str, n_rows: int = 10_000, on_clone: bool = True) -> float:
        db = self.clone_db if on_clone and self.clone_db else self.database
        t = _check_ident(table)
        tmp = f"{t}_ic_insert_test"
        self._exec(f"DROP TABLE IF EXISTS `{db}`.`{tmp}`")
        self._exec(f"CREATE TABLE `{db}`.`{tmp}` LIKE `{db}`.`{t}`")
        start = time.perf_counter()
        self._exec(
            f"INSERT INTO `{db}`.`{tmp}` SELECT * FROM `{db}`.`{t}` LIMIT {int(n_rows)}"
        )
        elapsed = (time.perf_counter() - start) * 1000
        self._exec(f"DROP TABLE `{db}`.`{tmp}`")
        return round(elapsed, 2)

    def index_size(self, index_name: str, table: str = None, on_clone: bool = True) -> int:
        db = self.clone_db if on_clone and self.clone_db else self.database
        sql = (
            "SELECT SUM(stat_value) * @@innodb_page_size AS bytes "
            "FROM mysql.innodb_index_stats "
            "WHERE database_name = %s AND index_name = %s AND stat_name = 'size'"
        )
        params = [db, _check_ident(index_name)]
        if table:
            sql += " AND table_name = %s"
            params.append(_check_ident(table))
        row = self._rows(sql, tuple(params))[0]
        return int(row["bytes"] or 0)

    def drop_clone(self) -> None:
        if self.clone_db:
            self._exec(f"DROP DATABASE IF EXISTS `{self.clone_db}`")
            self.clone_db = None
