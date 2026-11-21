"""Is Heatwise only cheaper because the timer leaves people cold? (DECISIONS D29)

The usual timer is off on weekday daytimes, so anyone home early or working
from home is cold (about 70% comfort). This compares Heatwise with timers
that keep people warmer, in the toy 3-room house and in a 5-room house with
a spare room and a study that nobody uses that week.

    python -m heatwise.compare_timers
"""

from __future__ import annotations

import numpy as np

from .compare import run_week
from .controller import Settings, timer_targets
from .occupancy import OccupancyModel
from .signals import get_signals
from .sim import DEFAULT_ROOMS, STEPS_PER_DAY, Room, simulate_occupancy

FIVE_ROOMS = DEFAULT_ROOMS + (
    Room("spare", tau_h=22.0, c_kwh_per_k=1.0, q_max_kw=2.5),
    Room("study", tau_h=22.0, c_kwh_per_k=1.0, q_max_kw=2.5),
)


def schedule(on):
    """Whole house to comfort while ``on(hour)``, 16° overnight, 12° otherwise."""
    def targets(step, weekday, n, settings=Settings()):
        h = (step % STEPS_PER_DAY) * 24 / STEPS_PER_DAY
        if on(h):
            return np.full(n, settings.comfort)
        return np.full(n, settings.night_setback if (h >= 23 or h < 6) else settings.away)
    return targets


TIMERS = {
    "Usual timer (weekdays 6-9am, 4:30-11pm)": timer_targets,
    "Timer 6am-11pm every day": schedule(lambda h: 6 <= h < 23),
    "Heating on 24/7": schedule(lambda h: True),
}


def compare(rooms=DEFAULT_ROOMS, signals=None, seed: int = 0) -> dict:
    signals = signals or get_signals(allow_live=False)
    names = tuple(r.name for r in rooms)
    train = simulate_occupancy(35, rooms=names, seed=seed)
    week = simulate_occupancy(7, rooms=names, seed=seed + 1000, start_day=0)
    hw = run_week("heatwise", week, signals, predictor=OccupancyModel().fit(train), rooms=rooms).summary()
    rows = {}
    for name, timer in TIMERS.items():
        s = run_week("timer", week, signals, timer=timer, rooms=rooms).summary()
        rows[name] = {**s, "heatwise_cost_saving_pct": round(100 * (1 - hw["cost_gbp"] / s["cost_gbp"]), 1),
                      "heatwise_carbon_saving_pct": round(100 * (1 - hw["carbon_kg"] / s["carbon_kg"]), 1)}
    return {"heatwise": hw, "timers": rows}


def main() -> None:
    signals = get_signals(allow_live=False)
    for label, rooms in (("Toy house, 3 rooms", DEFAULT_ROOMS), ("5 rooms (spare room and study unused)", FIVE_ROOMS)):
        res = compare(rooms, signals)
        hw = res["heatwise"]
        print(f"\n{label}\n  Heatwise{'':33s} £{hw['cost_gbp']:6.2f}  {hw['carbon_kg']:5.1f} kg  comfort {hw['comfort_pct']:5.1f}%")
        for name, s in res["timers"].items():
            print(f"  {name:41s} £{s['cost_gbp']:6.2f}  {s['carbon_kg']:5.1f} kg  comfort {s['comfort_pct']:5.1f}%"
                  f"  -> Heatwise {s['heatwise_cost_saving_pct']}% cheaper, {s['heatwise_carbon_saving_pct']}% less CO2")


if __name__ == "__main__":
    main()
