import os

import mysql.connector

META_DB = "indexcraft_meta"


def meta_config() -> dict:
    return {
        "host": os.getenv("META_DB_HOST") or os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("META_DB_PORT") or os.getenv("DB_PORT", 3306)),
        "user": os.getenv("META_DB_USER") or os.getenv("DB_USER", "root"),
        "password": os.getenv("META_DB_PASSWORD") or os.getenv("DB_PASSWORD", ""),
    }


class HistoryStore:
    def __init__(self, config: dict):
        self.conn = mysql.connector.connect(
            host=config.get("host", "localhost"),
            port=int(config.get("port", 3306)),
            user=config.get("user", "root"),
            password=config.get("password", ""),
            database=META_DB,
            autocommit=True,
        )

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def _insert(self, sql: str, params: tuple) -> int:
        cur = self.conn.cursor()
        cur.execute(sql, params)
        new_id = cur.lastrowid
        cur.close()
        return new_id

    def _rows(self, sql: str, params: tuple = ()) -> list:
        cur = self.conn.cursor(dictionary=True)
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows

    def save_run(self, db_type: str, db_name: str, query_text: str, baseline_ms=None) -> int:
        return self._insert(
            "INSERT INTO analysis_runs (db_type, db_name, query_text, baseline_ms) "
            "VALUES (%s, %s, %s, %s)",
            (db_type, db_name, query_text, baseline_ms),
        )

    def update_baseline(self, run_id: int, baseline_ms: float) -> None:
        self._insert("UPDATE analysis_runs SET baseline_ms = %s WHERE run_id = %s",
                     (baseline_ms, run_id))

    def save_problems(self, run_id: int, problems: list) -> dict:
        ids = {}
        for p in problems:
            pid = self._insert(
                "INSERT INTO problems (run_id, rule_code, message, severity) VALUES (%s, %s, %s, %s)",
                (run_id, p["rule_code"], p["message"], p["severity"]),
            )
            p["problem_id"] = pid
            ids.setdefault(p["rule_code"], pid)
        return ids

    def save_suggestions(self, run_id: int, suggestions: list, problem_ids: dict) -> list:
        for s in suggestions:
            reason = s["reason"]
            if s.get("rewritten_query"):
                reason += f" Rewritten query: {s['rewritten_query']}"
            s["suggestion_id"] = self._insert(
                "INSERT INTO suggestions (run_id, problem_id, ddl_text, reason, rank_no) "
                "VALUES (%s, %s, %s, %s, %s)",
                (run_id, problem_ids.get(s.get("rule_code")), s["ddl"], reason, s["rank"]),
            )
        return suggestions

    def save_test_result(self, suggestion_id: int, r: dict) -> int:
        return self._insert(
            "INSERT INTO test_results (suggestion_id, before_ms, after_ms, rows_before, rows_after, "
            "insert_before_ms, insert_after_ms, index_size_kb, net_benefit_ms, verdict) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE before_ms = VALUES(before_ms), after_ms = VALUES(after_ms), "
            "rows_before = VALUES(rows_before), rows_after = VALUES(rows_after), "
            "insert_before_ms = VALUES(insert_before_ms), insert_after_ms = VALUES(insert_after_ms), "
            "index_size_kb = VALUES(index_size_kb), net_benefit_ms = VALUES(net_benefit_ms), "
            "verdict = VALUES(verdict), tested_at = CURRENT_TIMESTAMP",
            (suggestion_id, r["before_ms"], r["after_ms"], r["rows_before"], r["rows_after"],
             r["insert_before_ms"], r["insert_after_ms"], r["index_size_kb"],
             r["net_benefit_ms"], r["verdict"]),
        )

    def save_report(self, run_id: int, text: str) -> int:
        return self._insert(
            "INSERT INTO reports (run_id, report_text) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE report_text = VALUES(report_text), created_at = CURRENT_TIMESTAMP",
            (run_id, text),
        )

    def list_runs(self, db_type: str = None, limit: int = 50) -> list:
        sql = (
            "SELECT r.run_id, r.db_type, r.db_name, r.query_text, r.baseline_ms, r.created_at, "
            "COUNT(DISTINCT p.problem_id) AS problems, "
            "COUNT(DISTINCT s.suggestion_id) AS suggestions, "
            "CASE WHEN SUM(t.verdict = 'Recommended') > 0 THEN 'Recommended' "
            "     WHEN SUM(t.verdict = 'Optional') > 0 THEN 'Optional' "
            "     WHEN COUNT(t.result_id) > 0 THEN 'Not worth it' "
            "     ELSE 'Not tested' END AS best_verdict, "
            "MAX(t.before_ms / NULLIF(t.after_ms, 0)) AS best_speedup "
            "FROM analysis_runs r "
            "LEFT JOIN problems p ON p.run_id = r.run_id "
            "LEFT JOIN suggestions s ON s.run_id = r.run_id "
            "LEFT JOIN test_results t ON t.suggestion_id = s.suggestion_id "
        )
        params = []
        if db_type:
            sql += "WHERE r.db_type = %s "
            params.append(db_type)
        sql += "GROUP BY r.run_id ORDER BY r.created_at DESC, r.run_id DESC LIMIT %s"
        params.append(int(limit))
        return self._rows(sql, tuple(params))

    def get_run(self, run_id: int):
        runs = self._rows("SELECT * FROM analysis_runs WHERE run_id = %s", (run_id,))
        if not runs:
            return None
        run = runs[0]
        run["problems"] = self._rows(
            "SELECT * FROM problems WHERE run_id = %s ORDER BY problem_id", (run_id,))
        run["suggestions"] = self._rows(
            "SELECT s.*, t.result_id, t.before_ms, t.after_ms, t.rows_before, t.rows_after, "
            "t.insert_before_ms, t.insert_after_ms, t.index_size_kb, t.net_benefit_ms, t.verdict, "
            "t.tested_at FROM suggestions s "
            "LEFT JOIN test_results t ON t.suggestion_id = s.suggestion_id "
            "WHERE s.run_id = %s ORDER BY s.rank_no", (run_id,))
        report = self._rows("SELECT * FROM reports WHERE run_id = %s", (run_id,))
        run["report"] = report[0] if report else None
        return run

    def get_report(self, report_id: int):
        rows = self._rows("SELECT * FROM reports WHERE report_id = %s", (report_id,))
        return rows[0] if rows else None

    def get_report_by_run(self, run_id: int):
        rows = self._rows("SELECT * FROM reports WHERE run_id = %s", (run_id,))
        return rows[0] if rows else None

    def delete_run(self, run_id: int) -> bool:
        cur = self.conn.cursor()
        cur.execute("DELETE FROM analysis_runs WHERE run_id = %s", (run_id,))
        deleted = cur.rowcount > 0
        cur.close()
        return deleted

    def speedup_by_rule(self) -> list:
        return self._rows(
            "SELECT p.rule_code, COUNT(*) AS cases, "
            "ROUND(AVG(t.before_ms / NULLIF(t.after_ms, 0)), 1) AS avg_speedup "
            "FROM problems p "
            "JOIN suggestions s ON s.problem_id = p.problem_id "
            "JOIN test_results t ON t.suggestion_id = s.suggestion_id "
            "GROUP BY p.rule_code ORDER BY avg_speedup DESC"
        )

    def recent_tests(self, limit: int = 10) -> list:
        return self._rows(
            "SELECT r.run_id, r.db_type, r.created_at, t.before_ms, t.after_ms, t.verdict "
            "FROM analysis_runs r "
            "JOIN suggestions s ON s.run_id = r.run_id "
            "JOIN test_results t ON t.suggestion_id = s.suggestion_id "
            "ORDER BY r.created_at DESC, t.result_id DESC LIMIT %s", (int(limit),)
        )
