"""A running household for the app: the engine plus a clock, overrides and a wallet.

``LiveHome`` ties the existing pieces together. Every ``tick`` (one 15-minute
step):

1. ``decide`` the targets: controller (ML occupancy, price and carbon, budget
   trim), then overrides in priority order: calendar, then the away toggle,
   then the away toggle. Running out of credit beats everything except the safety floor.
2. ``House.step`` the physics, then ``Wallet.pay`` for the electricity.

The household is simulated (people, sensors, house). Prices, carbon and
weather are real (or the snapshot), and the calendar is the user's secret
iCal link or a demo week. Calendar events are also applied to the simulated
people so the demo stays consistent: on an "away" event nobody is home.

Everything the app shows comes from ``state()``. All wording is template
sentences built from the controller's reason codes. The LLM will replace
these later without changing the API.
"""

from __future__ import annotations

import os
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import numpy as np

from . import calendar as cal
from .compare import run_week
from .controller import (
    AWAY, COAST, ECO, EXPECTED, IN_USE, PREHEAT, TRIM,
    Settings, comfort_targets, decide, slot_scores,
)
from .occupancy import OccupancyModel
from .signals import get_signals
from .sim import DAY_NAMES, DEFAULT_ROOMS, STEPS_PER_DAY, House, simulate_occupancy
from .supplier import LocalSupplier, make_supplier
from .wallet import Wallet

CUSTOMER = "demo-house"
WEEK_STEPS = 7 * STEPS_PER_DAY
COMFORT_RANGE = (16.0, 23.0)
MAX_TOPUP_GBP = 200.0
DISPLAY = {"living": "living room"}  # how rooms are named in sentences

# Extra reason codes for overrides, on top of the controller's own.
CAL_AWAY, CAL_RETURN, CAL_WFH, CAL_GUESTS = "cal_away", "cal_return", "cal_wfh", "cal_guests"
MANUAL_AWAY, NO_CREDIT = "manual_away", "no_credit"


def this_monday(today: date | None = None) -> date:
    today = today or datetime.now(timezone.utc).date()
    return today - timedelta(days=today.weekday())


def clock(step: int) -> str:
    m = (step % STEPS_PER_DAY) * 15
    return f"{DAY_NAMES[(step // STEPS_PER_DAY) % 7]} {m // 60:02d}:{m % 60:02d}"


def apply_calendar_to_people(occ, events, week_start: date) -> None:
    """Make the simulated household follow the calendar (demo consistency)."""
    living = occ.rooms.index("living")
    for t in range(occ.n_steps):
        h = cal.hints(events, t, week_start, preheat_steps=0)
        if h["away"]:
            occ.occupied[t] = False
            occ.motion[t] = False
            occ.people_home[t] = 0
        elif h["wfh"] or h["guests"]:
            occ.occupied[t, living] = True
            occ.motion[t, living] = True
            occ.people_home[t] = max(occ.people_home[t], 1)


class LiveHome:
    def __init__(
        self,
        seed: int = 0,
        budget_gbp: float = 40.0,
        week_start: date | None = None,
        start_step: int = 16 * 4,  # Monday 16:00
        allow_live_signals: bool = True,
        ical_url: str | None = None,
        supplier=None,
        settings: Settings = Settings(),
    ):
        self.settings = settings
        self.seed = seed
        self.rooms = DEFAULT_ROOMS
        self.names = [r.name for r in self.rooms]
        self.week_start = week_start or this_monday()

        self.signals = get_signals(allow_live=allow_live_signals)
        self.price, self.carbon, self.temp_out = self.signals.per_step(STEPS_PER_DAY)
        self.day_scores = slot_scores(self.price, self.carbon, settings)

        ical_url = ical_url if ical_url is not None else os.environ.get("HEATWISE_ICAL_URL", "")
        self.calendar_error = None
        if ical_url:
            try:
                self.events = cal.fetch_ics(ical_url)
                self.calendar_source = "google"
            except Exception as err:  # noqa: BLE001 - fall back to the demo week
                self.calendar_error = str(err)
                self.events = cal.parse_ics(cal.demo_calendar(self.week_start))
                self.calendar_source = "demo"
        else:
            self.events = cal.parse_ics(cal.demo_calendar(self.week_start))
            self.calendar_source = "demo"

        self.occ = simulate_occupancy(7, seed=seed + 1000)
        apply_calendar_to_people(self.occ, self.events, self.week_start)
        train = simulate_occupancy(35, seed=seed)
        self.model = OccupancyModel().fit(train)
        # Prior for the budget projection: what a typical week costs with Heatwise (DECISIONS L3).
        typical = run_week("heatwise", simulate_occupancy(7, seed=seed + 2000), self.signals,
                           predictor=self.model, settings=settings)
        self.prior_daily_p = typical.cost_gbp * 100 / 7

        self.house = House(self.rooms)
        self.supplier = supplier or make_supplier()
        self.budget_gbp = float(budget_gbp)
        if isinstance(self.supplier, LocalSupplier):
            self.supplier.checkout(CUSTOMER, self.budget_gbp)  # the human loads the budget
        self.wallet = Wallet(self.supplier, CUSTOMER)

        self.t = start_step
        self.start_step = start_step
        self.away_manual = False
        self.manual_trim = 0.0
        self.auto_trim = 0.0
        self.cost_log: list[float] = []  # pence per step since start
        self.last_kwh = np.zeros(len(self.rooms))
        self.targets, self.reasons = self._decide(self.t)

    # ---------- decisions ----------

    def _daily_estimate_p(self) -> float:
        """Expected spend per day: the prior, shifting to observed spend over the first 24 h."""
        recent = self.cost_log[-STEPS_PER_DAY:]
        if not recent:
            return self.prior_daily_p
        observed = sum(recent) / len(recent) * STEPS_PER_DAY
        w = len(recent) / STEPS_PER_DAY
        return w * observed + (1 - w) * self.prior_daily_p

    def _projected_p(self) -> float:
        spent = self.wallet.spent_pence + self.wallet.emergency_pence
        days_left = max(7 - self.t / STEPS_PER_DAY, 0)
        return spent + self._daily_estimate_p() * days_left

    def _trim(self) -> float:
        projected = self._projected_p()
        budget_p = self.budget_gbp * 100
        if projected <= budget_p:
            self.auto_trim = 0.0
        else:  # same rule as controller.budget_trim: 1° per 10% over, capped
            self.auto_trim = float(min(np.ceil((projected - budget_p) / budget_p * 10), self.settings.max_trim))
        return min(self.auto_trim + self.manual_trim, self.settings.max_trim)

    def _decide(self, t: int, p_soon: np.ndarray | None = None, motion: np.ndarray | None = None,
                people_home: int | None = None, trim: float | None = None):
        s = self.settings
        n = len(self.rooms)
        s_day = t % STEPS_PER_DAY
        if motion is None:
            motion = self.occ.motion[t] | (self.occ.motion[t - 1] if t > 0 else False)
        if p_soon is None:
            p_soon = self.model.predict_proba(self.occ, t)
        if people_home is None:
            people_home = int(self.occ.people_home[t])
        trim = self._trim() if trim is None else trim
        comfort = comfort_targets(t, n, s)
        targets, reasons = decide(motion, p_soon, people_home, self.day_scores[s_day], self.day_scores,
                                  trim, s, comfort)

        h = cal.hints(self.events, t, self.week_start)
        title = ", ".join(h["events"])
        if h["away"]:
            targets[:] = s.away
            for r in reasons:
                r.update(why=CAL_AWAY, mods=[], event=title)
        if h["returning"]:
            for i in range(n):
                if p_soon[i] >= s.preheat_threshold or self.names[i] == "living":
                    targets[i] = comfort[i]
                    reasons[i].update(why=CAL_RETURN, mods=[], event=title)
        for kind, rooms, code in (("wfh", ("living",), CAL_WFH), ("guests", ("living", "kitchen"), CAL_GUESTS)):
            if h[kind]:
                for name in rooms:
                    i = self.names.index(name)
                    targets[i] = max(targets[i], comfort[i])
                    reasons[i].update(why=code, mods=[], event=title)
        if self.away_manual:
            targets[:] = s.away
            for r in reasons:
                r.update(why=MANUAL_AWAY, mods=[])
        if self.wallet.needs_topup:
            targets[:] = s.away
            for r in reasons:
                r.update(why=NO_CREDIT, mods=[])
        return np.maximum(targets, s.away), reasons

    # ---------- actions ----------

    @property
    def finished(self) -> bool:
        return self.t >= WEEK_STEPS - 1

    def tick(self, steps: int = 1) -> None:
        for _ in range(max(0, min(steps, WEEK_STEPS))):
            if self.finished:
                return
            t, s_day = self.t, self.t % STEPS_PER_DAY
            self.targets, self.reasons = self._decide(t)
            q = self.house.heat_needed_kw(self.targets, self.temp_out[s_day])
            self.last_kwh = self.house.step(q, self.temp_out[s_day])
            kwh = float(self.last_kwh.sum())
            self.wallet.pay(t, kwh, float(self.price[s_day]), float(self.carbon[s_day]))
            self.cost_log.append(kwh * float(self.price[s_day]))
            self.t += 1
        self.targets, self.reasons = self._decide(self.t)

    def room_index(self, name: str) -> int:
        if name not in self.names:
            raise ValueError(f"unknown room {name!r}")
        return self.names.index(name)

    def set_comfort(self, temp: float) -> None:
        """Daytime comfort temperature for every room (the bedroom keeps its night setting)."""
        lo, hi = COMFORT_RANGE
        if not lo <= temp <= hi:
            raise ValueError(f"comfort must be {lo:.0f} to {hi:.0f}°C")
        self.settings = replace(self.settings, comfort=float(temp))
        self.targets, self.reasons = self._decide(self.t)

    def set_calendar(self, url: str) -> None:
        """Connect a secret iCal URL, or pass "" to go back to the demo week.

        On failure the current calendar is kept and a generic error is raised
        (the URL never appears in it).
        """
        url = url.strip()
        if url:
            events = cal.fetch_ics(url)  # raises without the URL in the message
            source = "google"
        else:
            events, source = cal.parse_ics(cal.demo_calendar(self.week_start)), "demo"
        self.events, self.calendar_source, self.calendar_error = events, source, None
        # Re-run the simulated household against the new calendar (demo consistency).
        self.occ = simulate_occupancy(7, seed=self.seed + 1000)
        apply_calendar_to_people(self.occ, self.events, self.week_start)
        self.targets, self.reasons = self._decide(self.t)

    def set_away(self, on: bool) -> None:
        self.away_manual = bool(on)
        self.targets, self.reasons = self._decide(self.t)

    def set_trim(self, degrees: float) -> None:
        if not 0 <= degrees <= self.settings.max_trim:
            raise ValueError(f"trim must be 0 to {self.settings.max_trim}")
        self.manual_trim = float(degrees)
        self.targets, self.reasons = self._decide(self.t)

    def topup(self, pounds: float) -> dict:
        """Local supplier: credit added now. SolvaPay: returns the checkout URL to pay in the browser."""
        if not 0 < pounds <= MAX_TOPUP_GBP:
            raise ValueError(f"top-up must be £0 to £{MAX_TOPUP_GBP:.0f}")
        if isinstance(self.supplier, LocalSupplier):
            self.supplier.checkout(CUSTOMER, pounds)
            self.budget_gbp += pounds
            self.wallet.checkout_url = None
            self.targets, self.reasons = self._decide(self.t)
            return {"paid": True}
        return {"paid": False, "checkout_url": self.wallet.checkout_url}

    # ---------- what the app shows ----------

    def _status(self, i: int) -> tuple[str, str]:
        """(chip, sentence) for room ``i``."""
        r, name = self.reasons[i], DISPLAY.get(self.names[i], self.names[i])
        why, mods = r["why"], r.get("mods", [])
        chip, text = {
            IN_USE: ("In use", f"Someone's in the {name}, so it's kept comfortable."),
            EXPECTED: ("Warming up", f"The {name} is usually used soon ("
                       + ("very likely" if r["p_soon"] >= 0.95 else f"{r['p_soon']:.0%} chance")
                       + " in the next 3 hours), so it's warming up."),
            ECO: ("Eco", f"Nobody's expected in the {name} for a while, so it's held at eco."),
            AWAY: ("Saving", "Nobody's home, so it's on frost protection."),
            CAL_AWAY: ("Away", f"Your calendar says you're away ({r.get('event', '')}), so the house is on frost protection."),
            CAL_RETURN: ("Welcome home", f"You're due back soon ({r.get('event', '')}), so the {name} is warming up."),
            CAL_WFH: ("WFH", f"Your calendar says you're working from home, so the {name} is kept comfortable."),
            CAL_GUESTS: ("Guests", f"Guests are coming ({r.get('event', '')}), so the {name} is kept comfortable."),
            MANUAL_AWAY: ("Away mode", "Away mode is on, so the house is on frost protection."),
            NO_CREDIT: ("No credit", "Out of credit: safety heating only until you top up."),
        }[why]
        extra = []
        if PREHEAT in mods:
            extra.append("Electricity is cheap and clean right now, so it's storing a little extra heat.")
        if COAST in mods:
            extra.append(f"It's a peak-price hour, so it's running {self.settings.coast:.0f}° cooler.")
        if TRIM in mods:
            extra.append(f"Trimmed {self._trim():.0f}° to keep you on budget.")
        return chip, " ".join([text, *extra])

    def _price_level(self, s_day: int) -> str:
        sc = self.day_scores[s_day]
        if sc <= np.quantile(self.day_scores, self.settings.good_quantile):
            return "cheap"
        if sc >= np.quantile(self.day_scores, self.settings.bad_quantile):
            return "peak"
        return "normal"

    def plan(self, hours: int = 24) -> dict:
        """The next ``hours``: expected heating per room per hour, price level, calendar events.

        Future motion is unknown, so this uses the routine heatmap alone and assumes
        someone is home unless the calendar says otherwise.
        """
        rows = {name: [] for name in self.names}
        temps = {name: [] for name in self.names}
        levels, labels = [], []
        comfort_line = self.settings.comfort - 1
        for h in range(hours):
            steps = [self.t + h * 4 + k for k in range(4)]
            tg = np.zeros(len(self.rooms))
            for t in steps:
                p = self.model.baseline.predict_proba(self.occ, t % WEEK_STEPS)
                tt, _ = self._decide(t, p_soon=p, motion=np.zeros(len(self.rooms), bool), people_home=1,
                                     trim=min(self.auto_trim + self.manual_trim, self.settings.max_trim))
                tg = np.maximum(tg, tt)
            for i, name in enumerate(self.names):
                temps[name].append(round(float(tg[i]), 1))
                rows[name].append("heat" if tg[i] >= comfort_line - 3 and tg[i] > self.settings.eco else
                                  "eco" if tg[i] > self.settings.away else "off")
            levels.append(self._price_level(steps[0] % STEPS_PER_DAY))
            labels.append(clock(steps[0])[-5:])
        start = datetime.combine(self.week_start, datetime.min.time()) + timedelta(minutes=15 * self.t)
        end = start + timedelta(hours=hours)
        events = [
            {"title": e.title, "kind": e.kind,
             "from_h": max((e.start - start).total_seconds() / 3600, 0),
             "to_h": min((e.end - start).total_seconds() / 3600, hours)}
            for e in self.events if e.end > start and e.start < end
        ]
        return {"hours": labels, "rooms": rows, "targets": temps, "price": levels, "events": events}

    def tips(self) -> list[str]:
        s_day = self.t % STEPS_PER_DAY
        tips = []
        level = self._price_level(s_day)
        if level == "cheap":
            tips.append("Electricity is cheap and clean right now. A good time to run the dishwasher or washing machine.")
        elif level == "peak":
            nxt = next((k for k in range(1, 48) if self._price_level((s_day + k) % STEPS_PER_DAY) != "peak"), 0)
            hrs = max(round(nxt / 4), 1)
            tips.append(f"Peak prices for about the next {hrs} hour{'s' if hrs > 1 else ''}. Avoid running big appliances if you can.")
        b = self.budget()
        if b["projected_gbp"] > b["budget_gbp"]:
            tips.append(f"You're on track to spend £{b['projected_gbp']:.2f} this week against a £{b['budget_gbp']:.2f} budget. "
                        "Top up, or let Heatwise trim a degree.")
        if (self.targets <= self.settings.away + 1e-6).all() and not self.away_manual and not self.wallet.needs_topup:
            tips.append("Nobody's home, so every room is on frost protection. Nothing to do.")
        upcoming = [e for e in self.events if e.kind == "away" and 0 < cal.step_of(e.start, self.week_start) - self.t <= 96]
        for e in upcoming:
            tips.append(f"\"{e.title}\" is coming up. The house will drop to 12° while you're away and warm up before you're back.")
        return tips[:3]

    def upcoming_events(self) -> list[dict]:
        """Calendar events from now to the end of the week, with what each does to the heating."""
        effect = {"away": "House on away, warm again before you're back",
                  "wfh": "Living room kept warm", "guests": "Living room and kitchen kept warm",
                  None: "No change to heating"}
        out = []
        for e in self.events:
            start, end = cal.step_of(e.start, self.week_start), cal.step_of(e.end, self.week_start)
            if end > self.t and start < WEEK_STEPS:
                out.append({"title": e.title, "kind": e.kind, "effect": effect[e.kind],
                            "start": clock(max(start, 0)), "end": clock(min(end, WEEK_STEPS - 1)),
                            "now": start <= self.t < end})
        return out

    def budget(self) -> dict:
        spent = (self.wallet.spent_pence + self.wallet.emergency_pence) / 100
        projected = self._projected_p() / 100
        credit = (self.supplier.balance_blocks(CUSTOMER) * self.supplier.block_pence + self.wallet.credit_pence) / 100 \
            if isinstance(self.supplier, LocalSupplier) else None
        return {
            "period": "this week",
            "budget_gbp": round(self.budget_gbp, 2),
            "spent_gbp": round(spent, 2),
            "projected_gbp": round(projected, 2),
            "credit_left_gbp": None if credit is None else round(credit, 2),
            "over_budget": projected > self.budget_gbp,
            "needs_topup": self.wallet.needs_topup,
            "auto_trim": self.auto_trim,
            "manual_trim": self.manual_trim,
            "supplier": self.supplier.name,
            "co2_kg": round(sum(r.carbon_g for r in self.wallet.receipts) / 1000, 2),
        }

    def state(self) -> dict:
        """Everything the app shows, as plain JSON-safe Python types."""
        return _plain(self._state())

    def _state(self) -> dict:
        t = min(self.t, WEEK_STEPS - 1)
        s_day = t % STEPS_PER_DAY
        hour = s_day // 4
        greeting = "Good morning" if 5 <= hour < 12 else "Good afternoon" if 12 <= hour < 18 else "Good evening"
        rooms = []
        for i, name in enumerate(self.names):
            chip, why = self._status(i)
            rooms.append({
                "name": name,
                "temp": round(float(self.house.state.temps[i]), 1),
                "target": round(float(self.targets[i]), 1),
                "heating": bool(self.last_kwh[i] > 1e-4),
                "status": chip,
                "why": why,
            })
        return {
            "clock": clock(t),
            "date": (self.week_start + timedelta(days=t // STEPS_PER_DAY)).isoformat(),
            "greeting": greeting,
            "outside_c": round(float(self.temp_out[s_day]), 1),
            "price_p": round(float(self.price[s_day]), 1),
            "carbon_g": round(float(self.carbon[s_day])),
            "price_level": self._price_level(s_day),
            "signals_source": self.signals.source,
            "away": self.away_manual,
            "rooms": rooms,
            "budget": self.budget(),
            "plan": self.plan(),
            "tips": self.tips(),
            "calendar": {"source": self.calendar_source, "error": self.calendar_error,
                         "events_this_week": len(self.events),
                         "upcoming": self.upcoming_events(),
                         "now": cal.hints(self.events, t, self.week_start)["events"]},
            "comfort_c": self.settings.comfort,
            "finished": self.finished,
        }


def _plain(x):
    """Recursively convert numpy scalars and arrays to plain Python for JSON."""
    if isinstance(x, dict):
        return {k: _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if isinstance(x, np.ndarray):
        return x.tolist()
    if isinstance(x, np.generic):
        return x.item()
    return x
