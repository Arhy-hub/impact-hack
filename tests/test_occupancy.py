import numpy as np
import pytest

from heatwise.occupancy import (
    HeatmapBaseline,
    OccupancyModel,
    build_dataset,
    labels,
    train_and_compare,
)
from heatwise.sim import simulate_occupancy


def test_labels_look_ahead_only():
    occ = simulate_occupancy(2, seed=0)
    y = labels(occ, horizon=2)
    t, r = 10, 0
    assert y[t, r] == (occ.occupied[t + 1, r] or occ.occupied[t + 2, r])
    assert not y[-1].any()


def test_dataset_shapes_match():
    occ = simulate_occupancy(2, seed=0)
    X, y = build_dataset(HeatmapBaseline(4).fit(occ), occ, horizon=4)
    assert X.shape[0] == y.shape[0] == (occ.n_steps - 4) * len(occ.rooms)


def test_features_do_not_use_ground_truth():
    """Changing who is *really* there, without changing sensors, must not change predictions."""
    occ = simulate_occupancy(7, seed=0)
    model = OccupancyModel().fit(simulate_occupancy(14, seed=1))
    before = model.predict_proba(occ, 200)
    occ.occupied[:] = ~occ.occupied
    after = model.predict_proba(occ, 200)
    assert np.allclose(before, after)


def test_baseline_probabilities_in_range():
    occ = simulate_occupancy(14, seed=0)
    p = HeatmapBaseline().fit(occ).predict_proba(occ, 50)
    assert ((p > 0) & (p < 1)).all()


@pytest.fixture(scope="module")
def comparison():
    return train_and_compare(train_days=21, test_days=7, seed=0)


def test_model_is_useful(comparison):
    assert comparison["model"]["auc"] > 0.85


def test_model_beats_heatmap_baseline(comparison):
    assert comparison["model"]["brier"] < comparison["baseline"]["brier"]
