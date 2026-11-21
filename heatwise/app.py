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
    type: str = Field(pattern=r"^(away|comfort|trim)$")
    value: bool | float


class TopUp(BaseModel):
    pounds: float = Field(gt=0, le=MAX_TOPUP_GBP)


def default_home() -> LiveHome:
    """The demo household. ``HEATWISE_BUDGET`` (£/week, default 30) sets the loaded budget."""
    try:
        budget = float(os.environ.get("HEATWISE_BUDGET", "30"))
    except ValueError:
        budget = 30.0
    budget = min(max(budget, 1.0), MAX_TOPUP_GBP)
    mode = os.environ.get("HEATWISE_MODE", "realtime")
    if mode == "realtime":
        try:
            return LiveHome(budget_gbp=budget, realtime=True)
        except Exception:  # noqa: BLE001 - anything wrong with live mode: use the simulated week
            pass
    return LiveHome(budget_gbp=budget)


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
               "trim": lambda h: h.set_trim(action["value"])}[action["type"]]
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

    @app.post("/api/reset")
    def reset():
        with lock:
            holder["home"] = home_factory()
        return act(lambda h: None)

    return app


app = create_app()
