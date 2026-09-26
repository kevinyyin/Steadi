"""Session controller: runs the check-in (Section 5, steps 1–4) and exercise mode one step at a time.

Each step: wait for the button → "start" cue = "Go" (timing starts) → score the tagged window → "stop" cue.
"""

import logging
from datetime import datetime

import numpy as np

from . import signals, steadi
from .clock import Clock
from .store import write_recording

log = logging.getLogger(__name__)

TICK_S = 0.05  # read the sensor and the button this often
CHECK_S = 0.25  # re-run detection on the growing window this often
PRE_S = 1.0  # seconds before "Go" kept in each step's window
TUG_TIMEOUT_S = 60.0
BALANCE_S = 10.0
SET_IDLE_S = 8.0  # a sit-to-stand set ends after this long without a new rep
SET_MAX_S = 120.0
PRESS_GUARD_S = 1.0  # a press this soon after the last one taken is a double-tap: ignored
SETTLE_S = 1.0  # wait up to this long for late samples (Wi-Fi batching, phone polling) before scoring a step

CHECKIN_STEPS = [
    ("tug", "Timed Up and Go",
     "Sit in the arm chair with your back against it. On 'Go', stand up, walk to the line at your normal pace, "
     "turn, walk back, and sit down."),
    ("dual_tug", "Timed Up and Go while naming animals",
     "Same walk again, but name animals out loud the whole time."),
    ("chair_stand", "30-second chair stand",
     "Sit in the middle of the armless chair, arms crossed on your chest. On 'Go', stand up fully and sit back "
     "down, again and again, for 30 seconds."),
    ("balance_feet_together", "Balance: feet together",
     "Stand beside the counter with your feet side by side, a hand hovering over the counter. Hold for 10 seconds."),
    ("balance_semi_tandem", "Balance: semi-tandem",
     "Move one foot forward so its instep touches the big toe of the other foot. Hold for 10 seconds."),
    ("balance_tandem", "Balance: tandem",
     "Put one foot directly in front of the other, heel touching toe. Hold for 10 seconds."),
]


class Busy(Exception):
    pass


class Cancelled(Exception):
    pass


class Controller:
    def __init__(self, source, base, store, clock=None, on_event=None):
        self.source, self.base, self.store = source, base, store
        self.clock = clock or Clock()
        self.on_event = on_event or (lambda event: None)
        self.chunks = []
        self.tags = []
        self.busy = False
        self._pending = None
        self._pressed = False
        self._last_press = float("-inf")
        self._stop = None
        self._rate_t0, self._rate_n = self.clock.now(), 0
        self._last_emit = 0.0
        self.state = {
            "mode": "idle", "person_id": None, "phase": "idle", "step": None, "prompt": "", "steps": [],
            "live": {}, "led": "off", "base": base.kind, "base_connected": base.connected,
            "source": {"kind": source.kind, "simulated": source.simulated, "rate_hz": 0.0},
            "last_record": None,
        }

    # ---- inputs from the API -------------------------------------------------------------------
    def start(self, person_id, mode, plan=None):
        """Queue a session; raises Busy, KeyError (no such person), or ValueError (profile incomplete)."""
        if self.busy or self._pending:
            raise Busy("a session is already running")
        person = self.store.get(person_id)
        if mode == "checkin" and not (person["profile"].get("age") and person["profile"].get("sex")):
            raise ValueError("Add age and sex to the profile first (the STEADI chair-stand norm needs them).")
        if mode not in ("checkin", "exercise"):
            raise ValueError(f"unknown mode {mode!r}")
        self._pending = (person_id, mode, plan)

    def press(self):
        self._pressed = True

    def stop(self, reason):
        """'arms_used' during the chair stand records 0 (STEADI); 'cancel' ends the session without saving.
        'arms_used' at any other time is ignored, so a mis-tap can't zero the next chair stand."""
        chair_running = any(s["id"] == "chair_stand" and s["status"] == "running" for s in self.state["steps"])
        if reason == "arms_used" and not chair_running:
            return
        if self.busy:
            self._stop = reason

    # ---- loop ----------------------------------------------------------------------------------
    async def run(self):
        while True:
            if self._pending:
                args, self._pending = self._pending, None
                try:
                    await self.run_session(*args)
                except Exception:
                    log.exception("session failed")
                    self.base.cue("error")
                    self.busy = False
                    self.state.update(phase="stopped", step=None, prompt="Something went wrong; nothing was saved.")
                    self._emit()
            else:
                await self.tick()

    async def tick(self):
        new = self.source.read()
        if len(new):
            self.chunks.append(new)
            self._rate_n += len(new)
        if self.base.pressed():
            self._pressed = True
        now = self.clock.now()
        if now - self._rate_t0 >= 1.0:
            self.state["source"]["rate_hz"] = round(self._rate_n / (now - self._rate_t0), 1)
            self.state["base_connected"] = self.base.connected
            self._rate_t0, self._rate_n = now, 0
            if not self.busy:
                self._trim(now - PRE_S - 1.0)
                self._emit()
        await self.clock.sleep(TICK_S)

    def samples(self):
        if len(self.chunks) != 1:
            self.chunks = [np.vstack(self.chunks)] if self.chunks else [np.empty((0, 7))]
        return self.chunks[0]

    def _trim(self, t_min):
        d = self.samples()
        self.chunks = [d[d[:, 0] >= t_min]]

    def _window(self, t_go):
        d = self.samples()
        d = d[d[:, 0] >= t_go - PRE_S]
        return d[:, 0], d[:, 1:4], d[:, 4:7]

    async def _score(self, sid, t_go, t_end):
        """Score a step once its data has arrived. Hardware samples reach us late, so scoring at t_end
        straight away would read the missing tail as a short hold or a dropout. Scores the same
        window `checkin replay` does: from 1 s before "Go" to t_end."""
        deadline = self.clock.now() + SETTLE_S
        while self.clock.now() < deadline and self.samples()[:, 0].max(initial=-np.inf) < t_end:
            self._check_cancel()
            await self.tick()
        t, acc, gyro = self._window(t_go)
        keep = t <= t_end
        return signals.score_step(sid, t[keep], acc[keep], gyro[keep], t_go, t_end)

    # ---- events --------------------------------------------------------------------------------
    def _emit(self):
        self._last_emit = self.clock.now()
        self.on_event({"type": "state", **self.state})

    def _emit_live(self, t_go, **live):
        self.state["live"] = {"elapsed_s": round(self.clock.now() - t_go, 1), **live}
        if self.clock.now() - self._last_emit >= CHECK_S:
            self._emit()

    def _cue(self, name):
        self.base.cue(name)
        self.on_event({"type": "cue", "name": name})

    def _led(self, color):
        self.base.led(color)
        self.state["led"] = color

    def _take_press(self):
        """A press since the last call. One within PRESS_GUARD_S of the last press taken is ignored, so a
        double-tap can't both start a step and stop it (a 0.05 s TUG, a stance "broken" at Go)."""
        pressed, self._pressed = self._pressed, False
        now = self.clock.now()
        if not pressed or now - self._last_press < PRESS_GUARD_S:
            return False
        self._last_press = now
        return True

    def _check_cancel(self):
        if self._stop == "cancel":
            raise Cancelled()

    # ---- sessions ------------------------------------------------------------------------------
    async def run_session(self, person_id, mode, plan=None):
        person = self.store.get(person_id)
        started = datetime.now()
        session_id = started.strftime("%Y%m%d-%H%M%S") + f"-{mode}"
        self.busy, self._stop, self.tags = True, None, []
        self._trim(self.clock.now() - PRE_S - 1.0)
        if mode == "exercise":
            plan = plan or steadi.make_plan(person)
            steps = self._exercise_steps(plan)
        else:
            steps = [(sid, label) for sid, label, _ in CHECKIN_STEPS]
        self.state.update(
            mode=mode, person_id=person_id, phase="running", step=None, prompt="", live={}, last_record=None,
            steps=[{"id": sid, "label": label, "status": "pending", "result": None} for sid, label in steps],
        )
        self._led("blue")
        self._emit()
        try:
            results = await (self._checkin() if mode == "checkin" else self._exercise(plan))
        except Cancelled:
            self._cue("error")
            self._led("off")
            self.busy = False
            self.state.update(phase="stopped", step=None, prompt="Session cancelled. Nothing was saved.")
            self._emit()
            return None

        path = self.store.recording_path(session_id)
        write_recording(path, self.samples(), self.tags, self.source.kind, self.source.simulated)
        person = self.store.get(person_id)  # re-read: the profile may have changed during the session
        common = {"id": session_id, "source": self.source.kind,
                  "simulated": bool(self.source.simulated or person["simulated"]), "recording": path.name}
        if mode == "checkin":
            record = steadi.evaluate(person, steadi.metrics_from_steps(results), started)
            record.update(common, steps=results)
            person["checkins"].append(record)
            self._led(record["level"])
        else:
            record = {"date": started.isoformat(timespec="seconds"), **common, "plan": plan,
                      "sets": [r for sid, r in results.items() if sid.startswith("sit_to_stand")],
                      "holds": [r for sid, r in results.items() if sid.startswith("hold_")]}
            person["exercise"].append(record)
            self._led("off")
        self.store.save(person)
        self._cue("done")
        self.busy = False
        self.state.update(phase="done", step=None, prompt="All done. Results are on the dashboard.",
                          last_record=record, live={})
        self._emit()
        self.on_event({"type": "saved", "person_id": person_id, "mode": mode, "id": session_id})
        return record

    async def _checkin(self):
        prompts = {sid: prompt for sid, _, prompt in CHECKIN_STEPS}
        results = {}
        results["tug"] = await self._tug("tug", prompts["tug"])
        results["dual_tug"] = await self._tug("dual_tug", prompts["dual_tug"])
        results["chair_stand"] = await self._chair_stand(prompts["chair_stand"])
        for stance in steadi.STANCES:
            sid = f"balance_{stance}"
            r = await self._hold(sid, sid, prompts[sid], BALANCE_S)
            results[sid] = r
            if r.get("hold_s") is None or r["hold_s"] < BALANCE_S:  # stop at the first stance that breaks
                for s in self.state["steps"]:
                    if s["status"] == "pending":
                        s["status"] = "skipped"
                break
        return results

    @staticmethod
    def _exercise_steps(plan):
        sts, bal = plan["sit_to_stand"], plan["balance"]
        label = steadi.STANCE_LABEL[bal["stance"]]
        return [(f"sit_to_stand#{i + 1}", f"Sit-to-stands, set {i + 1} ({sts['reps']} reps)")
                for i in range(sts["sets"])] + [
            (f"hold_{bal['stance']}#{i + 1}", f"Supported balance hold {i + 1}: {label}, {bal['target_s']:g} s")
            for i in range(bal["holds"])]

    async def _exercise(self, plan):
        results = {}
        sts, bal = plan["sit_to_stand"], plan["balance"]
        for i in range(sts["sets"]):
            sid = f"sit_to_stand#{i + 1}"
            results[sid] = await self._sit_to_stand_set(
                sid, f"Sit in a sturdy chair. On 'Go', stand up and sit down {sts['reps']} times. "
                "Each beep is one rep.", sts["reps"])
        for i in range(bal["holds"]):
            sid = f"hold_{bal['stance']}#{i + 1}"
            label = steadi.STANCE_LABEL[bal["stance"]]
            results[sid] = await self._hold(
                sid, f"hold_{bal['stance']}", f"Stand at the counter, one hand resting on it, feet {label}. "
                f"Hold for {bal['target_s']:g} seconds.", bal["target_s"])
        return results

    # ---- steps ---------------------------------------------------------------------------------
    def _status(self, sid, status, result=None):
        for s in self.state["steps"]:
            if s["id"] == sid:
                s["status"] = status
                if result is not None:
                    s["result"] = result

    async def _begin(self, sid, kind, prompt, **act):
        """Wait for the button, then cue "Go" and return its time."""
        self._status(sid, "waiting")
        self.state.update(step=sid, prompt=prompt + " Press the button when ready.", live={})
        self._emit()
        self._pressed = False
        while not self._take_press():
            self._check_cancel()
            await self.tick()
        t_go = self.clock.now()
        self._cue("start")
        self.source.act(kind, **act)
        self._status(sid, "running")
        self.state["prompt"] = prompt
        self._emit()
        return t_go

    def _end(self, sid, t_go, t_end, result, cue="stop"):
        if cue:
            self._cue(cue)
        self.tags.append((sid, t_go, t_end))
        failed = "error" in result or result.get("method") == "timeout"
        self._status(sid, "failed" if failed else "done", result)
        self._emit()

    async def _tug(self, sid, prompt):
        t_go = await self._begin(sid, sid, prompt)
        next_check = t_go + 2.0
        while True:
            await self.tick()
            self._check_cancel()
            now = self.clock.now()
            self._emit_live(t_go)
            if self._take_press():  # stopwatch fallback: the helper presses when seated
                result, cue = {"tug_s": round(now - t_go, 2), "method": "button"}, "stop"
                break
            if now >= next_check:
                next_check = now + CHECK_S
                if signals.tug_end(*self._window(t_go), t_go) is not None:
                    result, cue = await self._score(sid, t_go, now), "stop"
                    break
            if now - t_go >= TUG_TIMEOUT_S:
                result, cue = {"tug_s": None, "method": "timeout"}, "error"
                break
        self._end(sid, t_go, now, result, cue)
        return result

    async def _chair_stand(self, prompt):
        sid = "chair_stand"
        t_go = await self._begin(sid, sid, prompt)
        limit = t_go + signals.CHAIR_STAND_S
        next_check, stopped, arms = t_go + CHECK_S, False, False
        while self.clock.now() < limit + 2.0:  # 2 s past the limit shows whether a last stand was over halfway
            await self.tick()
            self._check_cancel()
            now = self.clock.now()
            self._take_press()  # the button doesn't stop the chair stand
            if self._stop == "arms_used":
                self._stop, arms = None, True
                break
            if not stopped and now >= limit:
                self._cue("stop")
                stopped = True
            if now >= next_check:
                next_check = now + CHECK_S
                t, acc, _ = self._window(t_go)
                self._emit_live(t_go, reps=len(signals.stand_times(t, acc, t_go, t_limit=limit)))
        now = self.clock.now()
        if arms:  # STEADI: stop if arms are needed and record 0
            result = {"stands": 0, "arms_used": True}
        else:
            result = {**(await self._score(sid, t_go, now)), "arms_used": False}
        self._end(sid, t_go, now, result, cue=None if stopped else "stop")
        return result

    async def _hold(self, sid, kind, prompt, seconds):
        """A balance stance, timed until it breaks (auto-stop) or `seconds` pass. The button marks a break."""
        t_go = await self._begin(sid, kind, prompt, seconds=seconds)
        next_check = t_go + CHECK_S
        while True:
            await self.tick()
            self._check_cancel()
            now = self.clock.now()
            pressed = self._take_press()
            self._emit_live(t_go)
            if pressed:
                t_end = now
                break
            if now >= next_check:
                next_check = now + CHECK_S
                if signals.balance_hold(*self._window(t_go), t_go, t_go + seconds)[1]:
                    t_end = now
                    break
            if now >= t_go + seconds + 0.2:
                t_end = t_go + seconds
                break
        result = await self._score(sid, t_go, t_end)
        if pressed:
            result.update(broke=True, method="button")
        result.setdefault("method", "sensor")
        result.update(stance=kind.split("_", 1)[1], target_s=seconds)
        self._end(sid, t_go, t_end, result)
        return result

    async def _sit_to_stand_set(self, sid, prompt, reps):
        t_go = await self._begin(sid, "sit_to_stand", prompt, reps=reps)
        count, last, next_check = 0, t_go, t_go + CHECK_S
        while True:
            await self.tick()
            self._check_cancel()
            now = self.clock.now()
            if self._take_press():  # the set ends early
                break
            if now >= next_check:
                next_check = now + CHECK_S
                t, acc, _ = self._window(t_go)
                n = len(signals.stand_times(t, acc, t_go))
                for _ in range(n - count):
                    self._cue("rep")
                if n > count:
                    count, last = n, now
                self._emit_live(t_go, reps=count, target=reps)
                if count >= reps:
                    break
            if now - last > SET_IDLE_S or now - t_go > SET_MAX_S:
                break
        result = {**(await self._score(sid, t_go, now)), "target": reps}
        self._end(sid, t_go, now, result)
        return result
