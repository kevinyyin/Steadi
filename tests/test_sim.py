import numpy as np
import pytest

from checkin import sim


def test_simulate_is_seeded_and_starts_still_at_go():
    t1, acc1, gyro1, truth1 = sim.simulate("tug", seed=7)
    t2, acc2, gyro2, truth2 = sim.simulate("tug", seed=7)
    assert np.array_equal(acc1, acc2) and truth1 == truth2
    assert t1[0] == pytest.approx(-1.0) and np.diff(t1) == pytest.approx(0.01)
    still = np.linalg.norm(acc1[t1 < 0], axis=1)
    assert still.mean() == pytest.approx(1.0, abs=0.03)  # 1 g at rest, whatever the mounting


def test_dual_task_is_slower_by_the_configured_fraction():
    p = sim.SimParams(dual_task_slowdown=0.25)
    tug = sim.simulate("tug", p)[3]["tug_s"]
    dual = sim.simulate("dual_tug", p)[3]["tug_s"]
    assert dual / tug == pytest.approx(1.25, abs=0.005)


def test_slower_walkers_take_longer():
    fast = sim.simulate("tug", sim.SimParams(walk_speed=1.4))[3]["tug_s"]
    slow = sim.simulate("tug", sim.SimParams(walk_speed=0.8))[3]["tug_s"]
    assert slow > fast + 3


def test_chair_stand_truth_applies_the_halfway_rule():
    assert sim.simulate("chair_stand", sim.SimParams(stand_cycle_s=3.0))[3]["stands"] == 10
    assert sim.simulate("sit_to_stand", reps=6)[3]["reps"] == 6


def test_balance_truth_is_capped_at_the_stance_time():
    p = sim.SimParams(hold_s={"feet_together": 60, "semi_tandem": 60, "tandem": 4.0})
    assert sim.simulate("balance_tandem", p)[3]["hold_s"] == 4.0
    assert sim.simulate("balance_semi_tandem", p)[3]["hold_s"] == 10.0
    assert sim.simulate("hold_semi_tandem", p, seconds=20)[3]["hold_s"] == 20.0


def test_walk_and_unknown_activity():
    t, acc, gyro, truth = sim.simulate("walk", seconds=30)
    assert t[-1] > 29 and truth == {}
    with pytest.raises(ValueError):
        sim.simulate("cartwheel")
