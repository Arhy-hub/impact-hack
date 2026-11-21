"""End-to-end toy runs, offline (committed snapshot signals, local supplier)."""

import json

import pytest

from heatwise import run_toy


@pytest.fixture(scope="module")
def report(tmp_path_factory, monkeypatch_module):
    out = tmp_path_factory.mktemp("web") / "data.json"
    return run_toy.main(["--offline", "--out", str(out)]), out


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    mp.delenv("SOLVAPAY_SECRET_KEY", raising=False)
    yield mp
    mp.undo()


def test_heatwise_cheaper_and_cleaner_than_timer(report):
    r, _ = report
    assert r["heatwise"]["cost_gbp"] < r["timer"]["cost_gbp"]
    assert r["heatwise"]["carbon_kg"] < r["timer"]["carbon_kg"]


def test_heatwise_at_least_as_comfortable(report):
    r, _ = report
    assert r["heatwise"]["comfort_pct"] >= r["timer"]["comfort_pct"]


def test_paid_run_stays_within_budget(report):
    r, _ = report
    paid = r["heatwise_paid"]
    assert paid["spent_gbp"] <= paid["budget_gbp"] + 0.10  # at most one block over
    assert paid["blocks_bought"] > 0


def test_writes_json_for_web_page(report):
    _, out = report
    data = json.loads(out.read_text(encoding="utf-8"))
    assert set(data) >= {"timer", "heatwise", "heatwise_paid", "series", "ml", "signals", "week"}


def test_week_data_for_floor_plan(report):
    r, _ = report
    w = r["week"]
    n, rooms = len(w["occupied"]), len(r["rooms"])
    assert n == 7 * 96
    for key in ("timer", "heatwise"):
        for field in ("temp", "target", "kwh"):
            assert len(w[key][field]) == n and len(w[key][field][0]) == rooms
    assert min(min(row) for row in w["heatwise"]["target"]) >= 12.0  # safety floor visible in the data


def test_tiny_budget_triggers_topup_request(tmp_path, monkeypatch):
    monkeypatch.delenv("SOLVAPAY_SECRET_KEY", raising=False)
    r = run_toy.main(["--offline", "--budget", "3", "--out", str(tmp_path / "d.json")])
    paid = r["heatwise_paid"]
    assert paid["topup_requests"], "running out of credit must raise a top-up request"
    assert paid["topup_requests"][0]["checkout_url"].startswith("local://checkout")
    assert paid["emergency_gbp"] > 0  # safety heat was kept on
