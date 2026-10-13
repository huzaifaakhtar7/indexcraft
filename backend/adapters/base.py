from abc import ABC, abstractmethod


class BaseAdapter(ABC):
    name: str

    @abstractmethod
    def connect(self, config: dict) -> None: ...

    @abstractmethod
    def explain(self, query: str) -> dict: ...

    @abstractmethod
    def run_timed(self, query: str, runs: int = 5) -> dict: ...

    @abstractmethod
    def list_indexes(self, table: str) -> list: ...

    @abstractmethod
    def column_stats(self, table: str, column: str) -> dict: ...

    @abstractmethod
    def make_clone(self, tables: list) -> str: ...

    @abstractmethod
    def create_index(self, ddl: str, on_clone: bool = True) -> None: ...

    @abstractmethod
    def measure_insert(self, table: str, n_rows: int) -> float: ...

    @abstractmethod
    def index_size(self, index_name: str) -> int: ...

    @abstractmethod
    def drop_clone(self) -> None: ...
