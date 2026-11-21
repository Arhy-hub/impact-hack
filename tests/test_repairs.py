"""Luke as a maintenance helper: spotting a faulty radiator and getting it fixed (DECISIONS D27)."""
import pytest

from heatwise.live import LiveHome
from heatwise.repairs import Maintenance, visit_slot


def _home_with_fault():
    home = LiveHome(budget_gbp=45)
    home.tick(8)  # Mon 18:00: people are coming home, rooms heat hard
    home.break_room("living")
    for _ in range(40):
        home.tick(1)
        if home.maint.issues:
            break
    return home


def test_a_broken_radiator_is_spotted():
    home = _home_with_fault()
    [issue] = home.maint.issues
    assert home.names[issue.room] == "living" and issue.status == "found"
    assert issue.actual_c < 0.5 * issue.expected_c
    assert any(l["kind"] == "repair" and "living room" in l["text"] for l in home.log)


def test_healthy_house_raises_no_issues():
    home = LiveHome(budget_gbp=45)
    home.tick(96)
    assert home.maint.issues == []


def test_booking_pays_from_allowance_and_the_engineer_fixes_it():
    home = _home_with_fault()
    home.book_repair(1)
    issue = home.maint.issues[0]
    assert issue.status == "booked" and home.maint.spent_gbp == 85
    home.tick(issue.visit_step - home.t + 1)
    assert issue.status == "fixed" and home.maint.efficiency[issue.room] == 1.0
    assert home.state()["report"]["fixed"] == 1


def test_repair_needs_enough_allowance_and_can_be_dismissed():
    m = Maintenance(3, allowance_gbp=50)
    m.issues.append(__import__("heatwise.repairs", fromlist=["Issue"]).Issue(1, 0, 0, 2.0, 0.4))
    with pytest.raises(ValueError):
        m.book(1, 0)
    assert m.dismiss(1).status == "dismissed"


def test_visits_are_in_working_hours():
    for step in range(0, 96 * 2, 3):
        v = visit_slot(step)
        assert v >= step + 8 and 9 <= (v % 96) // 4 < 17


def test_repair_api():
    from fastapi.testclient import TestClient
    from heatwise.app import create_app

    client = TestClient(create_app(lambda: LiveHome(budget_gbp=45)))
    assert client.post("/api/break", json={"room": "attic"}).status_code == 422
    assert client.post("/api/break", json={"room": "living"}).status_code == 200
    assert client.post("/api/repair", json={"issue": 99, "action": "book"}).status_code == 422
    assert client.post("/api/repairs_allowance", json={"gbp": 150}).json()["rules"]["repairs_gbp"] == 150
