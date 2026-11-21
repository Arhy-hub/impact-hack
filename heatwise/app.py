"""The Heatwise household app: JSON API plus the phone-shaped web page.

Run::

    uvicorn heatwise.app:app --host 127.0.0.1 --port 8000

then open http://127.0.0.1:8000 (or the same address on a phone on the
same network, if you deliberately bind to 0.0.0.0).

One demo household lives in memory. Every endpoint returns the full home
state, so the page just re-renders whatever comes back.

Endpoints:

* ``GET  /api/home``: everything the home screen shows
* ``POST /api/tick {"steps": n}``: move the demo clock forward n × 15 min
* ``POST /api/comfort {"temp": 20}``: daytime comfort temperature
* ``POST /api/calendar {"url": "https://..."}``: connect a secret iCal link ("" for the demo week)
* ``POST /api/away {"on": true}``
* ``POST /api/trim {"degrees": 1}``
* ``POST /api/topup {"pounds": 10}``
* ``POST /api/reset``: start the demo week again
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .live import COMFORT_RANGE, MAX_TOPUP_GBP, LiveHome

try:  # optional: read .env so keys and the calendar URL can live there
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

APP_DIR = Path(__file__).resolve().parent.parent / "app"
PAGE = APP_DIR / "index.html"


class Tick(BaseModel):
    steps: int = Field(1, ge=1, le=96)


class Comfort(BaseModel):
    temp: float = Field(ge=COMFORT_RANGE[0], le=COMFORT_RANGE[1])


class CalendarLink(BaseModel):
    url: str = Field("", max_length=2048)


class Away(BaseModel):
    on: bool


class Trim(BaseModel):
    degrees: float = Field(ge=0, le=3)


class Ask(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class Confirm(BaseModel):
    type: str = Field(pattern=r"^(away|comfort|trim|room)$")
    value: bool | float
    room: str | None = Field(default=None, pattern=r"^(bedroom|kitchen|living)$")


class TopUp(BaseModel):
    pounds: float = Field(gt=0, le=MAX_TOPUP_GBP)


def default_home() -> LiveHome:
    """The demo household. ``HEATWISE_BUDGET`` (£/week, default 45) sets the loaded budget."""
    try:
        budget = float(os.environ.get("HEATWISE_BUDGET", "45"))
    except ValueError:
        budget = 45.0
    budget = min(max(budget, 1.0), MAX_TOPUP_GBP)
    mode = os.environ.get("HEATWISE_MODE", "simulated")  # the example week is the demo default
    if mode == "realtime":
        try:
            return LiveHome(budget_gbp=budget, realtime=True)
        except Exception:  # noqa: BLE001 - anything wrong with live mode: use the simulated week
            pass
    return LiveHome(budget_gbp=budget)


class NewEvent(BaseModel):
    title: str = Field(min_length=1, max_length=60)
    kind: str | None = Field(None, pattern=r"^(away|wfh|guests)$")
    day: int = Field(ge=0, le=6)
    start_h: float = Field(ge=0, lt=24)
    end_h: float = Field(gt=0, le=48)


class Limits(BaseModel):
    weekly_gbp: float | None = Field(None, ge=5, le=200)
    daily_gbp: float | None = Field(None, ge=0.5, le=20)
    daily_off: bool = False


class Repair(BaseModel):
    issue: int = Field(ge=1, le=1000)
    action: str = Field(pattern=r"^(book|dismiss)$")


class BreakRoom(BaseModel):
    room: str = Field(pattern=r"^(bedroom|kitchen|living)$")


class Allowance(BaseModel):
    gbp: float = Field(ge=0, le=500)


class RoomComfort(BaseModel):
    room: str = Field(pattern=r"^[a-z_]{1,32}$")
    temp: float | None = Field(None, ge=16, le=23)


class Jump(BaseModel):
    day: int = Field(ge=0, le=6)
    hour: int = Field(ge=0, le=23)


class Mode(BaseModel):
    mode: str = Field(pattern=r"^(realtime|simulated)$")


def create_app(home_factory=default_home) -> FastAPI:
    app = FastAPI(title="Heatwise", docs_url=None, redoc_url=None, openapi_url=None)
    lock = threading.Lock()
    holder = {"home": home_factory()}

    def act(fn):
        with lock:
            try:
                holder["home"].sync()
                extra = fn(holder["home"])
            except ValueError as err:
                raise HTTPException(422, str(err)) from None
            state = holder["home"].state()
        if isinstance(extra, dict):
            state["result"] = extra
        return state

    app.mount("/assets", StaticFiles(directory=APP_DIR), name="assets")

    @app.middleware("http")
    async def revalidate_assets(request, call_next):
        # Browsers revalidate the page and its modules each load, so edits show up straight away.
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/assets"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/", include_in_schema=False)
    def page():
        return FileResponse(PAGE, media_type="text/html")

    @app.get("/api/home")
    def home():
        return act(lambda h: None)

    @app.post("/api/tick")
    def tick(body: Tick):
        return act(lambda h: h.tick(body.steps))

    @app.post("/api/comfort")
    def comfort(body: Comfort):
        return act(lambda h: h.set_comfort(body.temp))

    @app.post("/api/calendar")
    def calendar(body: CalendarLink):
        def connect(h):
            try:
                h.set_calendar(body.url)
            except RuntimeError as err:  # network/parse failure: generic message, no URL
                raise ValueError(str(err)) from None
        return act(connect)

    @app.post("/api/away")
    def away(body: Away):
        return act(lambda h: h.set_away(body.on))

    @app.post("/api/trim")
    def trim(body: Trim):
        return act(lambda h: h.set_trim(body.degrees))

    @app.post("/api/topup")
    def topup(body: TopUp):
        return act(lambda h: h.topup(body.pounds))

    @app.post("/api/ask")
    def ask(body: Ask):
        from .assistant import ask as assistant_ask

        with lock:
            state = holder["home"].state()
        return assistant_ask(body.text, state)

    @app.post("/api/confirm")
    def confirm(body: Confirm):
        from .assistant import validate

        action = validate(body.model_dump())
        if not action:
            raise HTTPException(422, "That change isn't allowed.")
        run = {"away": lambda h: h.set_away(action["value"]), "comfort": lambda h: h.set_comfort(action["value"]),
               "trim": lambda h: h.set_trim(action["value"]),
               "room": lambda h: h.set_room_comfort(action.get("room", ""), action["value"])}[action["type"]]
        return act(run)

    @app.post("/api/mode")
    def mode(body: Mode):
        with lock:
            home = holder["home"]
            try:
                holder["home"] = LiveHome(budget_gbp=home.budget_gbp, realtime=body.mode == "realtime")
            except Exception:  # noqa: BLE001 - fall back to the simulated week
                holder["home"] = LiveHome(budget_gbp=home.budget_gbp)
        return act(lambda h: None)

    @app.post("/api/events")
    def add_event(body: NewEvent):
        return act(lambda h: h.add_event(body.title, body.kind, body.day, body.start_h, body.end_h))

    @app.delete("/api/events/{index}")
    def remove_event(index: int):
        return act(lambda h: h.remove_event(index))

    @app.post("/api/limits")
    def limits(body: Limits):
        return act(lambda h: h.set_limits(body.weekly_gbp, body.daily_gbp, body.daily_off))

    @app.post("/api/room_comfort")
    def room_comfort(body: RoomComfort):
        return act(lambda h: h.set_room_comfort(body.room, body.temp))

    @app.post("/api/repair")
    def repair(body: Repair):
        """The user approves (book) or declines (dismiss) Luke's repair offer (D27)."""
        return act(lambda h: h.book_repair(body.issue) if body.action == "book" else h.dismiss_issue(body.issue))

    @app.post("/api/break")
    def break_room(body: BreakRoom):
        """Demo: make one room's radiator faulty so Luke can spot it."""
        return act(lambda h: h.break_room(body.room))

    @app.post("/api/repairs_allowance")
    def repairs_allowance(body: Allowance):
        return act(lambda h: h.maint.set_allowance(body.gbp))

    @app.post("/api/allow")
    def allow():
        return act(lambda h: h.allow_more(2.0))

    @app.post("/api/jump")
    def jump(body: Jump):
        """Restart the example week (keeping calendar, limits and comfort) and fast-forward to day/hour."""
        with lock:
            old = holder["home"]
            if old.realtime:
                raise HTTPException(422, "Jumping only works in the example week.")
            new = LiveHome(budget_gbp=old.budget_gbp, settings=old.settings)
            new.events = list(old.events)
            new._refresh_people()
            new.daily_cap_gbp, new.away_manual, new.manual_trim = old.daily_cap_gbp, old.away_manual, old.manual_trim
            new.room_comfort = dict(old.room_comfort)
            new.maint.allowance_gbp = old.maint.allowance_gbp
            target = body.day * 96 + body.hour * 4
            if target > new.t:
                new.tick(target - new.t)
            holder["home"] = new
        return act(lambda h: None)

    @app.post("/api/reset")
    def reset():
        with lock:
            holder["home"] = home_factory()
        return act(lambda h: None)

    return app


app = create_app()
