from datetime import date

import httpx
import pytest

from heatwise import calendar as cal

MONDAY = date(2026, 11, 16)


def test_classify_keywords():
    assert cal.classify("Trip to Manchester ✈️") == "away"
    assert cal.classify("WFH") == "wfh"
    assert cal.classify("Friends over for dinner") == "guests"
    assert cal.classify("Dentist") is None


def test_demo_calendar_parses():
    events = cal.parse_ics(cal.demo_calendar(MONDAY))
    assert [e.kind for e in events] == [None, "wfh", "away", "guests"]
    assert events[2].start.weekday() == 3  # Thursday


def test_hints_through_the_week():
    events = cal.parse_ics(cal.demo_calendar(MONDAY))
    tue_noon = 96 + 48
    assert cal.hints(events, tue_noon, MONDAY)["wfh"]
    thu_noon = 3 * 96 + 48
    assert cal.hints(events, thu_noon, MONDAY)["away"]
    fri_1800 = 4 * 96 + 72  # trip ends Fri 19:00: within the 2 h pre-heat window
    h = cal.hints(events, fri_1800, MONDAY)
    assert h["returning"] and not h["away"]
    assert cal.hints(events, 10, MONDAY) == {"away": False, "returning": False, "wfh": False, "guests": False, "events": []}


def test_parse_skips_bad_events_and_handles_all_day():
    ics = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n"
           "BEGIN:VEVENT\r\nUID:1\r\nDTSTART;VALUE=DATE:20261121\r\nDTEND;VALUE=DATE:20261123\r\nSUMMARY:Holiday\r\nEND:VEVENT\r\n"
           "BEGIN:VEVENT\r\nUID:2\r\nSUMMARY:No start\r\nEND:VEVENT\r\n"
           "END:VCALENDAR\r\n")
    events = cal.parse_ics(ics)
    assert len(events) == 1 and events[0].kind == "away"


def test_fetch_rejects_http_and_hides_url(monkeypatch):
    with pytest.raises(ValueError):
        cal.fetch_ics("http://example.com/secret.ics")

    def boom(*a, **k):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(cal.httpx, "get", boom)
    secret = "https://calendar.google.com/calendar/ical/SECRET-TOKEN/basic.ics"
    with pytest.raises(RuntimeError) as err:
        cal.fetch_ics(secret)
    assert "SECRET-TOKEN" not in str(err.value)
