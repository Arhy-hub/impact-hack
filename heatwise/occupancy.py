"""Predict which rooms will be used soon.

Target: for room r at step t, ``y = 1`` if the room is occupied at any step in
``t+1 .. t+horizon``. ``horizon`` should cover the room's warm-up time, so a
positive prediction means "start heating now".

Two predictors share one interface (``predict_proba(occ, step)``):

* ``HeatmapBaseline``: the historical rate of y for (room, weekday/weekend,
  time slot). This is what a "learned routine heatmap" does.
* ``OccupancyModel``: logistic regression that takes the heatmap's
  probability (as a log-odds feature) and corrects it with live sensor
  signals: recent motion in the room, motion anywhere, phones home. This lets
  it react to odd days (working from home, a late start, everyone out) that
  the heatmap alone can't see. See docs/DECISIONS.md (O3) for why it's built
  this way rather than as a model on time features alone.

Only *sensor* data (motion, phones home) is used as input, never the ground
truth ``occupied``. Ground truth is used only for labels.

Run ``python -m heatwise.occupancy`` to train on simulated weeks and print
Brier score and AUC for both predictors on a later, unseen week.
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

from .sim import STEPS_PER_DAY, Occupancy, simulate_occupancy

DEFAULT_HORIZON = 12  # steps = 3 hours ahead (covers warm-up from 12°C; DECISIONS O8)
MOTION_LAGS = (0, 1, 2, 4, 8)  # steps back: now, 15, 30, 60, 120 min


def labels(occ: Occupancy, horizon: int = DEFAULT_HORIZON) -> np.ndarray:
    """y[t, r] = room r occupied at some step in (t, t+horizon]. Last steps are padded False."""
    n, r = occ.occupied.shape
    y = np.zeros((n, r), dtype=bool)
    for h in range(1, horizon + 1):
        y[:-h] |= occ.occupied[h:]
    return y


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _live_features(occ: Occupancy, step: int, room: int) -> list[float]:
    lags = [float(occ.motion[step - k, room]) if step - k >= 0 else 0.0 for k in MOTION_LAGS]
    return lags + [float(occ.motion[step].any()), float(occ.people_home[step])]


def features(baseline: "HeatmapBaseline", occ: Occupancy, step: int) -> np.ndarray:
    """One feature row per room at ``step``: heatmap log-odds plus live sensor signals."""
    prior = _logit(baseline.predict_proba(occ, step))
    return np.array(
        [[prior[r], *_live_features(occ, step, r)] for r in range(len(occ.rooms))]
    )


def build_dataset(
    baseline: "HeatmapBaseline", occ: Occupancy, horizon: int = DEFAULT_HORIZON
) -> tuple[np.ndarray, np.ndarray]:
    """Features X and labels y for every (step, room), excluding the last ``horizon`` steps."""
    y_all = labels(occ, horizon)
    X = np.vstack([features(baseline, occ, t) for t in range(occ.n_steps - horizon)])
    y = y_all[: occ.n_steps - horizon].ravel().astype(int)
    return X, y


class HeatmapBaseline:
    """Historical rate of 'used within the horizon' per (room, weekend, slot)."""

    def __init__(self, horizon: int = DEFAULT_HORIZON):
        self.horizon = horizon
        self.table: np.ndarray | None = None

    def fit(self, occ: Occupancy) -> "HeatmapBaseline":
        y = labels(occ, self.horizon)
        n_rooms = len(occ.rooms)
        hits = np.zeros((n_rooms, 2, STEPS_PER_DAY))
        counts = np.zeros((n_rooms, 2, STEPS_PER_DAY))
        for t in range(occ.n_steps - self.horizon):
            w = int(occ.weekday(t) >= 5)
            s = occ.slot(t)
            hits[:, w, s] += y[t]
            counts[:, w, s] += 1
        # Laplace smoothing so unseen cells sit at 0.5 rather than 0 or 1.
        self.table = (hits + 1) / (counts + 2)
        return self

    def predict_proba(self, occ: Occupancy, step: int) -> np.ndarray:
        w = int(occ.weekday(step) >= 5)
        return self.table[:, w, occ.slot(step)].copy()


class OccupancyModel:
    """Heatmap prior corrected by live sensors (logistic regression).

    Training is cross-fitted to avoid leakage: the training days are split in
    two halves; the heatmap fitted on one half supplies the prior feature for
    the other half, and vice versa. The heatmap used at prediction time is
    then refitted on all training days.
    """

    def __init__(self, horizon: int = DEFAULT_HORIZON, C: float = 1.0):
        self.horizon = horizon
        self.clf = LogisticRegression(C=C, max_iter=2000)
        self.baseline = HeatmapBaseline(horizon)

    def fit(self, occ: Occupancy) -> "OccupancyModel":
        days = occ.n_steps // STEPS_PER_DAY
        half = (days // 2) * STEPS_PER_DAY
        a, b = _slice(occ, 0, half), _slice(occ, half, occ.n_steps)
        Xa, ya = build_dataset(HeatmapBaseline(self.horizon).fit(b), a, self.horizon)
        Xb, yb = build_dataset(HeatmapBaseline(self.horizon).fit(a), b, self.horizon)
        self.clf.fit(np.vstack([Xa, Xb]), np.concatenate([ya, yb]))
        self.baseline.fit(occ)
        return self

    def predict_proba(self, occ: Occupancy, step: int) -> np.ndarray:
        return self.clf.predict_proba(features(self.baseline, occ, step))[:, 1]


def _slice(occ: Occupancy, start: int, end: int) -> Occupancy:
    """Steps [start, end) as their own Occupancy; ``start`` must be a day boundary."""
    return Occupancy(
        occ.rooms,
        occ.occupied[start:end],
        occ.motion[start:end],
        occ.people_home[start:end],
        occ.weekday(start),
    )


def evaluate(predictor, occ: Occupancy, horizon: int = DEFAULT_HORIZON) -> dict[str, float]:
    """Brier score (lower is better) and AUC (higher is better) on ``occ``."""
    y_all = labels(occ, horizon)
    p, y = [], []
    for t in range(occ.n_steps - horizon):
        p.extend(predictor.predict_proba(occ, t))
        y.extend(y_all[t])
    p, y = np.array(p), np.array(y, dtype=int)
    return {"brier": float(brier_score_loss(y, p)), "auc": float(roc_auc_score(y, p))}


def train_and_compare(train_days: int = 35, test_days: int = 7, seed: int = 0) -> dict:
    """Train both predictors on ``train_days``, test on the following ``test_days``.

    The test week is generated with a different seed and starts on the weekday
    after training ends, so it is genuinely unseen (a time-based split).
    """
    train = simulate_occupancy(train_days, seed=seed)
    test = simulate_occupancy(test_days, seed=seed + 1000, start_day=train_days % 7)
    baseline = HeatmapBaseline().fit(train)
    model = OccupancyModel().fit(train)
    return {
        "baseline": evaluate(baseline, test),
        "model": evaluate(model, test),
        "predictors": (baseline, model),
    }


if __name__ == "__main__":
    result = train_and_compare()
    for name in ("baseline", "model"):
        m = result[name]
        print(f"{name:9s} Brier {m['brier']:.4f}  AUC {m['auc']:.4f}")
