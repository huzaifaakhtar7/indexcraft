import sqlite3
from contextlib import contextmanager

import mysql.connector
import psycopg2
from fastapi import HTTPException

_MYSQL = {
    1045: (401, "Wrong user name or password"),
    1049: (404, "This database does not exist"),
    1146: (404, None),
    1054: (400, None),
    1064: (400, None),
    1061: (409, "An index with this name already exists"),
    3024: (408, "The query took longer than 60 seconds and was stopped"),
    1317: (408, "The query took longer than 60 seconds and was stopped"),
    1969: (408, "The query took longer than 60 seconds and was stopped"),
    2003: (503, "Cannot reach the MySQL server. Check the host and port"),
    2005: (503, "Unknown MySQL host"),
}

_PG = {
    "28P01": (401, "Wrong user name or password"),
    "28000": (401, "This user is not allowed to connect"),
    "3D000": (404, "This database does not exist"),
    "42P01": (404, None),
    "42703": (400, None),
    "42601": (400, None),
    "42883": (400, None),
    "42P07": (409, "An index with this name already exists"),
    "57014": (408, "The query took longer than 60 seconds and was stopped"),
}


def _first_line(e) -> str:
    return str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__


def describe(e: Exception) -> tuple:
    if isinstance(e, mysql.connector.Error):
        status, message = _MYSQL.get(e.errno, (400, None))
        return status, message or e.msg
    if isinstance(e, psycopg2.Error):
        status, message = _PG.get(e.pgcode or "", (None, None))
        if status:
            return status, message or (e.diag.message_primary or _first_line(e))
        text = str(e)
        if "password authentication failed" in text:
            return 401, "Wrong user name or password"
        if "does not exist" in text and "database" in text:
            return 404, "This database does not exist"
        if isinstance(e, psycopg2.OperationalError):
            return 503, "Cannot reach the PostgreSQL server. Check the host and port"
        return 400, (e.diag.message_primary if e.diag else None) or _first_line(e)
    if isinstance(e, sqlite3.Error):
        text = str(e)
        if "no such table" in text:
            return 404, text
        if "already exists" in text:
            return 409, text
        if "file is not a database" in text:
            return 400, "This file is not a SQLite database"
        return 400, text
    if isinstance(e, TimeoutError):
        return 408, str(e) or "The query took too long and was stopped"
    if isinstance(e, FileNotFoundError):
        return 404, str(e)
    if isinstance(e, LookupError) and not isinstance(e, KeyError):
        return 404, str(e)
    if isinstance(e, NotImplementedError):
        return 501, str(e)
    if isinstance(e, ValueError):
        return 400, str(e)
    return 500, f"Unexpected error ({type(e).__name__})"


@contextmanager
def friendly_errors():
    try:
        yield
    except HTTPException:
        raise
    except Exception as e:
        status, message = describe(e)
        raise HTTPException(status_code=status, detail=message) from e
