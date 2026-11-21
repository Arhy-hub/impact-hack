"""Luke as a maintenance helper: spot heating faults and get them fixed, within a repairs allowance.

How a fault is spotted (DECISIONS D27)
--------------------------------------
The house model knows how much a room *should* warm when its heater runs:
``heat effect = heat delivered (kW) / room heat capacity (kWh/°C) x step length``.
Each step we compare that with what actually happened, after taking off the
room's normal cooling towards the outside temperature. Over the last
``WINDOW`` steps of hard heating (heater at half power or more), if the room
got less than ``ALERT_RATIO`` of the warming it should have, and the model
expected at least ``MIN_EXPECTED_C`` of warming, Luke raises an issue.

In a real home the "actual" side comes from the room's temperature sensor.
In the demo a fault is injected with ``break_room`` (a stuck radiator valve:
the heater only delivers ``FAULT_EFFICIENCY`` of its heat).

Repairs
-------
An issue starts as ``found``. Luke offers a fixed-price engineer visit
(``QUOTE_GBP``, simulated: there is no real engineer or booking). If you
approve, it is paid from the repairs allowance and ``booked``; after
the visit (the first working-hours slot at least ``MIN_NOTICE_STEPS`` away) the engineer has been, the heater works again and the
issue is ``fixed``. You can also ``dismiss`` an issue.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass

import numpy as np

QUOTE_GBP = 85.0  # fixed-price engineer visit (simulated)
MIN_NOTICE_STEPS = 8  # the engineer needs at least 2 hours' notice
WORK_HOURS = (9, 17)  # and only visits 9am to 5pm
FAULT_EFFICIENCY = 0.2  # a stuck valve: the radiator gives a fifth of its heat
WINDOW = 8  # steps of hard heating looked at (2 hours)
MIN_EXPECTED_C = 1.0  # don't judge until the model expected at least this much warming
ALERT_RATIO = 0.5  # raise an issue below half the expected warming
COMPANY = "Demo Heating Co."  # made-up engineer company for the demo


def visit_slot(step: int, steps_per_day: int = 96) -> int:
    """First step at least ``MIN_NOTICE_STEPS`` ahead that falls in working hours (whole hours)."""
    s = step + MIN_NOTICE_STEPS
    s += (-s) % 4  # round up to the hour
    per_h = steps_per_day // 24
    while not WORK_HOURS[0] <= (s % steps_per_day) // per_h < WORK_HOURS[1]:
        s += per_h
    return s


@dataclass
class Issue:
    id: int
    room: int
    found_step: int
    expected_c: float  # warming the model expected over the window
    actual_c: float  # warming that actually happened
    status: str = "found"  # found | booked | fixed | dismissed
    quote_gbp: float = QUOTE_GBP
    paid_step: int | None = None
    visit_step: int | None = None
    fixed_step: int | None = None


class Maintenance:
    def __init__(self, n_rooms: int, allowance_gbp: float = 100.0):
        self.efficiency = np.ones(n_rooms)  # 1 = heater working normally
        self.allowance_gbp = float(allowance_gbp)
        self.spent_gbp = 0.0
        self.issues: list[Issue] = []
        self._expected = [deque(maxlen=WINDOW) for _ in range(n_rooms)]
        self._actual = [deque(maxlen=WINDOW) for _ in range(n_rooms)]

    # ---------- demo ----------

    def break_room(self, i: int) -> None:
        """Demo: the radiator valve in room ``i`` sticks, so it gives a fraction of its heat."""
        self.efficiency[i] = FAULT_EFFICIENCY

    # ---------- spotting faults ----------

    def open_issue(self, i: int) -> Issue | None:
        return next((x for x in self.issues if x.room == i and x.status in ("found", "booked")), None)

    def observe(self, step: int, before: np.ndarray, after: np.ndarray, q_kw: np.ndarray,
                rooms, t_out: float, step_h: float) -> list[Issue]:
        """Compare each room's warming with the model after one step. Returns newly found issues."""
        found = []
        for i, room in enumerate(rooms):
            if q_kw[i] < 0.5 * room.q_max_kw:  # only judge while heating hard
                continue
            passive = (t_out - before[i]) / room.tau_h * step_h
            self._expected[i].append(q_kw[i] / room.c_kwh_per_k * step_h)
            self._actual[i].append(after[i] - before[i] - passive)
            exp, act = sum(self._expected[i]), sum(self._actual[i])
            if exp >= MIN_EXPECTED_C and act < ALERT_RATIO * exp and self.open_issue(i) is None:
                issue = Issue(id=len(self.issues) + 1, room=i, found_step=step,
                              expected_c=round(float(exp), 1), actual_c=round(float(act), 1))
                self.issues.append(issue)
                found.append(issue)
        return found

    # ---------- repairs ----------

    def _get(self, issue_id: int) -> Issue:
        issue = next((x for x in self.issues if x.id == issue_id), None)
        if issue is None:
            raise ValueError("unknown issue")
        return issue

    def book(self, issue_id: int, step: int) -> Issue:
        """Approved by the user: pay the quote from the repairs allowance and book the visit."""
        issue = self._get(issue_id)
        if issue.status != "found":
            raise ValueError("that issue isn't waiting for a repair")
        if self.spent_gbp + issue.quote_gbp > self.allowance_gbp + 1e-9:
            raise ValueError("not enough left in the repairs allowance")
        self.spent_gbp += issue.quote_gbp
        issue.status, issue.paid_step, issue.visit_step = "booked", step, visit_slot(step)
        return issue

    def dismiss(self, issue_id: int) -> Issue:
        issue = self._get(issue_id)
        if issue.status != "found":
            raise ValueError("that issue can't be dismissed now")
        issue.status = "dismissed"
        return issue

    def visits_due(self, step: int) -> list[Issue]:
        """Engineer visits that have happened by ``step``: the heater works again."""
        done = []
        for issue in self.issues:
            if issue.status == "booked" and issue.visit_step is not None and step >= issue.visit_step:
                self.efficiency[issue.room] = 1.0
                self._expected[issue.room].clear()
                self._actual[issue.room].clear()
                issue.status, issue.fixed_step = "fixed", step
                done.append(issue)
        return done

    def set_allowance(self, gbp: float) -> None:
        if not 0 <= gbp <= 500:
            raise ValueError("repairs allowance must be £0 to £500")
        self.allowance_gbp = float(gbp)

    def summary(self, names, clock) -> dict:
        return {
            "allowance_gbp": self.allowance_gbp,
            "spent_gbp": round(self.spent_gbp, 2),
            "left_gbp": round(self.allowance_gbp - self.spent_gbp, 2),
            "company": COMPANY,
            "issues": [{**asdict(x), "room": names[x.room],
                        "found": clock(x.found_step), "visit": clock(x.visit_step) if x.visit_step is not None else None}
                       for x in self.issues],
        }
