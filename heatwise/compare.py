"""Run a simulated week and score it.

``run_week`` drives the house with either the Heatwise controller or the
old-style timer, over the same people, weather and prices, and returns
cost, carbon, energy and comfort, plus per-step logs for charts.

Comfort is measured where it matters: for every step and room that someone is
*really* in (ground truth), is the room within ``comfort_tolerance`` of that
room's comfort temperature (20°, or 17° for the bedroom overnight)?
See docs/DECISIONS.md (R2).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .controller import Settings, budget_trim, comfort_targets, heatwise_targets, slot_scores, timer_targets
from .signals import DaySignals
from .sim import STEPS_PER_DAY, House, Occupancy


@dataclass
class WeekResult:
    strategy: str
    cost_gbp: float
    carbon_kg: float
    kwh: float
    comfort_pct: float
    temps: np.ndarray  # (steps, rooms) at the start of each step
    targets: np.ndarray
    kwh_per_step: np.ndarray
    trims: np.ndarray
    topup_requests: list[dict] = field(default_factory=list)

    def summary(self) -> dict:
        return {
            "strategy": self.strategy,
            "cost_gbp": round(float(self.cost_gbp), 2),
            "carbon_kg": round(float(self.carbon_kg), 2),
            "kwh": round(self.kwh, 1),
            "comfort_pct": round(float(self.comfort_pct), 1),
        }


def run_week(
    strategy: str,
    occ: Occupancy,
    signals: DaySignals,
    predictor=None,
    wallet=None,
    budget_gbp: float | None = None,
    settings: Settings = Settings(),
    start_temp: float = 18.0,
    comfort_tolerance: float = 1.0,
) -> WeekResult:
    """Simulate ``occ.n_steps`` steps with ``strategy`` in {"heatwise", "timer"}.

    The same day of signals repeats every day (toy version; see DECISIONS R1).
    With a ``wallet``, every step's electricity is paid for through it. While a
    top-up is pending, Heatwise holds every room at the safety floor.
    """
    if strategy not in ("heatwise", "timer"):
        raise ValueError(strategy)
    if strategy == "heatwise" and predictor is None:
        raise ValueError("heatwise needs an occupancy predictor")

    price, carbon, temp_out = signals.per_step(STEPS_PER_DAY)
    day_scores = slot_scores(price, carbon, settings)
    house = House()
    house.state.temps[:] = start_temp
    n, r = occ.n_steps, len(occ.rooms)
    temps = np.zeros((n, r))
    targets = np.zeros((n, r))
    kwh_log = np.zeros((n, r))
    trims = np.zeros(n)
    cost_p = carbon_g = 0.0
    budget_p = budget_gbp * 100 if budget_gbp else None
    period_days = n // STEPS_PER_DAY
    requests: list[dict] = []

    for t in range(n):
        s = t % STEPS_PER_DAY
        temps[t] = house.state.temps
        if strategy == "timer":
            tg = timer_targets(t, occ.weekday(t), r, settings)
        elif wallet is not None and wallet.needs_topup:
            tg = np.full(r, settings.away)
        else:
            trim = 0.0
            if budget_p is not None and t >= STEPS_PER_DAY:
                recent_daily = kwh_log[t - STEPS_PER_DAY:t].sum(axis=1) @ price[np.arange(t - STEPS_PER_DAY, t) % STEPS_PER_DAY]
                _, trim = budget_trim(cost_p, budget_p, t // STEPS_PER_DAY, period_days, recent_daily, settings)
            trims[t] = trim
            motion_recent = occ.motion[t] | (occ.motion[t - 1] if t > 0 else False)
            tg = heatwise_targets(
                motion_recent, predictor.predict_proba(occ, t), int(occ.people_home[t]),
                day_scores[s], day_scores, trim, settings, comfort_targets(t, r, settings),
            )
        targets[t] = tg
        q = house.heat_needed_kw(tg, temp_out[s])
        kwh = house.step(q, temp_out[s])
        kwh_log[t] = kwh
        step_kwh = float(kwh.sum())
        cost_p += step_kwh * price[s]
        carbon_g += step_kwh * carbon[s]
        if wallet is not None:
            was_ok = not wallet.needs_topup
            wallet.pay(t, step_kwh, float(price[s]), float(carbon[s]))
            if was_ok and wallet.needs_topup:
                requests.append({"step": t, "checkout_url": wallet.checkout_url})

    occupied = occ.occupied
    need = np.array([comfort_targets(t, r, settings) for t in range(n)])
    comfy = temps >= need - comfort_tolerance
    comfort_pct = 100.0 * (comfy & occupied).sum() / max(occupied.sum(), 1)
    return WeekResult(
        strategy, cost_p / 100, carbon_g / 1000, float(kwh_log.sum()), comfort_pct,
        temps, targets, kwh_log, trims, requests,
    )
