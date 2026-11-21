"""Household calendar: read events and turn them into heating hints.

Source: the user's Google Calendar **secret address in iCal format**
(Google Calendar → Settings → your calendar → "Secret address in iCal
format"). Put it in ``.env`` as ``HEATWISE_ICAL_URL``. That URL gives read
access to the calendar, so treat it like a password: it is never logged,
never returned by the API and never committed.

Without a URL, ``demo_calendar`` generates a calendar for the simulated
household's week.

Classification is keyword-based for now (``classify``). The LLM will replace
it later for messy titles. Kinds:

* ``away``: nobody home (trip, holiday, flight). Rooms drop to the safety
  floor, then pre-heat before the event ends.
* ``wfh``: someone working from home. Living room to comfort during the event.
* ``guests``: visitors. Living room and kitchen to comfort during the event.
* ``None``: shown on the plan but no effect on heating (gym, dentist).

Limitations (see docs/DECISIONS.md, K3 and K4): recurring events (RRULE) are
not expanded, and times are converted to UTC, which is London time in winter
and one hour off in British Summer Time.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone

import httpx

STEP_MIN = 15
KEYWORDS = {
    "away": ("away", "holiday", "vacation", "trip", "flight", "✈", "travel", "abroad", "conference"),
    "wfh": ("wfh", "work from home", "working from home", "home office"),
    "guests": ("guests", "friends over", "party", "visitors", "family over", "dinner at ours"),
}


@dataclass
class Event:
    title: str
    start: datetime  # naive, UTC
    end: datetime
    kind: str | None = None

    def to_json(self) -> dict:
        d = asdict(self)
        d["start"], d["end"] = self.start.isoformat(), self.end.isoformat()
        return d


def classify(title: str) -> str | None:
    t = title.lower()
    for kind, words in KEYWORDS.items():
        if any(w in t for w in words):
            return kind
    return None


def _naive_utc(v) -> datetime:
    if isinstance(v, datetime):
        return v.astimezone(timezone.utc).replace(tzinfo=None) if v.tzinfo else v
    return datetime.combine(v, time())  # all-day events: a date


def parse_ics(text: str | bytes) -> list[Event]:
    """Events from iCal text, classified. Malformed events are skipped."""
    from icalendar import Calendar

    events = []
    for comp in Calendar.from_ical(text).walk("VEVENT"):
        try:
            start = _naive_utc(comp.decoded("DTSTART"))
            end = _naive_utc(comp.decoded("DTEND")) if comp.get("DTEND") else start + timedelta(hours=1)
            title = str(comp.get("SUMMARY", "")).strip()[:120]
        except Exception:  # noqa: BLE001 - skip anything we can't read
            continue
        if end > start:
            events.append(Event(title, start, end, classify(title)))
    return sorted(events, key=lambda e: e.start)


def fetch_ics(url: str, timeout: float = 8.0) -> list[Event]:
    """Download and parse a secret iCal URL. Raises a generic error that never contains the URL."""
    if not url.startswith("https://"):
        raise ValueError("calendar URL must be https")
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True, headers={"User-Agent": "heatwise-hackathon"})
        r.raise_for_status()
        if len(r.content) > 5_000_000:
            raise ValueError("calendar too large")
        return parse_ics(r.content)
    except Exception as err:  # noqa: BLE001
        raise RuntimeError(f"couldn't load calendar ({type(err).__name__})") from None


def demo_calendar(week_start: date) -> str:
    """An iCal calendar for the simulated household's week (Monday ``week_start``)."""
    def at(day: int, hh: int, mm: int = 0) -> str:
        dt = datetime.combine(week_start + timedelta(days=day), time(hh, mm))
        return dt.strftime("%Y%m%dT%H%M%SZ")

    events = [
        ("Gym", at(0, 18, 30), at(0, 20)),
        ("WFH", at(1, 9), at(1, 17)),
        ("Trip to Manchester ✈️", at(3, 7), at(4, 19)),
        ("Friends over for dinner", at(5, 18), at(5, 23, 30)),
    ]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Heatwise//demo//EN"]
    for i, (title, s, e) in enumerate(events):
        lines += ["BEGIN:VEVENT", f"UID:demo-{i}@heatwise", f"DTSTAMP:{s}", f"DTSTART:{s}", f"DTEND:{e}",
                  f"SUMMARY:{title}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def step_of(dt: datetime, week_start: date) -> int:
    """Simulation step (15 min) of ``dt``, counted from Monday 00:00 of ``week_start``."""
    return int((dt - datetime.combine(week_start, time())).total_seconds() // (STEP_MIN * 60))


def active(events: list[Event], step: int, week_start: date) -> list[Event]:
    return [e for e in events if step_of(e.start, week_start) <= step < step_of(e.end, week_start)]


def hints(events: list[Event], step: int, week_start: date, preheat_steps: int = 8) -> dict:
    """Heating hints at ``step``: away (and whether it's time to pre-heat for the return), wfh, guests."""
    now = active(events, step, week_start)
    away = [e for e in now if e.kind == "away"]
    returning = any(step_of(e.end, week_start) - step <= preheat_steps for e in away)
    return {
        "away": bool(away) and not returning,
        "returning": bool(away) and returning,
        "wfh": any(e.kind == "wfh" for e in now),
        "guests": any(e.kind == "guests" for e in now),
        "events": [e.title for e in now],
    }
