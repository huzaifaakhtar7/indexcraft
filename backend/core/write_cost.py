INSERT_ROWS = 10_000


def measure_write_cost(adapter, table: str, n_rows: int = INSERT_ROWS) -> float:
    return adapter.measure_insert(table, n_rows, on_clone=True)
