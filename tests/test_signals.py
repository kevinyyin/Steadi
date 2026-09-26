import numpy as np
import pytest

from checkin import sim
from checkin.signals import balance_hold, data_error, score_step, stand_times, tug_end

MOUNTS = [(0, 0, 0), (90, 0, 0), (30, -60, 120)]  # the belt can be worn any way round


@pytest.mark.parametrize("mount", MOUNTS)
@pytest.mark.parametrize("speed", [0.8, 1.0, 1.2, 1.5])
def test_tug_end_is_within_half_a_second(speed, mount):
    t, acc, gyro, truth = sim.simulate("tug", sim.SimParams(walk_speed=speed, mount_deg=mount), seed=1)
    assert abs(tug_end(t, acc, gyro, 0.0) - truth["tug_s"]) < 0.5


@pytest.mark.parametrize("slowdown", [0.1, 0.2, 0.35])
def test_dual_task_cost_is_within_three_points(slowdown):
    p = sim.SimParams(walk_speed=1.0, dual_task_slowdown=slowdown)
    tug, dual = (tug_end(*sim.simulate(kind, p, seed=2)[:3], 0.0) for kind in ("tug", "dual_tug"))
    assert abs((dual - tug) / tug * 100 - slowdown * 100) < 3.0


def test_standing_pause_at_the_turn_does_not_end_the_tug():
    t, acc, gyro, truth = sim.simulate("tug", sim.SimParams(pause_s=4.0), seed=4)
    assert abs(tug_end(t, acc, gyro, 0.0) - truth["tug_s"]) < 0.5


def test_tug_not_over_while_still_walking():
    t, acc, gyro, truth = sim.simulate("tug", seed=5)
    cut = t < truth["tug_s"] - 1.0
    assert tug_end(t[cut], acc[cut], gyro[cut], 0.0) is None


@pytest.mark.parametrize("mount", MOUNTS)
@pytest.mark.parametrize("cycle", [1.8, 2.6, 3.5, 5.0])
def test_chair_stand_count_matches(cycle, mount):
    t, acc, gyro, truth = sim.simulate("chair_stand", sim.SimParams(stand_cycle_s=cycle, mount_deg=mount), seed=3)
    keep = t <= 32.0
    assert len(stand_times(t[keep], acc[keep], 0.0, t_limit=30.0)) == truth["stands"]


@pytest.mark.parametrize("cycle, extra", [(2.221, 1), (2.078, 0)])  # 82% vs 32% of the way up at 30 s
def test_a_stand_more_than_halfway_up_at_30_s_counts(cycle, extra):
    t, acc, gyro, truth = sim.simulate("chair_stand", sim.SimParams(stand_cycle_s=cycle), seed=0)
    keep = t <= 32.0
    counted = len(stand_times(t[keep], acc[keep], 0.0, t_limit=30.0))
    completed = len([x for x in stand_times(t[keep], acc[keep], 0.0) if x <= 30.0])
    assert counted == truth["stands"] == completed + extra


@pytest.mark.parametrize("cycle", [1.8, 2.6, 4.0])
@pytest.mark.parametrize("reps", [1, 5, 10])
def test_sit_to_stand_reps_match(reps, cycle):
    t, acc, gyro, truth = sim.simulate("sit_to_stand", sim.SimParams(stand_cycle_s=cycle), seed=6, reps=reps)
    assert len(stand_times(t, acc, 0.0)) == reps


def test_a_rise_still_in_progress_is_not_counted_yet():
    t, acc, gyro, _ = sim.simulate("sit_to_stand", seed=6, reps=3)
    rises = stand_times(t, acc, 0.0)
    cut = t < rises[0] - 0.3  # partway up the first stand
    assert stand_times(t[cut], acc[cut], 0.0) == []


@pytest.mark.parametrize("stance", ["feet_together", "semi_tandem", "tandem"])
@pytest.mark.parametrize("cap", [0.8, 4.0, 9.5, 60.0])
def test_balance_hold_is_within_one_second(stance, cap):
    p = sim.SimParams(hold_s={s: cap for s in ("feet_together", "semi_tandem", "tandem")}, mount_deg=(45, 45, 45))
    t, acc, gyro, truth = sim.simulate("balance_" + stance, p, seed=2)
    hold, broke, sway = balance_hold(t, acc, gyro, 0.0, 10.0)
    assert abs(hold - truth["hold_s"]) < 1.0 and broke == (cap < 10)


def test_full_hold_reads_exactly_ten_seconds():
    t, acc, gyro, _ = sim.simulate("balance_tandem", seed=1)
    keep = t < 10.0  # the last sample lands one tick before 10 s
    assert balance_hold(t[keep], acc[keep], gyro[keep], 0.0, 10.0)[0] == 10.0


def test_more_sway_measures_more():
    sways = [balance_hold(*sim.simulate("balance_tandem", sim.SimParams(sway=s), seed=1)[:3], 0.0, 10.0)[2]
             for s in (0.5, 1.0, 2.0)]
    assert sways == sorted(sways) and sways[0] > 0


@pytest.mark.parametrize("n", [0, 5, 50])
def test_short_windows_do_not_crash(n):
    t, acc, gyro, _ = sim.simulate("tug", seed=1)
    t, acc, gyro = t[:n], acc[:n], gyro[:n]
    assert tug_end(t, acc, gyro, 0.0) is None
    assert stand_times(t, acc, 0.0) == []
    assert balance_hold(t, acc, gyro, 0.0, 10.0)[0] >= 0.0


def test_a_sensor_dropout_is_an_error_not_a_low_score():
    t, acc, gyro, _ = sim.simulate("chair_stand", seed=1)
    gap = (t < 5.0) | (t > 20.0)  # the belt went quiet for 15 s
    assert data_error(t[gap], 0.0, 32.0) == "sensor data dropped out"
    assert score_step("chair_stand", t[gap], acc[gap], gyro[gap], 0.0, 32.0) == {"error": "sensor data dropped out"}
    assert score_step("tug", t[:0], acc[:0], gyro[:0], 0.0, 12.0) == {"error": "no sensor data"}


def test_score_step_dispatches_on_the_step_id():
    t, acc, gyro, truth = sim.simulate("hold_tandem", sim.SimParams(hold_s={"feet_together": 60, "semi_tandem": 60,
                                                                           "tandem": 7.0}), seed=1, seconds=20)
    r = score_step("hold_tandem#2", t, acc, gyro, 0.0, 20.0)
    assert r["stance"] == "tandem" and abs(r["hold_s"] - 7.0) < 1.0
    with pytest.raises(ValueError):
        score_step("jumping_jacks", t, acc, gyro, 0.0, 20.0)
    assert np.isfinite(r["sway"])


def test_lost_packets_at_the_end_of_a_stance_are_not_a_short_hold():
    t, acc, gyro, _ = sim.simulate("balance_tandem", seed=1)
    tail = t < 9.7  # UDP packets from 9.7 s to the 10 s mark never arrived (windows end at t_end)
    r = score_step("balance_tandem", t[tail], acc[tail], gyro[tail], 0.0, 10.0)
    assert r["hold_s"] == 10.0 and not r["broke"]  # a short gap is treated like one mid-stance
    lost = t < 9.0
    r = score_step("balance_tandem", t[lost], acc[lost], gyro[lost], 0.0, 10.0)
    assert r == {"error": "sensor data dropped out"}  # a longer one is still "not measured", never a flag
