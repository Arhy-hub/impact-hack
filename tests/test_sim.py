import numpy as np

from heatwise.sim import DEFAULT_ROOMS, STEPS_PER_DAY, House, simulate_occupancy


def test_room_cools_towards_outside_without_heat():
    house = House()
    start = house.state.temps.copy()
    for _ in range(STEPS_PER_DAY):
        house.step(np.zeros(len(DEFAULT_ROOMS)), t_out=5.0)
    assert np.all(house.state.temps < start)
    assert np.all(house.state.temps > 5.0)


def test_heat_needed_reaches_target_when_within_capacity():
    house = House()
    target = house.state.temps + 0.1  # small enough to stay under q_max
    q = house.heat_needed_kw(target, t_out=5.0)
    house.step(q, t_out=5.0)
    assert np.allclose(house.state.temps, target)


def test_heat_is_capped_and_never_negative():
    house = House()
    q_hot = house.heat_needed_kw(house.state.temps + 50, t_out=5.0)
    q_cold = house.heat_needed_kw(house.state.temps - 50, t_out=5.0)
    assert np.allclose(q_hot, [r.q_max_kw for r in DEFAULT_ROOMS])
    assert np.all(q_cold == 0)


def test_electricity_uses_cop():
    house = House(cop=3.0)
    q = np.array([1.2, 0.0, 0.6])
    kwh = house.step(q, t_out=5.0)
    assert np.allclose(kwh, q * 0.25 / 3.0)


def test_occupancy_shape_and_nights_in_bedroom():
    occ = simulate_occupancy(n_days=7, seed=1)
    assert occ.occupied.shape == (7 * STEPS_PER_DAY, 3)
    bedroom = occ.rooms.index("bedroom")
    three_am = [d * STEPS_PER_DAY + 12 for d in range(7)]
    assert occ.occupied[three_am, bedroom].all()


def test_weekday_daytime_mostly_empty():
    occ = simulate_occupancy(n_days=5, seed=2, wfh_prob=0.0)
    noon = [d * STEPS_PER_DAY + 48 for d in range(5)]
    assert occ.people_home[noon].sum() == 0


def test_motion_is_noisy_view_of_occupancy():
    occ = simulate_occupancy(n_days=14, seed=3)
    hit_rate = occ.motion[occ.occupied].mean()
    false_rate = occ.motion[~occ.occupied].mean()
    assert 0.8 < hit_rate < 0.97
    assert false_rate < 0.03


def test_same_seed_same_result():
    a = simulate_occupancy(n_days=3, seed=9)
    b = simulate_occupancy(n_days=3, seed=9)
    assert (a.occupied == b.occupied).all()


def test_warmup_hours_matches_simulation():
    house = House()
    target = np.full(3, 20.0)
    hours = house.warmup_hours(target, t_out=5.0)
    assert np.all(hours > 0) and np.all(np.isfinite(hours))
    # Run at full power for that long: every room should be at (or just past) target.
    steps = int(np.ceil(hours.max() * 4))
    for _ in range(steps):
        house.step(np.array([r.q_max_kw for r in DEFAULT_ROOMS]), t_out=5.0)
    assert np.all(house.state.temps >= 19.9)
    assert np.all(House().warmup_hours(np.full(3, 10.0), 5.0) == 0)
