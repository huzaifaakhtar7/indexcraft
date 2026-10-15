import itertools

import pytest
from fastapi.testclient import TestClient

from api.routes import get_history
from main import app
from tests.test_sqlite_adapter import build_shop


class FakeHistory:
    def __init__(self):
        self.ids = itertools.count(1)
        self.runs, self.problems, self.suggestions, self.results, self.reports = {}, {}, {}, {}, {}

    def save_run(self, db_type, db_name, query_text, baseline_ms=None):
        run_id = next(self.ids)
        self.runs[run_id] = {"run_id": run_id, "db_type": db_type, "db_name": db_name,
                             "query_text": query_text, "baseline_ms": baseline_ms}
        return run_id

    def update_baseline(self, run_id, baseline_ms):
        self.runs[run_id]["baseline_ms"] = baseline_ms

    def save_problems(self, run_id, problems):
        ids = {}
        for p in problems:
            p["problem_id"] = next(self.ids)
            self.problems[p["problem_id"]] = run_id
            ids.setdefault(p["rule_code"], p["problem_id"])
        return ids

    def save_suggestions(self, run_id, suggestions, problem_ids):
        for s in suggestions:
            s["suggestion_id"] = next(self.ids)
            self.suggestions[s["suggestion_id"]] = run_id
        return suggestions

    def save_test_result(self, suggestion_id, r):
        self.results[suggestion_id] = r["verdict"]

    def save_report(self, run_id, text):
        existing = next((r for r in self.reports.values() if r["run_id"] == run_id), None)
        if existing:
            existing["report_text"] = text
            return existing["report_id"]
        report_id = next(self.ids)
        self.reports[report_id] = {"report_id": report_id, "run_id": run_id,
                                   "report_text": text, "created_at": None}
        return report_id

    def get_report(self, report_id):
        return self.reports.get(report_id)

    def get_report_by_run(self, run_id):
        return next((r for r in self.reports.values() if r["run_id"] == run_id), None)

    def list_runs(self, db_type=None, limit=50):
        return [r for r in self.runs.values() if not db_type or r["db_type"] == db_type][:limit]

    def get_run(self, run_id):
        return self.runs.get(run_id)

    def delete_run(self, run_id):
        return self.runs.pop(run_id, None) is not None

    def close(self):
        pass


@pytest.fixture
def client(tmp_path):
    path = tmp_path / "shop_api.db"
    build_shop(path)
    store = FakeHistory()
    app.dependency_overrides[get_history] = lambda: store
    with TestClient(app) as c:
        c.db_path = str(path)
        c.store = store
        yield c
    app.dependency_overrides.clear()


def connect(client):
    res = client.post("/api/connect", json={"db_type": "sqlite", "database": client.db_path})
    assert res.status_code == 200, res.text
    return res.json()


def test_full_flow(client):
    conn = connect(client)
    assert {t["name"] for t in conn["tables"]} == {"customers", "orders"}
    sid = conn["session_id"]

    res = client.post("/api/analyze", json={"session_id": sid,
                                            "query": "SELECT * FROM orders WHERE customer_id = 500;"})
    assert res.status_code == 200, res.text
    analysis = res.json()
    assert analysis["problems"][0]["rule_code"] == "R1"
    assert analysis["plan"][0]["full_scan"]
    suggestion = analysis["suggestions"][0]

    res = client.post("/api/test", json={"session_id": sid, "suggestion_id": suggestion["suggestion_id"],
                                         "runs": 2})
    assert res.status_code == 200, res.text
    result = res.json()
    assert result["rows_after"] < result["rows_before"]
    assert result["verdict"] in ("Recommended", "Optional", "Not worth it")
    assert client.store.results[suggestion["suggestion_id"]] == result["verdict"]

    text = client.get(f"/api/report/{result['report_id']}?format=text")
    assert text.status_code == 200 and "MEASURED RESULTS" in text.text

    res = client.post("/api/apply", json={"session_id": sid, "suggestion_id": suggestion["suggestion_id"]})
    assert res.status_code == 400
    res = client.post("/api/apply", json={"session_id": sid, "suggestion_id": suggestion["suggestion_id"],
                                          "confirm": True})
    assert res.status_code == 200 and res.json()["sql"] == suggestion["ddl"]
    res = client.post("/api/apply", json={"session_id": sid, "suggestion_id": suggestion["suggestion_id"],
                                          "confirm": True})
    assert res.status_code == 409

    runs = client.get("/api/history?db_type=sqlite").json()
    assert runs[0]["run_id"] == analysis["run_id"]
    assert client.delete(f"/api/history/{analysis['run_id']}").status_code == 200
    assert client.get(f"/api/history/{analysis['run_id']}").status_code == 404

    assert client.post("/api/disconnect", json={"session_id": sid}).status_code == 200
    assert client.post("/api/analyze", json={"session_id": sid, "query": "SELECT 1"}).status_code == 404


@pytest.mark.parametrize("query", ["DELETE FROM orders", "SELECT 1; DROP TABLE orders",
                                   "UPDATE orders SET status = 'x'"])
def test_only_select_is_accepted(client, query):
    sid = connect(client)["session_id"]
    res = client.post("/api/analyze", json={"session_id": sid, "query": query})
    assert res.status_code == 400


def test_friendly_errors(client):
    res = client.post("/api/connect", json={"db_type": "sqlite", "database": "missing_file.db"})
    assert res.status_code == 404 and "not found" in res.json()["detail"]
    sid = connect(client)["session_id"]
    res = client.post("/api/analyze", json={"session_id": sid, "query": "SELECT * FROM nope WHERE a = 1"})
    assert res.status_code == 404 and "no such table" in res.json()["detail"]
    res = client.post("/api/connect", json={"db_type": "oracle", "database": "x", "password": "secret1"})
    assert res.status_code == 422 and "secret1" not in res.text
