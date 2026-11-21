import pytest

from heatwise.live import WEEK_STEPS, LiveHome, clock
from heatwise.supplier import LocalSupplier


@pytest.fixture
def home(monkeypatch):
    monkeypatch.delenv("SOLVAPAY_SECRET_KEY", raising=False)
    monkeypatch.delenv("HEATWISE_ICAL_URL", raising=False)
    return LiveHome(allow_live_signals=False, supplier=LocalSupplier())


def test_clock_labels():
    assert clock(0) == "Mon 00:00" and clock(64) == "Mon 16:00" and clock(96 + 30) == "Tue 07:30"


def test_state_shape(home):
    s = home.state()
    assert s["clock"] == "Mon 16:00"
    assert [r["name"] for r in s["rooms"]] == ["bedroom", "kitchen", "living"]
    assert set(s["budget"]) >= {"budget_gbp", "spent_gbp", "projected_gbp", "needs_topup"}
    assert len(s["plan"]["hours"]) == 24 and len(s["plan"]["rooms"]["living"]) == 24


def test_tick_advances_and_spends(home):
    home.tick(8)
    s = home.state()
    assert s["clock"] == "Mon 18:00"
    assert s["budget"]["spent_gbp"] > 0


def test_comfort_setting(home):
    home.tick(96 + 48 - home.t)  # Tue 12:00: living room in use (WFH)
    home.set_comfort(21)
    assert home.state()["comfort_c"] == 21
    assert home.state()["rooms"][2]["target"] >= 20.0
    for bad in (10, 30):
        with pytest.raises(ValueError):
            home.set_comfort(bad)


def test_calendar_switch_back_to_demo_and_bad_link(home):
    home.set_calendar("")
    assert home.state()["calendar"]["source"] == "demo"
    with pytest.raises(ValueError):
        home.set_calendar("http://insecure.example/cal.ics")
    assert home.state()["calendar"]["source"] == "demo"  # unchanged on failure


def test_plan_has_numeric_targets(home):
    plan = home.state()["plan"]
    assert len(plan["targets"]["living"]) == 24
    assert all(12.0 <= t <= 23.0 for t in plan["targets"]["living"])


def test_away_mode_drops_to_safety_floor_and_back(home):
    home.set_away(True)
    assert all(r["target"] == 12.0 and r["status"] == "Away mode" for r in home.state()["rooms"])
    home.set_away(False)
    assert any(r["target"] > 12.0 for r in home.state()["rooms"])


def test_calendar_wfh_and_away(home):
    home.tick(96 + 48 - home.t)  # Tue 12:00, WFH in the demo calendar
    living = home.state()["rooms"][2]
    assert living["status"] == "WFH" and living["target"] >= 19.0
    home.tick(3 * 96 + 48 - home.t)  # Thu 12:00, away on a trip
    assert all(r["status"] == "Away" and r["target"] == 12.0 for r in home.state()["rooms"])


def test_manual_trim_lowers_targets_not_below_floor(home):
    before = home.state()["rooms"][2]["target"]
    home.set_trim(2)
    after = home.state()["rooms"][2]["target"]
    assert after <= before and after >= 12.0
    with pytest.raises(ValueError):
        home.set_trim(5)


def test_out_of_credit_then_topup(monkeypatch):
    monkeypatch.delenv("HEATWISE_ICAL_URL", raising=False)
    home = LiveHome(allow_live_signals=False, budget_gbp=0.5, supplier=LocalSupplier())
    home.tick(40)
    s = home.state()
    assert s["budget"]["needs_topup"]
    assert all(r["status"] == "No credit" and r["target"] == 12.0 for r in s["rooms"])
    assert home.topup(10)["paid"]
    assert not home.state()["budget"]["needs_topup"]
    with pytest.raises(ValueError):
        home.topup(1000)


def test_week_end_stops(home):
    home.tick(WEEK_STEPS * 2)
    assert home.finished
    home.tick(5)  # no crash after the end


def test_bad_calendar_url_falls_back_to_demo(monkeypatch):
    home = LiveHome(allow_live_signals=False, ical_url="http://not-https.example/cal.ics", supplier=LocalSupplier())
    assert home.calendar_source == "demo" and home.calendar_error
    assert "not-https" not in home.calendar_error


def test_realtime_mode_starts_now_with_generated_calendar(monkeypatch):
    monkeypatch.delenv("HEATWISE_ICAL_URL", raising=False)
    from heatwise.live import now_step
    home = LiveHome(allow_live_signals=False, supplier=LocalSupplier(), realtime=True)
    s = home.state()
    assert s["mode"] == "realtime"
    assert home.t == now_step(home.week_start)
    assert [e["title"] for e in s["calendar"]["upcoming"]][:2] == ["Gym", "WFH"]
    home.sync()  # never goes backwards
    assert home.t >= now_step(home.week_start)
