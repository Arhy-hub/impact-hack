import numpy as np

from heatwise.controller import Settings, budget_trim, heatwise_targets, slot_scores, timer_targets

S = Settings()
DAY = np.linspace(10, 40, 96)  # scores for a day; low = good


def targets(motion=(False, False, False), p=(0.0, 0.0, 0.0), home=1, score=25.0, trim=0.0):
    return heatwise_targets(np.array(motion), np.array(p), home, score, DAY, trim, S)


def test_motion_heats_to_comfort():
    assert targets(motion=(True, False, False))[0] == S.comfort


def test_likely_use_heats_to_comfort():
    t = targets(p=(0.5, 0.39, 0.0))
    assert t[0] == S.comfort and t[1] == S.eco


def test_eco_when_home_away_when_empty():
    assert targets(home=1)[2] == S.eco
    assert targets(home=0)[2] == S.away


def test_preheat_in_good_slots_only_for_likely_rooms():
    t = targets(p=(0.3, 0.0, 0.0), score=10.0)
    assert t[0] == S.eco + S.preheat
    assert t[1] == S.eco


def test_coast_in_bad_slots():
    assert targets(motion=(True, False, False), score=40.0)[0] == S.comfort - S.coast


def test_trim_never_breaks_safety_floor():
    t = targets(home=0, trim=10.0)
    assert (t >= S.away).all()
    assert targets(motion=(True, False, False), trim=2.0)[0] == S.comfort - 2.0


def test_slot_scores_include_carbon():
    s = slot_scores(np.array([20.0]), np.array([200.0]), Settings(green_weight_p_per_kg=10))
    assert s[0] == 22.0


def test_timer_schedule():
    assert timer_targets(28, weekday=0, n_rooms=3)[0] == S.comfort  # 07:00
    assert timer_targets(48, weekday=0, n_rooms=3)[0] == S.away  # 12:00
    assert timer_targets(48, weekday=6, n_rooms=3)[0] == S.comfort  # Sunday noon


def test_budget_trim():
    assert budget_trim(5000, 10000, 15, 30, 300)[1] == 0.0  # projected 9500
    proj, trim = budget_trim(5000, 10000, 15, 30, 400)  # projected 11000, 10% over
    assert proj == 11000 and trim == 1.0
    assert budget_trim(9000, 10000, 1, 30, 1000)[1] == S.max_trim


def test_decide_gives_reasons_matching_targets():
    from heatwise.controller import AWAY, COAST, ECO, EXPECTED, IN_USE, PREHEAT, TRIM, decide

    t, r = decide(np.array([True, False, False]), np.array([0.1, 0.6, 0.0]), 1, 25.0, DAY, 0.0, S)
    assert [x["why"] for x in r] == [IN_USE, EXPECTED, ECO]
    t, r = decide(np.array([False] * 3), np.zeros(3), 0, 25.0, DAY, 0.0, S)
    assert all(x["why"] == AWAY for x in r)
    _, r = decide(np.array([False] * 3), np.array([0.3, 0, 0]), 1, 10.0, DAY, 0.0, S)
    assert PREHEAT in r[0]["mods"] and not r[1]["mods"]
    _, r = decide(np.array([True, False, False]), np.zeros(3), 1, 40.0, DAY, 1.0, S)
    assert r[0]["mods"] == [COAST, TRIM]
