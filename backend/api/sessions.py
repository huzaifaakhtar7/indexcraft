import uuid

_sessions: dict = {}


def create_session(adapter) -> str:
    session_id = uuid.uuid4().hex
    _sessions[session_id] = adapter
    return session_id


def get_session(session_id: str):
    return _sessions.get(session_id)


def close_session(session_id: str) -> None:
    _sessions.pop(session_id, None)
