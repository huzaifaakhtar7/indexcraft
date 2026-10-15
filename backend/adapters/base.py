import re
from abc import ABC, abstractmethod

_IDENT = re.compile(r"^[A-Za-z0-9_]+$")
_TABLE_IN_DDL = re.compile(r"\bon\s+[`\"]?([A-Za-z0-9_]+)[`\"]?", re.IGNORECASE)
TIMEOUT_MS = 60_000


def check_ident(name: str) -> str:
    if not _IDENT.match(name or ""):
        raise ValueError(f"Invalid name: {name}")
    return name


def check_create_index(ddl: str) -> str:
    text = ddl.strip().rstrip(";").strip()
    if not re.match(r"^create\s+(unique\s+)?index\s", text, re.IGNORECASE) or ";" in text:
        raise ValueError("Only a single CREATE INDEX statement is allowed")
    return text


def table_from_ddl(ddl: str):
    m = _TABLE_IN_DDL.search(ddl)
    return m.group(1) if m else None


class BaseAdapter(ABC):
    name: str
    label: str

    @abstractmethod
    def connect(self, config: dict) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def explain(self, query: str, on_clone: bool = False) -> dict: ...

    @abstractmethod
    def run_timed(self, query: str, runs: int = 5, on_clone: bool = False) -> dict: ...

    @abstractmethod
    def list_tables(self) -> list: ...

    @abstractmethod
    def list_columns(self, table: str) -> list: ...

    @abstractmethod
    def list_indexes(self, table: str, on_clone: bool = False) -> list: ...

    @abstractmethod
    def column_stats(self, table: str, column: str) -> dict: ...

    @abstractmethod
    def make_clone(self, tables: list) -> str: ...

    @abstractmethod
    def create_index(self, ddl: str, on_clone: bool = True) -> None: ...

    @abstractmethod
    def drop_index(self, table: str, index_name: str, on_clone: bool = True) -> None: ...

    @abstractmethod
    def measure_insert(self, table: str, n_rows: int = 10_000, on_clone: bool = True) -> float: ...

    @abstractmethod
    def index_size(self, index_name: str, table: str = None, on_clone: bool = True) -> int: ...

    @abstractmethod
    def drop_clone(self) -> None: ...

    def drop_index_sql(self, table: str, index_name: str) -> str:
        return f"DROP INDEX {index_name}"
