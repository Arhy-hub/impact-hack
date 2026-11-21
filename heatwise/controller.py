"""Decide each room's target temperature for the next step.

Rules (from ``heatwise-idea.md``, made price- and carbon-aware):

1. Motion in this room in the last 15 minutes, or the occupancy model says it
   will be used within the hour with probability >= ``use_threshold``:
   heat to ``comfort``.
2. Otherwise, if anyone is home: hold ``eco``. If nobody is home: ``away``
   (frost protection).
3. Slot score = price + green_weight * carbon. In the cheapest/cleanest quarter
   of the day, rooms likely to be used later get ``+preheat`` (store heat).
   In the worst quarter, occupied rooms coast ``-coast`` degrees.
4. Subtract the budget trim (0 to ``max_trim`` degrees) when the month is
   projected to go over budget.
5. Never go below ``away``. This is the safety floor and nothing overrides it.

``timer_targets`` is the old-style baseline: the whole house on a fixed
schedule, whoever is home.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .sim import STEPS_PER_DAY


@dataclass(frozen=True)
class Settings:
    comfort: float = 20.0
    sleep: float = 17.0  # bedroom comfort overnight
    sleep_hours: tuple[float, float] = (23.0, 7.0)
    sleep_room: int = 0  # index of the bedroom in the house's rooms
    night_setback: float = 16.0  # timer baseline overnight
    eco: float = 17.0
    away: float = 12.0  # safety floor, never trimmed below
    use_threshold: float = 0.4
    preheat_threshold: float = 0.2
    preheat: float = 1.0
    coast: float = 1.0
    good_quantile: float = 0.25
    bad_quantile: float = 0.75
    green_weight_p_per_kg: float = 10.0  # pence we'd pay to avoid 1 kg CO2
    max_trim: float = 3.0


def comfort_targets(step: int, n_rooms: int, settings: Settings = Settings()) -> np.ndarray:
    """Comfort temperature per room at ``step``: 20° by day, the bedroom at 17° overnight."""
    hour = (step % STEPS_PER_DAY) * 24 / STEPS_PER_DAY
    start, end = settings.sleep_hours
    comfort = np.full(n_rooms, settings.comfort)
    if hour >= start or hour < end:
        comfort[settings.sleep_room] = settings.sleep
    return comfort


def slot_scores(price_p: np.ndarray, carbon_g: np.ndarray, settings: Settings) -> np.ndarray:
    """Lower is better: pence per kWh plus the carbon cost per kWh at our green weight."""
    return price_p + settings.green_weight_p_per_kg * carbon_g / 1000.0


def heatwise_targets(
    motion_recent: np.ndarray,
    p_soon: np.ndarray,
    people_home: int,
    score: float,
    day_scores: np.ndarray,
    trim: float = 0.0,
    settings: Settings = Settings(),
    comfort: np.ndarray | None = None,
) -> np.ndarray:
    """Target temperature per room. All inputs are things a real house can sense or forecast.

    ``comfort`` is the per-room comfort temperature (see ``comfort_targets``);
    it defaults to ``settings.comfort`` everywhere.
    """
    return decide(motion_recent, p_soon, people_home, score, day_scores, trim, settings, comfort)[0]


# Reason codes returned by ``decide``. One primary reason per room, plus modifiers.
IN_USE, EXPECTED, ECO, AWAY = "in_use", "expected", "eco", "away"
PREHEAT, COAST, TRIM = "preheat", "coast", "trim"


def decide(
    motion_recent: np.ndarray,
    p_soon: np.ndarray,
    people_home: int,
    score: float,
    day_scores: np.ndarray,
    trim: float = 0.0,
    settings: Settings = Settings(),
    comfort: np.ndarray | None = None,
) -> tuple[np.ndarray, list[dict]]:
    """Targets plus the reason for each room, so the app can explain itself.

    Each reason is ``{"why": IN_USE|EXPECTED|ECO|AWAY, "mods": [PREHEAT|COAST|TRIM...],
    "p_soon": float}``.
    """
    s = settings
    n = len(p_soon)
    comfort = np.full(n, s.comfort) if comfort is None else comfort
    in_use = motion_recent | (p_soon >= s.use_threshold)
    base = s.eco if people_home > 0 else s.away
    targets = np.where(in_use, comfort, np.minimum(base, comfort)).astype(float)
    reasons = [
        {"why": IN_USE if motion_recent[i] else EXPECTED if in_use[i] else ECO if people_home > 0 else AWAY,
         "mods": [], "p_soon": round(float(p_soon[i]), 2)}
        for i in range(n)
    ]

    good = score <= np.quantile(day_scores, s.good_quantile)
    bad = score >= np.quantile(day_scores, s.bad_quantile)
    if good:
        boost = p_soon >= s.preheat_threshold
        targets = np.where(boost, np.maximum(targets, s.eco) + s.preheat, targets)
        for i in np.flatnonzero(boost):
            reasons[i]["mods"].append(PREHEAT)
    elif bad:
        targets = np.where(in_use, targets - s.coast, targets)
        for i in np.flatnonzero(in_use):
            reasons[i]["mods"].append(COAST)

    t = min(max(trim, 0.0), s.max_trim)
    if t > 0:
        targets = targets - t
        for r in reasons:
            r["mods"].append(TRIM)
    return np.maximum(targets, s.away), reasons


def timer_targets(step: int, weekday: int, n_rooms: int, settings: Settings = Settings()) -> np.ndarray:
    """Old-style timer: every room to comfort in fixed windows, a night setback
    overnight, and off (frost protection) during the weekday working day."""
    hour = (step % STEPS_PER_DAY) * 24 / STEPS_PER_DAY
    if weekday >= 5:
        on = 7.5 <= hour < 23.0
    else:
        on = 6.0 <= hour < 9.0 or 16.5 <= hour < 23.0
    night = hour >= 23.0 or hour < (7.5 if weekday >= 5 else 6.0)
    if on:
        return np.full(n_rooms, settings.comfort)
    return np.full(n_rooms, settings.night_setback if night else settings.away)


def budget_trim(spent_p: float, budget_p: float, day_index: int, period_days: int,
                recent_daily_p: float, settings: Settings = Settings()) -> tuple[float, float]:
    """Projected period spend and the comfort trim needed to stay within budget.

    Projection = spent so far + recent daily spend x days left (as in the idea doc).
    Trim rises by 1° for every 10% the projection is over budget, capped at ``max_trim``.
    """
    days_left = max(period_days - day_index, 0)
    projected = spent_p + recent_daily_p * days_left
    if budget_p <= 0 or projected <= budget_p:
        return projected, 0.0
    over = (projected - budget_p) / budget_p
    return projected, float(min(np.ceil(over * 10), settings.max_trim))
