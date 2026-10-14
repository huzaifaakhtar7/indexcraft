def pct_change(before: float, after: float) -> float:
    if not before:
        return 0.0
    return round((before - after) / before * 100, 1)


def score(before_ms: float, after_ms: float, insert_before_ms: float, insert_after_ms: float,
          insert_rows: int = 10_000, read_share: float = 0.9) -> dict:
    read_share = min(max(read_share, 0.0), 1.0)
    write_share = 1 - read_share
    read_saving_ms = before_ms - after_ms
    write_penalty_ms = (insert_after_ms - insert_before_ms) / max(insert_rows, 1)
    net = read_share * read_saving_ms - write_share * write_penalty_ms

    gain = pct_change(before_ms, after_ms)
    if net > 0 and gain >= 30:
        verdict = "Recommended"
    elif net > 0 and gain >= 5:
        verdict = "Optional"
    else:
        verdict = "Not worth it"

    return {
        "read_share": round(read_share, 2),
        "write_share": round(write_share, 2),
        "read_saving_ms": round(read_saving_ms, 2),
        "write_penalty_ms_per_row": round(write_penalty_ms, 4),
        "read_gain_pct": gain,
        "write_loss_pct": round(-pct_change(insert_before_ms, insert_after_ms), 1),
        "speedup": round(before_ms / after_ms, 1) if after_ms else None,
        "net_benefit_ms": round(net, 2),
        "verdict": verdict,
    }
