from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from adapters.factory import get_adapter
from api.errors import friendly_errors
from api.schemas import (AnalyzeRequest, AnalyzeResponse, ApplyRequest, ApplyResponse,
                         ConnectRequest, ConnectResponse, HealthResponse, OkResponse,
                         RunTestRequest, RunTestResponse, SessionRequest)
from api.sessions import close_session, create_session, get_session
from core.analyzer import analyze, rank_results, test_suggestion
from core.query_guard import check_select
from core.reporter import build_report
from history.store import HistoryStore, meta_config

router = APIRouter()


def get_history():
    try:
        store = HistoryStore(meta_config())
    except Exception as e:
        raise HTTPException(503, "The history database (indexcraft_meta) is not reachable. "
                                 "Check META_DB_* or DB_* settings of the backend.") from e
    try:
        yield store
    finally:
        store.close()


def _session(session_id: str):
    session = get_session(session_id)
    if session is None:
        raise HTTPException(404, "Session not found. Connect to the database again.")
    return session


def _save_report(history, session, run_id: int) -> Optional[int]:
    analysis = session.analyses[run_id]
    results = rank_results(list(session.results[run_id].values()))
    if results:
        history.update_baseline(run_id, results[0]["before_ms"])
    history.save_report(run_id, build_report(analysis, results, session.db_type, session.db_name))
    report = history.get_report_by_run(run_id)
    return report["report_id"] if report else None


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok", message="IndexCraft backend is running")


@router.post("/connect", response_model=ConnectResponse)
def connect(req: ConnectRequest):
    config = {
        "host": req.host,
        "port": req.port,
        "user": req.user,
        "password": req.password.get_secret_value(),
        "database": req.database,
        "schema": req.schema_name,
    }
    with friendly_errors():
        adapter = get_adapter(req.db_type)
        adapter.connect(config)
        try:
            tables = adapter.list_tables()
        except Exception:
            adapter.close()
            raise
    session_id = create_session(adapter, req.db_type, adapter.database)
    return ConnectResponse(
        session_id=session_id, db_type=req.db_type, database=adapter.database,
        tables=[{"name": t["name"], "rows": int(t["approx_rows"] or 0)} for t in tables],
    )


@router.post("/disconnect", response_model=OkResponse)
def disconnect(req: SessionRequest):
    with friendly_errors():
        closed = close_session(req.session_id)
    if not closed:
        raise HTTPException(404, "Session not found")
    return OkResponse(ok=True, message="Disconnected. The test copy was deleted.")


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_query(req: AnalyzeRequest, history=Depends(get_history)):
    session = _session(req.session_id)
    with friendly_errors():
        query = check_select(req.query)
        with session.lock:
            analysis = analyze(session.adapter, query)
        run_id = history.save_run(session.db_type, session.db_name, analysis["query"])
        problem_ids = history.save_problems(run_id, analysis["problems"])
        history.save_suggestions(run_id, analysis["suggestions"], problem_ids)
        session.add_analysis(run_id, analysis)
        report_id = _save_report(history, session, run_id)
    return AnalyzeResponse(
        run_id=run_id, report_id=report_id, db_type=session.db_type, database=session.db_name,
        query=analysis["query"], rows_examined=analysis["rows_examined"], plan=analysis["plan"],
        problems=analysis["problems"], suggestions=analysis["suggestions"], notes=analysis["notes"],
    )


@router.post("/test", response_model=RunTestResponse)
def test_on_copy(req: RunTestRequest, history=Depends(get_history)):
    session = _session(req.session_id)
    run_id, analysis, suggestion = session.find_suggestion(req.suggestion_id)
    if suggestion is None:
        raise HTTPException(404, "Suggestion not found in this session. Analyze the query first.")
    with friendly_errors():
        with session.lock:
            result = test_suggestion(session.adapter, analysis, suggestion,
                                     read_share=req.read_share, runs=req.runs)
        history.save_test_result(req.suggestion_id, result)
        session.results[run_id][req.suggestion_id] = result
        report_id = _save_report(history, session, run_id)
    return RunTestResponse(run_id=run_id, suggestion_id=req.suggestion_id, report_id=report_id,
                           ddl=suggestion["ddl"], **result)


@router.post("/apply", response_model=ApplyResponse)
def apply(req: ApplyRequest):
    session = _session(req.session_id)
    _, _, suggestion = session.find_suggestion(req.suggestion_id)
    if suggestion is None:
        raise HTTPException(404, "Suggestion not found in this session. Analyze the query first.")
    if not req.confirm:
        raise HTTPException(400, "Apply changes the real database. Send confirm=true to continue.")
    with friendly_errors():
        with session.lock:
            session.adapter.create_index(suggestion["ddl"], on_clone=False)
            session.adapter.drop_clone()
            session.forget_baselines()
    message = f"Index {suggestion['index_name']} was created on the real database."
    if suggestion.get("rewritten_query"):
        message += " Also change the query in your application to the rewritten version."
    return ApplyResponse(applied=True, sql=suggestion["ddl"],
                         rewritten_query=suggestion.get("rewritten_query"), message=message)


@router.get("/report/{report_id}")
def report(report_id: int, format: Literal["json", "text"] = "json", history=Depends(get_history)):
    with friendly_errors():
        row = history.get_report(report_id)
    if row is None:
        raise HTTPException(404, "Report not found")
    if format == "text":
        return PlainTextResponse(row["report_text"], headers={
            "Content-Disposition": f'inline; filename="indexcraft_report_{report_id}.txt"'})
    return {"report_id": row["report_id"], "run_id": row["run_id"],
            "created_at": row["created_at"], "report_text": row["report_text"]}


@router.get("/history")
def history_list(db_type: Optional[Literal["mysql", "postgres", "sqlite"]] = None,
                 limit: int = Query(50, ge=1, le=500), history=Depends(get_history)):
    with friendly_errors():
        return history.list_runs(db_type=db_type, limit=limit)


@router.get("/history/stats")
def history_stats(history=Depends(get_history)):
    with friendly_errors():
        return {"speedup_by_rule": history.speedup_by_rule(), "recent_tests": history.recent_tests()}


@router.get("/history/{run_id}")
def history_run(run_id: int, history=Depends(get_history)):
    with friendly_errors():
        run = history.get_run(run_id)
    if run is None:
        raise HTTPException(404, "Run not found")
    return run


@router.delete("/history/{run_id}", response_model=OkResponse)
def history_delete(run_id: int, history=Depends(get_history)):
    with friendly_errors():
        deleted = history.delete_run(run_id)
    if not deleted:
        raise HTTPException(404, "Run not found")
    return OkResponse(ok=True, message=f"Run {run_id} and its linked rows were deleted")
