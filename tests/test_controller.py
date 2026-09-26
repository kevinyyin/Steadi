import asyncio
from datetime import date

import numpy as np
import pytest

from checkin import sim, steadi
from checkin.base import VirtualBase
from checkin.clock import FakeClock
from checkin.controller import Controller
from checkin.signals import score_step
from checkin.sources import EMPTY, SimSource
from checkin.store import Store, read_recording

ALL_HOLD = {"feet_together": 60.0, "semi_tandem": 60.0, "tandem": 60.0}


class RecordingBase(VirtualBase):
    def __init__(self):
        self.cues = []

    def cue(self, name):
        self.cues.append(name)


def make(tmp_path, params=None, seed=3, source_cls=SimSource):
    clock = FakeClock(t=1000.0037)  # off the 100 Hz sample grid, like a real clock
    store = Store(tmp_path)
    person = store.create("Test Person", {"age": 72, "sex": "female", "fallen": False, "unsteady": False,
                                         "worried": False})
    source = source_cls(clock, params or sim.SimParams(), seed=seed)
    base = RecordingBase()
    ctl = Controller(source, base, store, clock)
    return ctl, source, base, store, person


def drive(ctl, coro, on_running=None):
    """Run a session, pressing the on-screen button whenever a step waits for it."""

    async def go():
        task = asyncio.ensure_future(coro)
        while not task.done():
            steps = ctl.state["steps"]
            if any(s["status"] == "waiting" for s in steps):
                ctl.press()
            running = next((s["id"] for s in steps if s["status"] == "running"), None)
            if running and on_running:
                on_running(ctl, running)
            await asyncio.sleep(0)
        return task.result()

    return asyncio.run(go())


def test_full_simulated_checkin_matches_the_simulator(tmp_path):
    p = sim.SimParams(walk_speed=1.1, dual_task_slowdown=0.25, stand_cycle_s=2.9,
                      hold_s={**ALL_HOLD, "tandem": 6.5})
    ctl, source, base, store, person = make(tmp_path, p)
    record = drive(ctl, ctl.run_session(person["id"], "checkin"))
    m, truth = record["metrics"], source.truth
    assert abs(m["tug_s"] - truth["tug"]["tug_s"]) < 0.5
    assert abs(m["dual_tug_s"] - truth["dual_tug"]["tug_s"]) < 0.5
    assert abs(m["dual_task_cost_pct"] - 25.0) < 3.0
    assert m["chair_stands"] == truth["chair_stand"]["stands"]
    assert abs(m["feet_together_s"] - 10.0) < 1.0 and abs(m["semi_tandem_s"] - 10.0) < 1.0
    assert abs(m["tandem_s"] - truth["balance_tandem"]["hold_s"]) < 1.0
    assert [f["id"] for f in record["flags"]] == ["balance"] and record["level"] == "amber"
    assert record["simulated"] is True and record["source"] == "sim"
    assert store.get(person["id"])["checkins"][-1]["id"] == record["id"]
    assert base.cues.count("start") == 6 and base.cues[-1] == "done"
    assert ctl.state["phase"] == "done" and ctl.state["led"] == "amber"


def test_timing_starts_at_go_not_at_movement(tmp_path):
    ctl, source, base, store, person = make(tmp_path)
    record = drive(ctl, ctl.run_session(person["id"], "checkin"))
    # the simulator waits 0.5 s after "Go" before moving; that reaction time is part of the TUG
    assert abs(record["metrics"]["tug_s"] - source.truth["tug"]["tug_s"]) < 0.5
    assert source.truth["tug"]["tug_s"] > 0.5


def test_recording_replays_to_the_same_scores(tmp_path):
    ctl, source, base, store, person = make(tmp_path)
    record = drive(ctl, ctl.run_session(person["id"], "checkin"))
    rec = read_recording(store.recording_path(record["id"]))
    assert rec.simulated and set(rec.steps) == set(record["steps"])
    t, acc, gyro = rec.data[:, 0], rec.data[:, 1:4], rec.data[:, 4:7]
    for sid, (t_go, t_end) in rec.steps.items():
        keep = (t >= t_go - 1.0) & (t <= t_end)
        r = score_step(sid, t[keep], acc[keep], gyro[keep], t_go, t_end)
        for k in ("tug_s", "stands", "hold_s"):
            if k in r:
                assert abs(r[k] - record["steps"][sid][k]) <= 0.02, (sid, k)
    assert record["metrics"]["tandem_s"] == 10.0  # a full hold must not replay as 9.99 (that would flag)


def test_balance_stops_at_the_first_stance_that_breaks(tmp_path):
    p = sim.SimParams(hold_s={**ALL_HOLD, "semi_tandem": 3.0})
    ctl, source, base, store, person = make(tmp_path, p)
    record = drive(ctl, ctl.run_session(person["id"], "checkin"))
    m = record["metrics"]
    assert abs(m["semi_tandem_s"] - 3.0) < 1.0 and m["tandem_s"] == 0.0
    assert "balance_tandem" not in record["steps"]
    rec = read_recording(store.recording_path(record["id"]))
    t_go, t_end = rec.steps["balance_semi_tandem"]
    assert t_end - t_go < 4.0  # auto-stop: the stance ended when it broke, not at 10 s
    assert [s["status"] for s in ctl.state["steps"]][-1] == "skipped"


def test_arms_used_records_zero_chair_stands(tmp_path):
    def arms(ctl, running):
        if running == "chair_stand":
            ctl.stop("arms_used")

    ctl, source, base, store, person = make(tmp_path)
    record = drive(ctl, ctl.run_session(person["id"], "checkin"), on_running=arms)
    assert record["steps"]["chair_stand"] == {"stands": 0, "arms_used": True}
    assert "chair_stand" in [f["id"] for f in record["flags"]]


def test_button_during_tug_is_the_stopwatch_fallback(tmp_path):
    def press_late(ctl, running):
        if running == "tug" and ctl.state["live"].get("elapsed_s", 0) >= 5.0:
            ctl.press()

    ctl, source, base, store, person = make(tmp_path)
    record = drive(ctl, ctl.run_session(person["id"], "checkin"), on_running=press_late)
    assert record["steps"]["tug"]["method"] == "button" and 5.0 <= record["steps"]["tug"]["tug_s"] < 5.2


def test_cancel_saves_nothing(tmp_path):
    ctl, source, base, store, person = make(tmp_path)
    result = drive(ctl, ctl.run_session(person["id"], "checkin"), on_running=lambda c, r: c.stop("cancel"))
    assert result is None and store.get(person["id"])["checkins"] == []
    assert ctl.state["phase"] == "stopped" and base.cues[-1] == "error" and not ctl.busy


class SilentAfterGo(SimSource):
    """The belt's battery dies at the first "Go"."""

    def act(self, kind, **kw):
        self.dead = True

    def read(self):
        return EMPTY if getattr(self, "dead", False) else super().read()


def test_a_dead_sensor_is_not_scored_as_a_poor_result(tmp_path):
    ctl, source, base, store, person = make(tmp_path, source_cls=SilentAfterGo)
    record = drive(ctl, ctl.run_session(person["id"], "checkin"))
    assert record["steps"]["tug"]["method"] == "timeout" and record["metrics"]["tug_s"] is None
    assert record["metrics"]["chair_stands"] is None and record["metrics"]["tandem_s"] is None
    assert record["flags"] == [] and "error" in base.cues


def test_exercise_session_counts_reps_and_times_holds(tmp_path):
    p = sim.SimParams(hold_s={**ALL_HOLD, "feet_together": 12.0})
    ctl, source, base, store, person = make(tmp_path, p)
    plan = {"sit_to_stand": {"sets": 2, "reps": 5},
            "balance": {"stance": "feet_together", "holds": 2, "target_s": 20.0}}
    record = drive(ctl, ctl.run_session(person["id"], "exercise", plan))
    assert [s["reps"] for s in record["sets"]] == [5, 5]
    assert base.cues.count("rep") == 10
    assert all(abs(h["hold_s"] - 12.0) < 1.0 and h["stance"] == "feet_together" for h in record["holds"])
    assert store.get(person["id"])["exercise"][-1]["id"] == record["id"]


def test_exercise_without_a_plan_uses_the_persons_plan(tmp_path):
    ctl, source, base, store, person = make(tmp_path)
    record = drive(ctl, ctl.run_session(person["id"], "exercise"))
    assert len(record["sets"]) == 2 and len(record["holds"]) == 2  # no check-in yet: the standard plan
    assert all(s["reps"] == 8 for s in record["sets"])


def test_a_dead_sensor_in_exercise_does_not_break_the_dashboard(tmp_path):
    ctl, source, base, store, person = make(tmp_path, source_cls=SilentAfterGo)
    record = drive(ctl, ctl.run_session(person["id"], "exercise"))
    assert all("error" in r for r in record["sets"] + record["holds"])  # not measured, never 0
    d = steadi.dashboard(store.get(person["id"]), date.today())  # the next plan and adherence still work
    assert d["adherence"]["weeks"][-1]["reps"] == 0 and d["plan"]["balance"]["stance"] == "feet_together"


class LateSource(SimSource):
    """Wi-Fi hardware: each sample reaches the laptop LAG_S after it was taken."""

    LAG_S = 0.3

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)
        self.buf = EMPTY

    def read(self):
        self.buf = np.vstack([self.buf, super().read()])
        ready = self.buf[:, 0] <= self.clock.now() - self.LAG_S
        out, self.buf = self.buf[ready], self.buf[~ready]
        return out


@pytest.mark.parametrize("lag", [0.3, 0.7])  # ESP32 broadcasts held for the next AP beacon; phyphox HTTP polling
def test_late_sensor_data_is_waited_for_not_scored_short(tmp_path, lag):
    ctl, source, base, store, person = make(tmp_path, source_cls=type("Late", (LateSource,), {"LAG_S": lag}))
    record = drive(ctl, ctl.run_session(person["id"], "checkin"))
    m = record["metrics"]
    assert [sid for sid, r in record["steps"].items() if "error" in r] == []
    assert (m["feet_together_s"], m["semi_tandem_s"], m["tandem_s"]) == (10.0, 10.0, 10.0) and record["flags"] == []
    assert abs(m["tug_s"] - source.truth["tug"]["tug_s"]) < 0.5
    assert m["chair_stands"] == source.truth["chair_stand"]["stands"]
    plan = {"sit_to_stand": {"sets": 1, "reps": 5},
            "balance": {"stance": "feet_together", "holds": 1, "target_s": 20.0}}
    ex = drive(ctl, ctl.run_session(person["id"], "exercise", plan))
    assert ex["sets"][0]["reps"] == 5 and ex["holds"][0]["hold_s"] == 20.0  # a full hold reaches its target


def test_arms_used_outside_the_chair_stand_is_ignored(tmp_path):
    def mis_tap(ctl, running):
        if running == "tug":
            ctl.stop("arms_used")

    ctl, source, base, store, person = make(tmp_path)
    record = drive(ctl, ctl.run_session(person["id"], "checkin"), on_running=mis_tap)
    assert record["steps"]["chair_stand"] == {"stands": source.truth["chair_stand"]["stands"], "arms_used": False}
