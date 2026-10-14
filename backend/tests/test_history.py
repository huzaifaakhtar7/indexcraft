from core.scoring import score


def test_big_gain_is_recommended():
    assert score(1400, 2.5, 688, 1064)["verdict"] == "Recommended"


def test_no_gain_is_not_worth_it():
    assert score(430, 480, 25, 45)["verdict"] == "Not worth it"


def test_small_gain_is_optional():
    assert score(100, 90, 25, 26)["verdict"] == "Optional"


def test_write_heavy_workload_changes_verdict():
    assert score(10, 2, 100, 50000, read_share=0.0)["verdict"] == "Not worth it"
