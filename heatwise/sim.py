"""Simulated house: rooms, people and heat.

Toy version. Everything here is synthetic. It exists so the controller, the
occupancy model and the payment loop can be tested end to end before any real
sensor data exists.

Time runs in 15-minute steps (``STEP_H = 0.25`` hours). One day is 96 steps.

Thermal model (one node per room, an RC model)::

    dT/dt = (T_out - T) / tau  +  Q_heat / C

* ``tau`` (hours) is how fast a room cools towards the outside temperature.
* ``C`` (kWh per °C) is how much heat the room stores.
* ``Q_heat`` (kW of heat) comes from the heater, capped at ``q_max``.

Electricity used is heat divided by the heat pump's COP (coefficient of
performance). See ``docs/DECISIONS.md`` for why these numbers were chosen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

STEP_H = 0.25  # hours per step
STEPS_PER_DAY = 96
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass(frozen=True)
class Room:
    name: str
    tau_h: float  # cooling time constant, hours
    c_kwh_per_k: float  # heat stored per degree
    q_max_kw: float  # heater's maximum heat output

    @property
    def ua_kw_per_k(self) -> float:
        """Heat loss per degree of indoor/outdoor difference."""
        return self.c_kwh_per_k / self.tau_h


# Toy house: 3 rooms. Values are made up but in a plausible range for a UK terrace.
DEFAULT_ROOMS = (
    Room("bedroom", tau_h=22.0, c_kwh_per_k=1.0, q_max_kw=2.5),
    Room("kitchen", tau_h=18.0, c_kwh_per_k=1.0, q_max_kw=2.5),
    Room("living", tau_h=24.0, c_kwh_per_k=1.4, q_max_kw=3.0),
)

# Routines: (start hour, end hour, room). Gaps mean "out of the house".
# Bedroom overnight is split at midnight into two entries.
WEEKDAY_ROUTINES = {
    "alex": [(0, 7, "bedroom"), (7, 7.75, "kitchen"), (18, 19.5, "kitchen"),
             (19.5, 23, "living"), (23, 24, "bedroom")],
    "sam": [(0, 6.5, "bedroom"), (6.5, 7.25, "kitchen"), (17.5, 18.5, "living"),
            (18.5, 19.5, "kitchen"), (19.5, 22.5, "living"), (22.5, 24, "bedroom")],
}
WEEKEND_ROUTINES = {
    "alex": [(0, 9, "bedroom"), (9, 10.5, "kitchen"), (10.5, 13, "living"),
             (18, 19.5, "kitchen"), (19.5, 24, "living")],
    "sam": [(0, 8.5, "bedroom"), (8.5, 9.5, "kitchen"), (9.5, 12, "living"),
            (16, 17, "kitchen"), (17, 23.5, "living"), (23.5, 24, "bedroom")],
}


@dataclass
class Occupancy:
    """Ground truth and sensor view of who is where.

    Arrays are shaped ``(n_steps, n_rooms)`` (``occupied``, ``motion``) or
    ``(n_steps,)`` (``people_home``).
    """

    rooms: tuple[str, ...]
    occupied: np.ndarray  # bool, someone is really in the room
    motion: np.ndarray  # bool, what the motion sensor saw
    people_home: np.ndarray  # int, phones on the home Wi-Fi
    start_day: int = 0  # weekday index of step 0 (0 = Monday)

    @property
    def n_steps(self) -> int:
        return self.occupied.shape[0]

    def weekday(self, step: int) -> int:
        return (self.start_day + step // STEPS_PER_DAY) % 7

    def slot(self, step: int) -> int:
        return step % STEPS_PER_DAY


def _to_step(hour: float) -> int:
    return int(round(hour * STEPS_PER_DAY / 24))


def simulate_occupancy(
    n_days: int,
    rooms: tuple[str, ...] = tuple(r.name for r in DEFAULT_ROOMS),
    seed: int = 0,
    jitter_h: float = 0.5,
    wfh_prob: float = 0.15,
    motion_detect_prob: float = 0.9,
    false_motion_prob: float = 0.01,
    start_day: int = 0,
) -> Occupancy:
    """Generate ``n_days`` of who-is-where with realistic noise.

    Noise sources: each routine block starts and ends up to ``jitter_h`` hours
    early or late; on a weekday a person works from home with probability
    ``wfh_prob`` (living room 9:00 to 17:00); the motion sensor misses some
    presence and occasionally fires on an empty room.
    """
    rng = np.random.default_rng(seed)
    idx = {name: i for i, name in enumerate(rooms)}
    n = n_days * STEPS_PER_DAY
    occupied = np.zeros((n, len(rooms)), dtype=bool)
    people_home = np.zeros(n, dtype=int)

    for d in range(n_days):
        weekday = (start_day + d) % 7
        routines = WEEKEND_ROUTINES if weekday >= 5 else WEEKDAY_ROUTINES
        base = d * STEPS_PER_DAY
        for person, blocks in routines.items():
            where = np.full(STEPS_PER_DAY, -1)
            for start, end, room in blocks:
                # Midnight edges stay fixed so nights join up across days.
                j0 = 0 if start == 0 else rng.uniform(-jitter_h, jitter_h)
                j1 = 0 if end == 24 else rng.uniform(-jitter_h, jitter_h)
                s = max(0, _to_step(start + j0))
                e = min(STEPS_PER_DAY, _to_step(end + j1))
                where[s:e] = idx[room]
            if weekday < 5 and rng.random() < wfh_prob:
                where[_to_step(9):_to_step(17)] = idx["living"]
            for t in range(STEPS_PER_DAY):
                if where[t] >= 0:
                    occupied[base + t, where[t]] = True
                    people_home[base + t] += 1

    detect = rng.random(occupied.shape) < motion_detect_prob
    false_fire = rng.random(occupied.shape) < false_motion_prob
    motion = (occupied & detect) | (~occupied & false_fire)
    return Occupancy(rooms, occupied, motion, people_home, start_day)


@dataclass
class HouseState:
    temps: np.ndarray  # °C per room

    @classmethod
    def initial(cls, rooms=DEFAULT_ROOMS, temp: float = 17.0) -> "HouseState":
        return cls(np.full(len(rooms), temp, dtype=float))


@dataclass
class House:
    rooms: tuple[Room, ...] = DEFAULT_ROOMS
    cop: float = 3.0  # heat pump: kWh of heat per kWh of electricity
    state: HouseState = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.state is None:
            self.state = HouseState.initial(self.rooms)

    def heat_needed_kw(self, target: np.ndarray, t_out: float) -> np.ndarray:
        """Heat (kW) per room to reach ``target`` by the end of this step, capped.

        Solves the RC step for Q so that T_next == target, then clips to
        [0, q_max]. The heater can only add heat, never cool.
        """
        q = np.empty(len(self.rooms))
        for i, room in enumerate(self.rooms):
            needed = (target[i] - self.state.temps[i]) * room.c_kwh_per_k / STEP_H
            needed += room.ua_kw_per_k * (self.state.temps[i] - t_out)
            q[i] = min(max(needed, 0.0), room.q_max_kw)
        return q

    def step(self, q_kw: np.ndarray, t_out: float) -> np.ndarray:
        """Advance one step with heat ``q_kw`` per room. Returns electricity used (kWh)."""
        for i, room in enumerate(self.rooms):
            dT = (t_out - self.state.temps[i]) / room.tau_h + q_kw[i] / room.c_kwh_per_k
            self.state.temps[i] += dT * STEP_H
        return q_kw * STEP_H / self.cop
