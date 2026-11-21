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
* ``POST /api/boost {"room": "...", "hours": 1}`` and ``POST /api/boost/cancel {"room": "..."}``
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
from pydantic import BaseModel, Field

from .live import MAX_BOOST_H, MAX_TOPUP_GBP, LiveHome

try:  # optional: read .env so keys and the calendar URL can live there
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

PAGE = Path(__file__).resolve().parent.parent / "app" / "index.html"
ROOM_PATTERN = r"^[a-z_]{1,32}$"


class Tick(BaseModel):
    steps: int = Field(1, ge=1, le=96)


class Boost(BaseModel):
    room: str = Field(pattern=ROOM_PATTERN)
    hours: float = Field(1.0, ge=0.25, le=MAX_BOOST_H)


class Room(BaseModel):
    room: str = Field(pattern=ROOM_PATTERN)


class Away(BaseModel):
    on: bool


class Trim(BaseModel):
    degrees: float = Field(ge=0, le=3)


class TopUp(BaseModel):
    pounds: float = Field(gt=0, le=MAX_TOPUP_GBP)


def default_home() -> LiveHome:
    """The demo household. ``HEATWISE_BUDGET`` (£/week, default 30) sets the loaded budget."""
    try:
        budget = float(os.environ.get("HEATWISE_BUDGET", "30"))
    except ValueError:
        budget = 30.0
    return LiveHome(budget_gbp=min(max(budget, 1.0), MAX_TOPUP_GBP))


def create_app(home_factory=default_home) -> FastAPI:
    app = FastAPI(title="Heatwise", docs_url=None, redoc_url=None, openapi_url=None)
    lock = threading.Lock()
    holder = {"home": home_factory()}

    def act(fn):
        with lock:
            try:
                extra = fn(holder["home"])
            except ValueError as err:
                raise HTTPException(422, str(err)) from None
            state = holder["home"].state()
        if isinstance(extra, dict):
            state["result"] = extra
        return state

    @app.get("/", include_in_schema=False)
    def page():
        return FileResponse(PAGE, media_type="text/html")

    @app.get("/api/home")
    def home():
        return act(lambda h: None)

    @app.post("/api/tick")
    def tick(body: Tick):
        return act(lambda h: h.tick(body.steps))

    @app.post("/api/boost")
    def boost(body: Boost):
        return act(lambda h: h.boost(body.room, body.hours))

    @app.post("/api/boost/cancel")
    def cancel(body: Room):
        return act(lambda h: h.cancel_boost(body.room))

    @app.post("/api/away")
    def away(body: Away):
        return act(lambda h: h.set_away(body.on))

    @app.post("/api/trim")
    def trim(body: Trim):
        return act(lambda h: h.set_trim(body.degrees))

    @app.post("/api/topup")
    def topup(body: TopUp):
        return act(lambda h: h.topup(body.pounds))

    @app.post("/api/reset")
    def reset():
        with lock:
            holder["home"] = home_factory()
        return act(lambda h: None)

    return app


app = create_app()
