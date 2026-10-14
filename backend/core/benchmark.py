import statistics
import time


def median_ms(fn, runs: int = 5, warmup: int = 1) -> dict:
    for _ in range(warmup):
        fn()
    timings = []
    result = None
    for _ in range(runs):
        start = time.perf_counter()
        result = fn()
        timings.append((time.perf_counter() - start) * 1000)
    return {
        "median_ms": round(statistics.median(timings), 2),
        "min_ms": round(min(timings), 2),
        "max_ms": round(max(timings), 2),
        "runs": runs,
        "timings_ms": [round(t, 2) for t in timings],
        "result": result,
    }
