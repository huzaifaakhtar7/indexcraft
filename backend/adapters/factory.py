from importlib import import_module

from adapters.base import BaseAdapter

_ADAPTERS = {
    "mysql": ("adapters.mysql_adapter", "MySQLAdapter"),
    "postgres": ("adapters.postgres_adapter", "PostgresAdapter"),
    "sqlite": ("adapters.sqlite_adapter", "SQLiteAdapter"),
}


def get_adapter(db_type: str) -> BaseAdapter:
    key = db_type.strip().lower()
    if key not in _ADAPTERS:
        raise ValueError(f"Unsupported database type: {db_type}")
    module_name, class_name = _ADAPTERS[key]
    module = import_module(module_name)
    adapter_class = getattr(module, class_name, None)
    if adapter_class is None:
        raise NotImplementedError(f"{class_name} is not implemented yet")
    return adapter_class()
