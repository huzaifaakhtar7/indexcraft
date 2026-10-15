import threading
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Session:
    adapter: object
    db_type: str
    db_name: str
    lock: threading.Lock = field(default_factory=threading.Lock)
    analyses: dict = field(default_factory=dict)
    suggestions: dict = field(default_factory=dict)
    results: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def add_analysis(self, run_id: int, analysis: dict) -> None:
        self.analyses[run_id] = analysis
        self.results[run_id] = {}
        for s in analysis["suggestions"]:
            self.suggestions[s["suggestion_id"]] = run_id

    def find_suggestion(self, suggestion_id: int):
        run_id = self.suggestions.get(suggestion_id)
        if run_id is None:
            return None, None, None
        analysis = self.analyses[run_id]
        suggestion = next(s for s in analysis["suggestions"] if s["suggestion_id"] == suggestion_id)
        return run_id, analysis, suggestion

    def forget_baselines(self) -> None:
        for analysis in self.analyses.values():
            analysis.pop("_baseline", None)

    def close(self) -> None:
        with self.lock:
            try:
                self.adapter.drop_clone()
            finally:
                self.adapter.close()


_sessions: dict = {}
_guard = threading.Lock()


def create_session(adapter, db_type: str, db_name: str) -> str:
    session_id = uuid.uuid4().hex
    with _guard:
        _sessions[session_id] = Session(adapter, db_type, db_name)
    return session_id


def get_session(session_id: str):
    return _sessions.get(session_id)


def close_session(session_id: str) -> bool:
    with _guard:
        session = _sessions.pop(session_id, None)
    if session is None:
        return False
    session.close()
    return True


def close_all() -> None:
    for session_id in list(_sessions):
        try:
            close_session(session_id)
        except Exception:
            pass
