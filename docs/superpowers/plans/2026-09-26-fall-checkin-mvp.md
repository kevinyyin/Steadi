# Fall-Risk Check-In MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the screen → assess → intervene → track loop from `docs/COMPETITION.md`, so a full STEADI check-in and an exercise session run from the start button to saved, scored results with no hardware. The ESP32 belt, phone, and Arduino base station plug in behind the same interfaces.

**Architecture:** A plain-Python core:
- **Simulator** (`sim.py`): a seeded lower-back IMU simulator.
- **Detectors** (`signals.py`): orientation-free TUG end, stand counting with STEADI's halfway rule, and balance hold and sway.
- **STEADI logic** (`steadi.py`): norms, flags, fall-risk level, rolling baseline, exercise plan, and adherence.

An asyncio session controller (`controller.py`) runs one step at a time: wait for the button, send the "Go" cue (timing starts), score the tagged window, send the "stop" cue. It talks to two small duck-typed interfaces: motion sources (simulator, CSV replay, ESP32 UDP, phyphox) and base stations (on-screen, Arduino serial). FastAPI serves a JSON + WebSocket API (`docs/API.md`) and one bare-bones static page. People live in JSON files under `data/`. Every session's raw stream is saved as a CSV that `checkin replay` re-scores.

**Tech Stack:**
- **Python:** 3.11 with uv (`uv_build` backend); numpy, FastAPI, uvicorn, websockets, and pyserial.
- **Testing and lint:** pytest with httpx2 (what Starlette's `TestClient` now uses); ruff.
- **Front end:** vanilla HTML/JS with Chart.js 4.5.1 vendored.
- **Firmware:** Arduino sketches built with arduino-cli. The cores `arduino:renesas_uno`, `arduino:avr`, and `esp32:esp32` are already installed on this machine.

**Spec:** `docs/COMPETITION.md` (Sections 0, 0.1, 4 "Claims", 5, 7), `docs/PARTS_LIST.md` (pins, wiring, buzzer cues), and the project rules in `CLAUDE.md`.

**How this plan was checked:** every code block was run before the plan was written:
- **Tests and lint:** 128 tests pass and ruff is clean.
- **Sketches:** both compile. The base station builds for Uno R4 Minima, Uno, and Nano; the belt builds for ESP32 and ESP32-S3.
- **Task boundaries:** each task's tests pass with only the earlier tasks present and fail without the task's own code.
- **Live run:** a real-time check-in and a quick exercise session were driven from the dashboard's Button in a browser.
- **Accuracy:** 72 full simulated check-ins across walking speeds, dual-task slowdowns, stand rates, and balance failures all met the Done criteria. Worst cases: TUG 0.33 s, dual-task cost 0.4 points, holds 0.10 s.

Copy the blocks exactly. If something disagrees with this plan, stop and report instead of improvising.

## Global Constraints

Every task's requirements include these.

- **Stack:** Python 3.11 with uv; FastAPI serving one static page plus a WebSocket; vanilla HTML/JS with a vendored chart library; JSON files in `data/`; pytest; ruff; firmware built with `arduino-cli` (CLAUDE.md).
- **Commands that must work:** `uv sync`, `uv run checkin serve --source sim --base virtual` (→ http://localhost:8000), `uv run checkin replay <file.csv>`, `uv run pytest`, `uv run ruff check .`
- **Hardware isn't final:** everything runs on the simulator and on-screen base station; real devices are adapters behind the same interfaces.
- **No SKDH:** no core score depends on it. Out of scope: audio, the Claude API summary, the fall safety net, SKDH, the WYZE camera, the step 5 walk (the simulator can still produce a walk).
- **Offline:** "The dashboard must work with no internet … no cloud calls or CDN assets." Chart.js is vendored into `src/checkin/static/vendor/`.
- **Settings, not code:** "Serial port, UDP port, and Wi-Fi credentials are settings, never hard-coded. The ESP32 broadcasts UDP instead of targeting one IP." Unicast is an option.
- **Claims:** say "fall-risk screening", "flags increased fall risk", and "change from baseline". Never say it diagnoses, predicts when someone will fall, or guarantees prevention. Label simulated data "Simulated" wherever it appears.
- **STEADI cutoffs (Section 4):** TUG ≥12 s; chair stand below the age/sex average; full tandem stance held <10 s. Chair-stand table (flag when below):

  | Age | 60–64 | 65–69 | 70–74 | 75–79 | 80–84 | 85–89 | 90–94 |
  |---|---|---|---|---|---|---|---|
  | Men | <14 | <12 | <12 | <11 | <10 | <8 | <7 |
  | Women | <12 | <11 | <10 | <10 | <9 | <8 | <4 |

- **Timing (Section 5):** "TUG and chair-stand timing start on the 'Go' cue (the buzzer), not on detected movement. TUG ends when the person is seated again." Chair stand: "a stand over halfway at 30 s counts".
- **Dual-task cost:** "(dual-task TUG time − normal TUG time) ÷ normal TUG time × 100".
- **Level (ours, not STEADI's):** "a flag is a 'yes' to any key question or any test past its cutoff. Green = no flags; amber = 1 flag or a sustained decline vs. baseline; red = 2+ flags. Always show which items flagged."
- **Balance:** "feet together → semi-tandem → full tandem, 10 s each (stop at first failure)". Never single-leg or eyes-closed; auto-stop if sway spikes; "stop the chair stand if arms are needed (STEADI records a 0)".
- **Exercise:** sit-to-stands in sets of 5–10 with a beep per rep; supported balance holds progressing as holds succeed; the plan leans on the weakest area; every session is logged.
- **Sensor:** MPU-6050 at ±8 g, ±500 °/s, 100 Hz, built-in low-pass filter on, read from the FIFO. It must start even if a clone reports an unexpected WHO_AM_I. I2C pins must be configurable (GPIO 21/22 on a classic ESP32).
- **Base station pins (PARTS_LIST Section 2):** button D2 (`INPUT_PULLUP`), RGB red D9, green D6, blue D5 (470 Ω each), buzzer D8 via `tone()`.
  - Cues: start = two rising beeps (2000 → 3000 Hz); stop = one long low beep (1500 Hz, 600 ms); done = three-note rising melody; error = three quick low beeps.
- **Frontend (CLAUDE.md):** no cream or off-white backgrounds, italic accent words in headings, numbered "01 / 02 / 03" section labels, monospace labels, or pill-shaped buttons. The dashboard stays bare-bones; it will be redesigned against `docs/API.md`.
- **Working style (CLAUDE.md):**
  - Tick tasks off in `TASKS.md` as you go.
  - End with **Blocked on me**, **Changed**, and **Found**. Under Found, mark each adapter not tested against real hardware and say what was tested instead.

## Review Focus

The five inputs most likely to bite a real person that the spec doesn't spell out, and the tests that pin them:

1. **The belt goes quiet mid-step** (battery, Wi-Fi gap). The step must read "not measured", never 0 stands, 0 s, or a flag.
   - Task 2 `test_a_sensor_dropout_is_an_error_not_a_low_score`
   - Task 3 `test_a_sensor_error_never_becomes_a_zero`
   - Task 7 `test_a_dead_sensor_is_not_scored_as_a_poor_result`
2. **An older adult pauses standing mid-TUG** (after rising, or at the line before turning). The TUG keeps timing until they sit.
   - Task 2 `test_standing_pause_at_the_turn_does_not_end_the_tug`, `test_tug_not_over_while_still_walking`
3. **The belt or phone is worn any way round.** Scores must not change.
   - Task 2 `MOUNTS` parametrization across TUG, chair stand, and balance
4. **A full 10 s stance recorded at an arbitrary real clock time** must read exactly 10.0 live and on replay. 9.99 would flag the tandem stance.
   - Task 2 `test_full_hold_reads_exactly_ten_seconds`
   - Task 4 `test_recording_round_trip_keeps_step_windows`
   - Task 7 `test_recording_replays_to_the_same_scores` (FakeClock off the 100 Hz grid)
5. **Ages outside the STEADI table** (a 25-year-old judge, a 97-year-old) use the nearest group and say so.
   - Task 3 `test_ages_outside_the_table_use_the_nearest_group_and_say_so`
   - Task 9 `test_checkin_over_the_api_from_button_to_dashboard` (age 34 → "women 60–64 (the youngest STEADI group)")

## Decisions This Plan Makes

The spec leaves these open. None changes the check-in protocol, the STEADI cutoffs, or the claims, but reviewers should know them:

- **Key questions:** the three questions count as one flag that names every "yes", because STEADI treats them as one screen. So three "yes" answers alone give amber, not red.
- **"Go":** the moment the start cue is sent (the first of the two rising beeps).
- **Seated again (TUG end):** seat contact, meaning where the sit-down's downward movement stops, confirmed by 1 s of stillness in a seated posture.
- **Chair stand:** the stop cue sounds at 30 s. Two more seconds are recorded so a stand in progress can be judged "over halfway".
- **Ages outside the table:** under 60 uses the 60–64 norm (Section 10, risk 6); over 94 uses the 90–94 norm. Both are labelled.
- **Sustained decline (our rule):** worse than the rolling baseline two check-ins in a row. The baseline is the mean of up to 4 earlier check-ins and needs at least 2. "Worse" means TUG +10%, dual-task cost +10 points, chair stands −2, or tandem −3 s.
- **Exercise plan:**
  - Sit-to-stands: 8 reps per set; 2 sets, or 3 when chair stands are below the STEADI line + 2.
  - Balance: 2 supported holds of 20 s, or 4 with a balance flag. Holds move up a stance once every hold reaches 20 s.
  - Target: 5 exercise days a week.
- **The helper's button doubles as a stopwatch:** during a TUG it stops the clock (the risk register's hour-12 kill criterion); during a stance it marks a break.
- **Dropouts and timeouts:** a step whose data has a hole longer than 0.5 s is "not measured". A TUG times out after 60 s (error cue), so a missed sit-down never hangs the session.

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `pyproject.toml`, `.python-version`, `.gitignore`, `TASKS.md` | Project, dependencies, entry point `checkin`, ruff/pytest config, checklist | 1 |
| `src/checkin/sim.py` | Seeded lower-back IMU simulator with true scores | 1 |
| `src/checkin/signals.py` | One step's IMU window → score (TUG end, stands, holds, dropout guard) | 2 |
| `src/checkin/steadi.py` | Cutoffs, flags, level, baseline, alert text, plan, adherence, dashboard payload | 3 |
| `src/checkin/store.py` | People as JSON; recordings as CSV | 4 |
| `src/checkin/clock.py` | Real clock and instant test clock shared by the controller and sources | 5 |
| `src/checkin/sources.py` | Motion sources: simulator, CSV replay, ESP32 UDP, phyphox | 5 |
| `firmware/phyphox/belt-imu.phyphox` | Phone experiment: accelerometer + gyroscope at 100 Hz | 5 |
| `src/checkin/base.py` | Base stations: virtual, Arduino serial | 6 |
| `firmware/PROTOCOL.md` | Serial and UDP protocols, cue tones | 6 |
| `src/checkin/controller.py` | Session controller: check-in and exercise mode | 7 |
| `src/checkin/seed.py` | "Simulated: Dad" 8-week history | 8 |
| `src/checkin/server.py`, `docs/API.md` | FastAPI JSON + WebSocket API and its documentation | 9 |
| `src/checkin/static/vendor/chart.umd.min.js` | Vendored Chart.js 4.5.1 | 9 |
| `src/checkin/cli.py` | `checkin serve / replay / seed` | 10 |
| `src/checkin/static/index.html`, `app.js` | Bare-bones dashboard | 11 |
| `firmware/base_station/base_station.ino` | Arduino: button, RGB LED, buzzer cues | 12 |
| `firmware/esp32_imu/esp32_imu.ino`, `config.h`, `secrets.example.h` | ESP32 belt: MPU-6050 FIFO → UDP | 13 |
| `README.md`, `.claude/launch.json` | Every hardware combination; preview config | 14 |

Leave the unrelated saved web page in `docs/` untracked. Don't add, move, or delete it.

## Execution Order

Tasks 1–11 are sequential (each builds on the previous). Tasks 12 and 13 (firmware) don't depend on any Python task or on each other, so they can run in parallel with Tasks 1–11. Task 14 comes last.

---

### Task 1: Project scaffold and simulator

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore`, `TASKS.md`, `src/checkin/__init__.py` (empty), `src/checkin/sim.py`
- Test: `tests/test_sim.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `sim.SimParams(walk_speed=1.2, dual_task_slowdown=0.20, stand_cycle_s=2.6, hold_s={stance: 60.0}, sway=1.0, noise=1.0, mount_deg=(0, 0, 0), pause_s=0.0)`
  - `sim.render(kind, p, rng, **kw) -> (acc (n,3) g, gyro (n,3) deg/s, truth: dict, end_pitch: float)`: samples from "Go" (τ = 0) at 100 Hz.
    - Kinds: `"tug"`, `"dual_tug"`, `"chair_stand"`, `"sit_to_stand"` (`reps=`), `"balance_<stance>"` and `"hold_<stance>"` (`seconds=`, default 10), `"walk"` (`seconds=`).
    - `truth`: `{"tug_s"}`, `{"stands"}`, `{"reps"}`, `{"hold_s"}`, or `{}`.
  - `sim.simulate(kind, p=None, seed=0, pre_s=1.0, start_pitch=None, **kw) -> (t, acc, gyro, truth)`: "Go" at t = 0, with `pre_s` of stillness before it.
  - `sim.Device(p, rng)` is callable `(acc, gyro) -> (acc, gyro)` and adds mounting rotation, bias, and noise. `sim.idle(n, pitch) -> (acc, gyro)`.
  - Constants: `FS = 100.0`, `G = 9.81`, `SIT_PITCH = -15.0`, `STANCES = ("feet_together", "semi_tandem", "tandem")`.

- [ ] **Step 1: Create the repo and project files**

```bash
git init
mkdir -p src/checkin tests
touch src/checkin/__init__.py
```

`pyproject.toml`:

```toml
[project]
name = "checkin"
version = "0.1.0"
description = "STEADI fall-risk screening check-in: belt, base station, family dashboard"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "numpy>=1.26",
    "pyserial>=3.5",
    "uvicorn>=0.30",
    "websockets>=13",
]

[project.scripts]
checkin = "checkin.cli:main"

[dependency-groups]
dev = [
    "httpx2>=2.13",
    "pytest>=8",
    "ruff>=0.6",
]

[build-system]
requires = ["uv_build>=0.8,<0.13"]
build-backend = "uv_build"

[tool.ruff]
line-length = 120

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pytest.ini_options]
testpaths = ["tests"]
filterwarnings = ["error"]
```

`.python-version`:

```text
3.11
```

`.gitignore`:

```text
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
.DS_Store
data/
firmware/esp32_imu/secrets.h
```

`TASKS.md`:

```markdown
# Tasks

Plan: docs/superpowers/plans/2026-09-26-fall-checkin-mvp.md

- [ ] 1. Project scaffold and simulator
- [ ] 2. Step scoring (signals)
- [ ] 3. STEADI logic
- [ ] 4. People store and recordings
- [ ] 5. Clock and motion sources
- [ ] 6. Base stations and protocol
- [ ] 7. Session controller
- [ ] 8. Simulated: Dad history
- [ ] 9. API server and docs/API.md
- [ ] 10. CLI
- [ ] 11. Dashboard page
- [ ] 12. Base station firmware
- [ ] 13. ESP32 belt firmware
- [ ] 14. README and final verification
```

Run: `uv sync`
Expected: resolves and installs fastapi, numpy, pyserial, uvicorn, websockets, httpx2, pytest, ruff, and builds `checkin`.

- [ ] **Step 2: Write the failing test** `tests/test_sim.py`

```python
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
```

- [ ] **Step 3: Run it to see it fail**

Run: `uv run pytest tests/test_sim.py -q`
Expected: FAIL with `ImportError: cannot import name 'sim' from 'checkin'`.

- [ ] **Step 4: Write** `src/checkin/sim.py`

The simulator models a lower-back sensor in a body frame (x forward, y left, z up):
- Sit-to-stands and sit-downs: a forward-flexion bump and a 0.35 m minimum-jerk rise or fall.
- Walking: step-frequency oscillations. Turns: a 180° yaw-rate half-sine.
- Balance: band-limited sway, with a sideways step when the stance breaks.

Durations scale with walking speed; the dual-task TUG stretches every phase by `1 + dual_task_slowdown`, so its true cost equals the setting exactly. The TUG's true end is seat contact: 90% of the way through the sit-down, where the descent reaches the seat. The chair stand's true count applies STEADI's halfway rule at 30 s.

```python
"""Simulated lower-back IMU: seeded accelerometer (g) + gyroscope (deg/s) at 100 Hz.

Body frame: x forward, y left, z up. Pitch is forward trunk flexion (deg).
Every render starts at the "Go" cue (tau = 0) and returns the true scores.
"""

from dataclasses import dataclass, field

import numpy as np

FS = 100.0
G = 9.81
SIT_PITCH = -15.0  # deg: the pelvis tilts back when seated
RISE_M = 0.35  # lower back rises this much from seated to standing
STANCES = ("feet_together", "semi_tandem", "tandem")
SWAY_RMS = {"feet_together": 0.10, "semi_tandem": 0.16, "tandem": 0.25}  # m/s² at sway=1


@dataclass
class SimParams:
    walk_speed: float = 1.2  # m/s; TUG walking, turns, and transitions scale with it
    dual_task_slowdown: float = 0.20  # dual-task TUG takes this fraction longer
    stand_cycle_s: float = 2.6  # one sit→stand→sit cycle
    hold_s: dict = field(default_factory=lambda: {s: 60.0 for s in STANCES})  # time until each stance breaks
    sway: float = 1.0  # multiplier on SWAY_RMS
    noise: float = 1.0  # multiplier on sensor noise and bias
    mount_deg: tuple = (0.0, 0.0, 0.0)  # belt mounting rotation (roll, pitch, yaw)
    pause_s: float = 0.0  # TUG: stands still at the line this long before turning


def _mj(u):
    """Minimum-jerk 0→1 position profile."""
    u = np.clip(u, 0.0, 1.0)
    return 10 * u**3 - 15 * u**4 + 6 * u**5


def _mj_acc(u):
    """Second derivative of _mj with respect to u (zero outside [0, 1])."""
    inside = (u >= 0) & (u <= 1)
    return np.where(inside, 60 * u - 180 * u**2 + 120 * u**3, 0.0)


class _Track:
    """Accumulates per-sample pitch, yaw rate, linear acceleration, and oscillating gyro."""

    def __init__(self):
        self.parts = []
        self.t = 0.0

    def add(self, dur, pitch, yaw=0.0, acc=None, gyro=None):
        n = int(round(dur * FS))
        seg = {
            "pitch": np.broadcast_to(pitch, (n,)).astype(float),
            "yaw": np.broadcast_to(yaw, (n,)).astype(float),
            "acc": np.zeros((n, 3)) if acc is None else acc,
            "gyro": np.zeros((n, 3)) if gyro is None else gyro,
        }
        self.parts.append(seg)
        self.t += n / FS

    def arrays(self):
        return {k: np.concatenate([p[k] for p in self.parts]) for k in ("pitch", "yaw", "acc", "gyro")}


def _tau(dur):
    return np.arange(int(round(dur * FS))) / FS


def _still(tr, dur, pitch):
    tr.add(dur, pitch)


def _transition(tr, dur, up):
    """Sit-to-stand (up) or stand-to-sit: forward flexion bump, posture change, vertical move."""
    tau = _tau(dur)
    u = tau / dur
    p0, p1, flex = (SIT_PITCH, 0.0, 35.0) if up else (0.0, SIT_PITCH, 25.0)
    pitch = p0 + (p1 - p0) * _mj((u - 0.3) / 0.7) + flex * np.sin(np.pi * np.minimum(u / 0.7, 1.0)) ** 2
    lift = 0.7 * dur
    start = 0.3 if up else 0.2
    a_up = RISE_M * _mj_acc((u - start) / 0.7) / lift**2 * (1 if up else -1)
    a_fwd = 0.1 * (np.pi / dur) ** 2 * 2 * np.cos(2 * np.pi * u)
    acc = np.column_stack([a_fwd, np.zeros_like(u), a_up])
    tr.add(dur, pitch, acc=acc)


def _gait(tau, dur, speed, scale=1.0):
    """Walking oscillations: returns (acc (n,3) m/s², gyro (n,3) deg/s)."""
    f = 0.9 + 0.75 * speed  # steps per second
    env = np.clip(np.minimum(tau, dur - tau) / 0.4, 0, 1) * scale
    ph = 2 * np.pi * f * tau
    acc = np.column_stack(
        [1.2 * env * np.sin(ph + np.pi / 2), 0.8 * env * np.sin(ph / 2), 2.0 * (speed / 1.2) * env * np.sin(ph)]
    )
    gyro = np.column_stack([6 * env * np.sin(ph / 2 + 0.5), 4 * env * np.sin(ph), 8 * env * np.sin(ph / 2 + 1.0)])
    return acc, gyro


def _walk(tr, dur, speed):
    acc, gyro = _gait(_tau(dur), dur, speed)
    tr.add(dur, 3.0, acc=acc, gyro=gyro)


def _turn(tr, dur, speed, deg=180.0):
    tau = _tau(dur)
    yaw = deg * (np.pi / 2) / dur * np.sin(np.pi * tau / dur)
    acc, gyro = _gait(tau, dur, speed, scale=0.6)
    tr.add(dur, 3.0, yaw=yaw, acc=acc, gyro=gyro)


def _sway(rng, n, rms):
    """Band-limited random horizontal sway acceleration (n, 2) with the given RMS."""
    tau = np.arange(n) / FS
    out = np.zeros((n, 2))
    for axis in range(2):
        f = rng.uniform(0.2, 1.5, 8)
        ph = rng.uniform(0, 2 * np.pi, 8)
        x = np.sin(2 * np.pi * f[:, None] * tau[None, :] + ph[:, None]).sum(axis=0)
        out[:, axis] = x / (x.std() + 1e-9) * rms
    return out


def _stand_sway(tr, rng, dur, rms):
    n = int(round(dur * FS))
    sw = _sway(rng, n, rms)
    acc = np.column_stack([sw[:, 0], sw[:, 1], np.zeros(n)])
    tr.add(dur, 0.0, acc=acc)


def _step_out(tr):
    """Stance breaks: a quick sideways step."""
    dur = 0.6
    tau = _tau(dur)
    s = np.sin(np.pi * tau / dur)
    acc = np.column_stack([np.zeros_like(s), 3.0 * s, 1.5 * np.sin(2 * np.pi * tau / dur)])
    gyro = np.column_stack([60 * s, 25 * s, np.zeros_like(s)])
    tr.add(dur, 0.0, acc=acc, gyro=gyro)


def _tug(tr, p, slowdown):
    k = 1.0 + slowdown
    speed = p.walk_speed / k
    slow = 1.2 / p.walk_speed * k
    _still(tr, 0.5 * k, SIT_PITCH)  # reaction to "Go"
    _transition(tr, 1.3 * slow, up=True)
    _walk(tr, 3.0 / speed, speed)
    if p.pause_s:
        _still(tr, p.pause_s * k, 3.0)
    _turn(tr, 1.3 * slow, speed)
    _walk(tr, 3.0 / speed, speed)
    _turn(tr, 1.1 * slow, speed)
    sit = 1.5 * slow
    _transition(tr, sit, up=False)
    truth = {"tug_s": round(tr.t - 0.1 * sit, 3)}  # seated = the descent reaches the seat (90% through)
    _still(tr, 4.0, SIT_PITCH)
    return truth


def _stand_cycles(tr, p, reps=None, until=None):
    """Chair stands: count full stands; returns completed stands and (if `until`) the halfway-rule count."""
    c = p.stand_cycle_s
    up, top, down, seat = 0.42 * c, 0.08 * c, 0.42 * c, 0.08 * c
    _still(tr, 0.4, SIT_PITCH)
    count = 0
    while (reps is not None and count < reps) or (until is not None and tr.t < until + 2.0):
        start = tr.t
        _transition(tr, up, up=True)
        if until is not None and start < until < tr.t:
            u = (until - start) / up
            if _mj((u - 0.3) / 0.7) > 0.5:  # more than halfway up at the end counts
                count += 1
        elif until is None or tr.t <= until:
            count += 1
        _still(tr, top, 0.0)
        _transition(tr, down, up=False)
        _still(tr, seat, SIT_PITCH)
    _still(tr, 3.0, SIT_PITCH)
    return count


def _balance(tr, rng, p, stance, seconds):
    rms = SWAY_RMS[stance] * p.sway
    hold = min(seconds, p.hold_s[stance])
    if hold < seconds:
        _stand_sway(tr, rng, hold, rms)
        _step_out(tr)
        _stand_sway(tr, rng, seconds - hold + 2.0, rms * 2)
    else:
        _stand_sway(tr, rng, seconds + 2.0, rms)
    return round(hold, 3)


def render(kind, p, rng, **kw):
    """Clean body-frame signals for one activity starting at "Go".

    Returns (acc g (n,3), gyro deg/s (n,3), truth dict, end posture pitch).
    """
    tr = _Track()
    if kind in ("tug", "dual_tug"):
        truth = _tug(tr, p, p.dual_task_slowdown if kind == "dual_tug" else 0.0)
        end = SIT_PITCH
    elif kind == "chair_stand":
        truth = {"stands": _stand_cycles(tr, p, until=30.0)}
        end = SIT_PITCH
    elif kind == "sit_to_stand":
        truth = {"reps": _stand_cycles(tr, p, reps=kw["reps"])}
        end = SIT_PITCH
    elif kind.startswith(("balance_", "hold_")):
        stance = kind.split("_", 1)[1]
        truth = {"hold_s": _balance(tr, rng, p, stance, kw.get("seconds", 10.0))}
        end = 0.0
    elif kind == "walk":
        _walk(tr, kw.get("seconds", 30.0), p.walk_speed)
        truth = {}
        end = 0.0
    else:
        raise ValueError(f"unknown activity {kind!r}")
    return (*_to_sensor(tr.arrays()), truth, end)


def _to_sensor(a):
    th = np.radians(a["pitch"])
    s, c = np.sin(th), np.cos(th)
    fw = a["acc"] + np.array([0.0, 0.0, G])  # specific force, heading frame
    acc = np.column_stack([c * fw[:, 0] - s * fw[:, 2], fw[:, 1], s * fw[:, 0] + c * fw[:, 2]]) / G
    pitch_rate = np.gradient(a["pitch"]) * FS
    gyro = a["gyro"] + np.column_stack([np.zeros_like(th), pitch_rate, np.zeros_like(th)])
    gyro += a["yaw"][:, None] * np.column_stack([-s, np.zeros_like(s), c])
    return acc, gyro


def idle(n, pitch):
    """Still posture: (acc, gyro) for n samples."""
    th = np.radians(pitch)
    acc = np.tile([-np.sin(th), 0.0, np.cos(th)], (n, 1))
    return acc, np.zeros((n, 3))


def _rot(deg):
    r, p, y = np.radians(deg)
    rx = np.array([[1, 0, 0], [0, np.cos(r), -np.sin(r)], [0, np.sin(r), np.cos(r)]])
    ry = np.array([[np.cos(p), 0, np.sin(p)], [0, 1, 0], [-np.sin(p), 0, np.cos(p)]])
    rz = np.array([[np.cos(y), -np.sin(y), 0], [np.sin(y), np.cos(y), 0], [0, 0, 1]])
    return rz @ ry @ rx


class Device:
    """Sensor imperfections that stay fixed for one belt: mounting, bias, noise."""

    def __init__(self, p, rng):
        self.rot = _rot(p.mount_deg).T
        self.rng = rng
        self.noise = p.noise
        self.acc_bias = rng.normal(0, 0.01, 3) * p.noise
        self.gyro_bias = rng.normal(0, 1.5, 3) * p.noise

    def __call__(self, acc, gyro):
        n = len(acc)
        acc = acc @ self.rot.T + self.acc_bias + self.rng.normal(0, 0.005 * self.noise, (n, 3))
        gyro = gyro @ self.rot.T + self.gyro_bias + self.rng.normal(0, 0.1 * self.noise, (n, 3))
        return acc, gyro


def simulate(kind, p=None, seed=0, pre_s=1.0, start_pitch=None, **kw):
    """One activity with `pre_s` seconds of stillness before "Go" at t = 0.

    Returns (t, acc, gyro, truth). Used by tests and `checkin replay` fixtures.
    """
    p = p or SimParams()
    rng = np.random.default_rng(seed)
    dev = Device(p, rng)
    acc, gyro, truth, _ = render(kind, p, rng, **kw)
    if start_pitch is None:
        start_pitch = 0.0 if kind.startswith(("balance_", "hold_", "walk")) else SIT_PITCH
    pa, pg = idle(int(pre_s * FS), start_pitch)
    acc, gyro = dev(np.vstack([pa, acc]), np.vstack([pg, gyro]))
    t = np.arange(len(acc)) / FS - pre_s
    return t, acc, gyro, truth
```

- [ ] **Step 5: Run the tests and lint**

Run: `uv run pytest tests/test_sim.py -q && uv run ruff check .`
Expected: `6 passed`, then `All checks passed!`

- [ ] **Step 6: Commit**

Tick task 1 in `TASKS.md`, then:

```bash
git add pyproject.toml uv.lock .python-version .gitignore TASKS.md CLAUDE.md docs/COMPETITION.md docs/PARTS_LIST.md docs/superpowers src/checkin/__init__.py src/checkin/sim.py tests/test_sim.py
git commit -m "feat: project scaffold and seeded lower-back IMU simulator"
```

---

### Task 2: Step scoring (signals)

**Files:**
- Create: `src/checkin/signals.py`
- Test: `tests/test_signals.py`

**Interfaces:**
- Consumes: `sim.simulate`, `sim.SimParams` (tests only).
- Produces. All inputs are `t` (n,) s, `acc` (n,3) g, `gyro` (n,3) deg/s, and `t_go`. Windows should start about 1 s before "Go".
  - `tug_end(t, acc, gyro, t_go) -> float | None`: time seated again.
  - `stand_times(t, acc, t_go, t_limit=None) -> list[float]`: completed stands. With `t_limit`, a stand more than halfway up at the limit counts.
  - `balance_hold(t, acc, gyro, t_go, t_end) -> (hold_s, broke, sway_mps2)`.
  - `data_error(t, t_go, t_end) -> str | None`: `"no sensor data"` or `"sensor data dropped out"`.
  - `score_step(step_id, t, acc, gyro, t_go, t_end) -> dict`. It dispatches on the part of the step id before `#`, and raises `ValueError` for unknown steps:
    - TUG: `{"tug_s", "method": "sensor"|"window end"}`
    - chair stand: `{"stands"}`
    - sit-to-stand: `{"reps"}`
    - balance or hold: `{"stance", "hold_s", "broke", "sway"}`
    - missing data: `{"error"}`
  - Constants: `CHAIR_STAND_S = 30.0`, `MAX_GAP_S = 0.5`, plus the tuning knobs at the top of the file.

How the detectors work (they never assume which way the belt is mounted):
- **TUG end:** the first 1 s run of stillness (acc std < 0.03 g and bias-corrected gyro < 8 °/s) after at least 3 s of movement, in a posture closer to the pre-"Go" seated posture than to walking. It's then refined to seat contact: where the vertical velocity of the last downward move returns to zero.
- **Vertical velocity:** the integral of `|acc| − mean`, detrended with a 4 s moving average. A 6 s or 8 s window breaks rep counting; 4 s was the best of those tested.
- **Stands:** upward velocity bumps peaking above 0.2 m/s. A stand counts when it completes. At the chair-stand limit, a bump still rising counts if its displacement so far is over half the median full stand.
- **Balance break:** acc departs 0.2 g from the stance's first 0.5 s, or the gyro exceeds 30 °/s. Sway is the RMS of horizontal acceleration in m/s². A stance with data to within 50 ms of its end was held for the whole window.

- [ ] **Step 1: Write the failing test** `tests/test_signals.py`

```python
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
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/test_signals.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'checkin.signals'`.

- [ ] **Step 3: Write** `src/checkin/signals.py`

```python
"""Turn one step's IMU window into a score. Orientation-free: works however the belt is mounted.

Inputs everywhere: t (n,) seconds, acc (n,3) g, gyro (n,3) deg/s, t_go = the "Go" cue.
Windows should include ~1 s before "Go" (the person is still, seated or standing).
"""

import numpy as np

G = 9.81

# Tuning knobs: set from real recordings with `checkin replay`.
STILL_ACC_G = 0.03  # rolling std of acc below this = still
STILL_GYRO_DPS = 8.0  # rolling mean |gyro| below this = still
STILL_WIN_S = 0.4
SEATED_HOLD_S = 1.0  # stillness this long after walking = seated again
MIN_MOVING_S = 3.0  # TUG must move this long before it can end
RISE_PEAK_MPS = 0.2  # a stand's upward velocity must peak above this
BREAK_ACC_G = 0.2  # balance: acc departs from the stance posture by this much
BREAK_GYRO_DPS = 30.0  # balance: or the trunk rotates this fast
MAX_GAP_S = 0.5  # a longer hole in the data means the sensor dropped out: don't score the step
CHAIR_STAND_S = 30.0


def _roll(x, win_s, fs):
    """Centered moving average along axis 0 (edges average what's available)."""
    w = max(1, min(len(x), int(round(win_s * fs))))
    k = np.ones(w)
    if x.ndim == 1:
        return np.convolve(x, k, "same") / np.convolve(np.ones(len(x)), k, "same")
    return np.column_stack([_roll(x[:, i], win_s, fs) for i in range(x.shape[1])])


def _fs(t):
    return 1.0 / np.median(np.diff(t))


def _unit(v):
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def _angle(a, b):
    return np.degrees(np.arccos(np.clip(np.sum(_unit(a) * _unit(b), axis=-1), -1, 1)))


def _still(t, acc, gyro, bias):
    fs = _fs(t)
    mean = _roll(acc, STILL_WIN_S, fs)
    acc_sd = np.sqrt(np.sum(_roll(acc**2, STILL_WIN_S, fs) - mean**2, axis=1).clip(0))
    gyro_mag = _roll(np.linalg.norm(gyro - bias, axis=1), STILL_WIN_S, fs)
    return (acc_sd < STILL_ACC_G) & (gyro_mag < STILL_GYRO_DPS)


def tug_end(t, acc, gyro, t_go):
    """Time the person is seated again, or None if not yet seen.

    Seated = still for SEATED_HOLD_S after at least MIN_MOVING_S of movement,
    in a posture closer to the pre-"Go" seated posture than to walking.
    """
    if (t >= t_go).sum() < 10:
        return None
    pre = (t >= t_go - 1.0) & (t < t_go)
    if pre.sum() < 10:
        pre = (t >= t_go) & (t < t_go + 0.3)
    bias = np.median(gyro[pre], axis=0)
    seated_ref = acc[pre].mean(axis=0)
    after = t >= t_go
    t, acc, gyro = t[after], acc[after], gyro[after]
    fs = _fs(t)
    still = _still(t, acc, gyro, bias)
    moving = ~still
    if moving.sum() < 10:
        return None
    upright_ref = np.median(acc[moving], axis=0)
    posture = _roll(acc, 0.5, fs)
    seated = _angle(posture, seated_ref) <= _angle(posture, upright_ref) + 5.0
    moved = np.cumsum(moving) / fs
    hold = int(SEATED_HOLD_S * fs)
    ok = still & seated & (moved >= MIN_MOVING_S)
    # first index where `ok` holds for `hold` samples in a row
    run = np.convolve(ok.astype(int), np.ones(hold, int), "valid")
    hits = np.flatnonzero(run == hold)
    if len(hits) == 0:
        return None
    t_still = t[hits[0]] - STILL_WIN_S / 2
    # Seat contact: where the last downward move (the sit-down) comes to rest, if it's near the stillness.
    v = _vertical_velocity(t, acc)
    down = v < 0
    edges = np.flatnonzero(np.diff(down.astype(int)))
    bounds = np.concatenate([[0], edges + 1, [len(v)]])
    for a, b in reversed(list(zip(bounds[:-1], bounds[1:], strict=True))):
        if down[a] and v[a:b].min() <= -RISE_PEAK_MPS and b < len(v):
            if t_still - 1.5 <= t[b] <= t_still + 0.5:
                return float(t[b])
            break
    return float(t_still)


def _vertical_velocity(t, acc):
    """Vertical velocity (m/s) from |acc|: orientation-free, drift removed with a 4 s moving average."""
    fs = _fs(t)
    mag = np.linalg.norm(acc, axis=1)
    v = np.cumsum((mag - mag.mean()) * G) / fs
    return v - _roll(v, 4.0, fs)


def stand_times(t, acc, t_go, t_limit=None):
    """Times each full stand is reached after "Go".

    With `t_limit` (chair stand: Go + 30 s), a stand still rising at the limit
    counts if it's more than halfway up (STEADI), and is reported at t_limit.
    """
    keep = t >= t_go - 1.0
    t, acc = t[keep], acc[keep]
    if len(t) < 10:
        return []
    fs = _fs(t)
    v = _vertical_velocity(t, acc)
    up = v > 0
    edges = np.flatnonzero(np.diff(up.astype(int)))
    bounds = np.concatenate([[0], edges + 1, [len(v)]])
    rises = []  # (start index, end index, displacement m); end == len(v) means still rising
    for a, b in zip(bounds[:-1], bounds[1:], strict=True):
        if up[a] and v[a:b].max() >= RISE_PEAK_MPS and t[a] >= t_go:
            rises.append((a, b, v[a:b].sum() / fs))
    done = [d for _, b, d in rises if b < len(v)]
    full = np.median(done) if done else 0.3
    out = []
    for a, b, _ in rises:
        if b < len(v) and (t_limit is None or t[b] <= t_limit):
            out.append(float(t[b]))
        elif t_limit is not None and t[a] < t_limit <= t[-1]:
            so_far = v[a : np.searchsorted(t, t_limit)].sum() / fs
            if so_far > 0.5 * full:  # more than halfway up at the limit counts
                out.append(float(t_limit))
    return out


def balance_hold(t, acc, gyro, t_go, t_end):
    """(hold seconds, broke?, RMS sway m/s²) for a stance timed from "Go" to t_end at most."""
    keep = t >= t_go
    t, acc, gyro = t[keep], acc[keep], gyro[keep]
    if len(t) < 10:
        return 0.0, False, 0.0
    fs = _fs(t)
    first = t < t_go + 0.5
    ref = acc[first].mean(axis=0)
    bias = np.median(gyro[first], axis=0)
    dev = np.linalg.norm(_roll(acc, 0.1, fs) - ref, axis=1)
    rot = _roll(np.linalg.norm(gyro - bias, axis=1), 0.1, fs)
    broke = (dev > BREAK_ACC_G) | (rot > BREAK_GYRO_DPS)
    broke &= t <= t_end
    idx = np.flatnonzero(broke)
    stop = t[idx[0]] if len(idx) else (t_end if t[-1] >= t_end - 0.05 else t[-1])  # held to the end
    hold = max(0.0, float(stop - t_go))
    during = t < stop
    if during.sum() < 10:
        return round(hold, 2), bool(len(idx)), 0.0
    a = acc[during]
    down = _unit(a.mean(axis=0))
    horiz = a - np.outer(a @ down, down)
    sway = float(np.sqrt(np.mean(np.sum((horiz - horiz.mean(axis=0)) ** 2, axis=1))) * G)
    return round(hold, 2), bool(len(idx)), round(sway, 3)


def data_error(t, t_go, t_end):
    """Why a step window can't be scored, or None."""
    inside = t[(t >= t_go) & (t <= t_end)]
    if len(inside) < 10:
        return "no sensor data"
    if np.diff(np.concatenate([[t_go], inside, [t_end]])).max() > MAX_GAP_S:
        return "sensor data dropped out"
    return None


def score_step(step, t, acc, gyro, t_go, t_end):
    """Final score for one step window. `step` is a step id like "tug" or "sit_to_stand#2".

    A window with missing data scores {"error": ...} so a dropout never reads as a poor result.
    """
    kind = step.split("#")[0]
    if kind not in ("tug", "dual_tug", "chair_stand", "sit_to_stand") and not kind.startswith(("balance_", "hold_")):
        raise ValueError(f"unknown step {step!r}")
    error = data_error(t, t_go, t_end)
    if error:
        return {"error": error}
    if kind in ("tug", "dual_tug"):
        end = tug_end(t, acc, gyro, t_go)
        method = "sensor"
        if end is None or end > t_end:
            end, method = t_end, "window end"
        return {"tug_s": round(end - t_go, 2), "method": method}
    if kind == "chair_stand":
        return {"stands": len(stand_times(t, acc, t_go, t_limit=t_go + CHAIR_STAND_S))}
    if kind == "sit_to_stand":
        return {"reps": len(stand_times(t, acc, t_go))}
    hold, broke, sway = balance_hold(t, acc, gyro, t_go, t_end)
    return {"stance": kind.split("_", 1)[1], "hold_s": hold, "broke": broke, "sway": sway}
```

- [ ] **Step 4: Run the tests and lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: `66 passed`, then `All checks passed!`

- [ ] **Step 5: Commit**

Tick task 2 in `TASKS.md`, then:

```bash
git add src/checkin/signals.py tests/test_signals.py TASKS.md
git commit -m "feat: orientation-free TUG, chair-stand, and balance scoring"
```

---

### Task 3: STEADI logic

**Files:**
- Create: `src/checkin/steadi.py`
- Test: `tests/test_steadi.py`

**Interfaces:**
- Consumes: nothing (pure functions on dicts).
- Produces:
  - `chair_norm(age, sex) -> (cutoff, label)`
  - `metrics_from_steps(steps: dict[step_id, result]) -> metrics`, with keys `tug_s`, `dual_tug_s`, `dual_task_cost_pct`, `chair_stands`, `<stance>_s`, `<stance>_sway`
  - `flags_for(profile, metrics) -> [{"id", "text"}]`, where the ids are `key_questions`, `tug`, `chair_stand`, `balance`
  - `changes_for(metrics, history)`, `declines_for(changes, history)`, `level_for(flags, declines) -> "green"|"amber"|"red"`, `alert_for(name, level, flags, declines) -> dict | None`
  - `evaluate(person, metrics, when: datetime) -> record` with `date`, `key_questions`, `metrics`, `cutoffs`, `flags`, `changes`, `declines`, `level`, `alert`
  - `next_stance(logs)`, `make_plan(person) -> {"sit_to_stand": {"sets", "reps"}, "balance": {"stance", "holds", "target_s"}, "why"}`
  - `adherence(logs, today: date, weeks=8)`, `trends(person)`, `dashboard(person, today) -> dict` (the payload of `GET /api/people/{id}/dashboard`)
  - Constants: `STANCES`, `STANCE_LABEL`, `TUG_CUTOFF_S = 12.0`, `TANDEM_CUTOFF_S = 10.0`, `CHAIR_NORMS`, `TRACKED`, `KEY_QUESTIONS`.
- Person dict (stored by Task 4): `{"id", "name", "simulated", "profile": {"age", "sex", "fallen", "unsteady", "worried"}, "checkins": [record], "exercise": [log]}`.
- Exercise log: `{"date", "sets": [{"reps", "target"}], "holds": [{"stance", "hold_s", "target_s", ...}], ...}`.

- [ ] **Step 1: Write the failing test** `tests/test_steadi.py`

```python
import json
import re
from datetime import date, datetime, timedelta

import pytest

from checkin import steadi


def person(age=78, sex="male", **answers):
    profile = {"age": age, "sex": sex, "fallen": False, "unsteady": False, "worried": False, **answers}
    return {"id": "p", "name": "Pat", "simulated": False, "profile": profile, "checkins": [], "exercise": []}


def metrics(tug=10.0, dual=12.0, stands=13, tandem=10.0, feet=10.0, semi=10.0):
    return steadi.metrics_from_steps({
        "tug": {"tug_s": tug}, "dual_tug": {"tug_s": dual}, "chair_stand": {"stands": stands},
        "balance_feet_together": {"hold_s": feet, "sway": 0.1},
        "balance_semi_tandem": {"hold_s": semi, "sway": 0.2},
        "balance_tandem": {"hold_s": tandem, "sway": 0.3},
    })


@pytest.mark.parametrize("age, sex, cutoff, label", [
    (60, "male", 14, "men 60–64"), (64, "male", 14, "men 60–64"), (65, "male", 12, "men 65–69"),
    (78, "male", 11, "men 75–79"), (94, "male", 7, "men 90–94"), (62, "female", 12, "women 60–64"),
    (72, "female", 10, "women 70–74"), (91, "female", 4, "women 90–94"),
])
def test_chair_norms_match_the_steadi_table(age, sex, cutoff, label):
    assert steadi.chair_norm(age, sex) == (cutoff, label)


def test_ages_outside_the_table_use_the_nearest_group_and_say_so():
    assert steadi.chair_norm(25, "female") == (12, "women 60–64 (the youngest STEADI group)")
    assert steadi.chair_norm(97, "male") == (7, "men 90–94 (the oldest STEADI group)")


def test_cutoffs_are_inclusive_where_steadi_says():
    ids = lambda m: [f["id"] for f in steadi.flags_for(person()["profile"], m)]  # noqa: E731
    assert ids(metrics(tug=11.99)) == [] and ids(metrics(tug=12.0)) == ["tug"]
    assert ids(metrics(stands=11)) == [] and ids(metrics(stands=10)) == ["chair_stand"]
    assert ids(metrics(tandem=10.0)) == [] and ids(metrics(tandem=9.9)) == ["balance"]


def test_any_yes_to_the_key_questions_is_one_flag_naming_the_answers():
    flags = steadi.flags_for(person(fallen=True, worried=True)["profile"], metrics())
    assert [f["id"] for f in flags] == ["key_questions"]
    assert "fallen in the past year" in flags[0]["text"] and "worries about falling" in flags[0]["text"]


def test_dual_task_cost_and_stopping_at_the_first_failed_stance():
    m = steadi.metrics_from_steps({"tug": {"tug_s": 10.0}, "dual_tug": {"tug_s": 12.5},
                                   "balance_feet_together": {"hold_s": 10.0, "sway": 0.1},
                                   "balance_semi_tandem": {"hold_s": 4.2, "sway": 0.4}})
    assert m["dual_task_cost_pct"] == 25.0 and m["chair_stands"] is None
    assert (m["semi_tandem_s"], m["tandem_s"]) == (4.2, 0.0)  # tandem not attempted: STEADI counts it as failed


def test_a_sensor_error_never_becomes_a_zero():
    m = steadi.metrics_from_steps({"tug": {"error": "no sensor data"}, "chair_stand": {"error": "x"},
                                   "balance_feet_together": {"error": "x"}})
    assert m["tug_s"] is None and m["chair_stands"] is None and m["tandem_s"] is None
    assert steadi.flags_for(person()["profile"], m) == []


def test_levels():
    assert steadi.level_for([], []) == "green"
    assert steadi.level_for([{"id": "tug"}], []) == "amber"
    assert steadi.level_for([], [{"id": "tug_s"}]) == "amber"
    assert steadi.level_for([{"id": "tug"}, {"id": "balance"}], []) == "red"


def add(p, m, day):
    rec = steadi.evaluate(p, m, datetime(2026, 9, 1) + timedelta(weeks=day))
    p["checkins"].append(rec)
    return rec


def test_change_from_baseline_needs_two_earlier_check_ins():
    p = person()
    assert add(p, metrics(stands=13), 0)["changes"]["chair_stands"] is None
    assert add(p, metrics(stands=13), 1)["changes"]["chair_stands"] is None
    ch = add(p, metrics(stands=12), 2)["changes"]["chair_stands"]
    assert ch == {"baseline": 13, "change": -1, "worse": False}


def test_sustained_decline_needs_two_worse_check_ins_in_a_row():
    p = person(age=62, sex="female")  # norm 12: 13 → 11 would flag, so stay above it
    for i, stands in enumerate([17, 17, 17]):
        add(p, metrics(stands=stands), i)
    first = add(p, metrics(stands=14), 3)
    assert first["changes"]["chair_stands"]["worse"] and first["declines"] == [] and first["level"] == "green"
    second = add(p, metrics(stands=14), 4)
    assert [d["id"] for d in second["declines"]] == ["chair_stands"] and second["level"] == "amber"
    assert "change from baseline" not in second["alert"]["title"]  # plain title; the items carry the detail


def test_alert_wording_never_overclaims():
    p = person(fallen=True)
    rec = add(p, metrics(tug=13.0, stands=8, tandem=3.0), 0)
    assert rec["level"] == "red" and len(rec["alert"]["items"]) == 4
    text = json.dumps(rec).lower()
    assert "flags increased fall risk" in text
    assert not re.search(r"diagnos|predict|prevent|guarantee", text)


def test_plan_leans_on_the_weakest_area():
    def plan_after(**kw):
        p = person()  # 78-year-old man: the STEADI line is 11 stands
        add(p, metrics(**kw), 0)
        plan = steadi.make_plan(p)
        return plan["sit_to_stand"]["sets"], plan["balance"]["holds"]

    assert steadi.make_plan(person())["why"] == "no check-in yet: the standard plan"
    assert plan_after(stands=9) == (3, 2)  # below the line
    assert plan_after(stands=12) == (3, 2)  # near it still counts as low
    assert plan_after(stands=13) == (2, 2)  # a full tandem hold is not a weak area
    assert plan_after(stands=16, tandem=6.0) == (2, 4)
    assert plan_after(stands=9, tandem=6.0) == (3, 4)


def test_balance_holds_progress_once_every_hold_hits_its_target():
    hold = lambda stance, s: {"stance": stance, "hold_s": s, "target_s": 20.0}  # noqa: E731
    assert steadi.next_stance([]) == "feet_together"
    assert steadi.next_stance([{"holds": [hold("feet_together", 20), hold("feet_together", 20)]}]) == "semi_tandem"
    assert steadi.next_stance([{"holds": [hold("semi_tandem", 20), hold("semi_tandem", 9)]}]) == "semi_tandem"
    assert steadi.next_stance([{"holds": [hold("tandem", 20)]}]) == "tandem"
    assert steadi.next_stance([{"holds": [hold("tandem", 20)]}, {"holds": []}]) == "tandem"


def test_adherence_counts_exercise_days_per_week():
    today = date(2026, 9, 26)  # a Saturday
    logs = [{"date": f"2026-09-{d:02d}T09:00:00", "sets": [{"reps": 8}], "holds": [{"hold_s": 20.0}]}
            for d in (21, 21, 22, 24, 26, 14)]
    a = steadi.adherence(logs, today, weeks=2)
    assert a["weeks"] == [
        {"week_start": "2026-09-14", "days": 1, "sessions": 1, "reps": 8, "hold_s": 20.0},
        {"week_start": "2026-09-21", "days": 4, "sessions": 5, "reps": 40, "hold_s": 100.0},
    ]
    assert a["last_7_days"] == 4 and a["target_days_per_week"] == 5


def test_dashboard_bundles_everything_the_page_shows():
    p = person()
    add(p, metrics(stands=9), 0)
    d = steadi.dashboard(p, date(2026, 9, 26))
    assert set(d) == {"person", "latest", "level", "alert", "trends", "plan", "adherence", "exercise"}
    assert d["trends"]["series"]["chair_stands"] == [9] and d["trends"]["cutoffs"]["chair_stands"] == 11
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/test_steadi.py -q`
Expected: FAIL with `ImportError: cannot import name 'steadi' from 'checkin'`.

- [ ] **Step 3: Write** `src/checkin/steadi.py`

```python
"""STEADI screening logic: cutoffs, flags, fall-risk level, change from baseline, exercise plan, adherence.

Wording rule (docs/COMPETITION.md Section 4): "flags increased fall risk", "change from baseline".
Never "diagnose", "predict", or "prevent" in anything shown to people.
"""

from datetime import date, timedelta
from statistics import mean

TUG_CUTOFF_S = 12.0  # STEADI: 12 s or more flags
TANDEM_CUTOFF_S = 10.0  # STEADI: tandem stance held under 10 s flags
STANCES = ("feet_together", "semi_tandem", "tandem")
STANCE_LABEL = {"feet_together": "feet together", "semi_tandem": "semi-tandem", "tandem": "tandem"}

# STEADI 30-second chair stand: below these counts is below average. (lowest age in band, cutoff)
CHAIR_NORMS = {
    "male": [(60, 14), (65, 12), (70, 12), (75, 11), (80, 10), (85, 8), (90, 7)],
    "female": [(60, 12), (65, 11), (70, 10), (75, 10), (80, 9), (85, 8), (90, 4)],
}
SEX_WORD = {"male": "men", "female": "women"}

# Our change-from-baseline rule (not STEADI's): worse than the rolling baseline by this much,
# two check-ins in a row, counts as a sustained decline.
BASELINE_N = 4  # rolling baseline = mean of up to this many previous check-ins
BASELINE_MIN = 2  # need at least this many to compare
TRACKED = {  # metric: (label, unit, worse direction, threshold, threshold is relative?)
    "tug_s": ("Timed Up and Go", "s", +1, 0.10, True),
    "dual_task_cost_pct": ("Dual-task cost", "%", +1, 10.0, False),
    "chair_stands": ("Chair stands", "", -1, 2.0, False),
    "tandem_s": ("Tandem stance", "s", -1, 3.0, False),
}
KEY_QUESTIONS = {
    "fallen": "fallen in the past year",
    "unsteady": "feels unsteady when standing or walking",
    "worried": "worries about falling",
}
EXERCISE_REPS = 8
CHAIR_LOW_MARGIN = 2  # chair stands under the STEADI line + this count as "low" for the plan
EXERCISE_HOLD_S = 20.0
TARGET_DAYS_PER_WEEK = 5  # "exercises most days"


def chair_norm(age, sex):
    """(cutoff, label): fewer stands than cutoff is below average for age and sex."""
    bands = CHAIR_NORMS[sex]
    lo, cutoff = bands[0]
    for band_lo, band_cut in bands:
        if age >= band_lo:
            lo, cutoff = band_lo, band_cut
    label = f"{SEX_WORD[sex]} {lo}–{lo + 4}"
    if age < 60:
        label += " (the youngest STEADI group)"
    elif age > 94:
        label += " (the oldest STEADI group)"
    return cutoff, label


def metrics_from_steps(steps):
    """Flatten step results (keyed by step id) into the tracked metrics."""
    tug = (steps.get("tug") or {}).get("tug_s")
    dual = (steps.get("dual_tug") or {}).get("tug_s")
    m = {
        "tug_s": tug,
        "dual_tug_s": dual,
        "dual_task_cost_pct": round((dual - tug) / tug * 100, 1) if tug and dual else None,
        "chair_stands": (steps.get("chair_stand") or {}).get("stands"),
    }
    failed = False  # STEADI stops at the first stance that breaks; later stances count as 0 s
    for s in STANCES:
        b = steps.get(f"balance_{s}")
        if b:
            m[f"{s}_s"], m[f"{s}_sway"] = b.get("hold_s"), b.get("sway")
            failed = b.get("hold_s") is not None and b["hold_s"] < TANDEM_CUTOFF_S
        else:
            m[f"{s}_s"], m[f"{s}_sway"] = (0.0 if failed else None), None
    return m


def flags_for(profile, m):
    """STEADI flags: a 'yes' to any key question, or a test past its cutoff."""
    flags = []
    yes = [text for key, text in KEY_QUESTIONS.items() if profile.get(key)]
    if yes:
        flags.append({"id": "key_questions", "text": "Answered yes: " + "; ".join(yes)})
    if m.get("tug_s") is not None and m["tug_s"] >= TUG_CUTOFF_S:
        flags.append({"id": "tug", "text": f"Timed Up and Go took {m['tug_s']:.1f} s (STEADI flags 12 s or more)"})
    if m.get("chair_stands") is not None and profile.get("age") and profile.get("sex"):
        cutoff, label = chair_norm(profile["age"], profile["sex"])
        if m["chair_stands"] < cutoff:
            flags.append(
                {
                    "id": "chair_stand",
                    "text": f"{m['chair_stands']} chair stands in 30 s, below the STEADI average of {cutoff} "
                    f"for {label}",
                }
            )
    if m.get("tandem_s") is not None and m["tandem_s"] < TANDEM_CUTOFF_S:
        flags.append(
            {"id": "balance", "text": f"Held the tandem stance {m['tandem_s']:.1f} s (STEADI flags under 10 s)"}
        )
    return flags


def changes_for(m, history):
    """Change from the rolling baseline for each tracked metric (None until there's enough history)."""
    out = {}
    for key, (_label, _unit, direction, threshold, relative) in TRACKED.items():
        past = [c["metrics"].get(key) for c in history]
        past = [v for v in past if v is not None][-BASELINE_N:]
        if m.get(key) is None or len(past) < BASELINE_MIN:
            out[key] = None
            continue
        base = mean(past)
        change = m[key] - base
        limit = threshold * base if relative else threshold
        out[key] = {"baseline": round(base, 2), "change": round(change, 2), "worse": change * direction >= limit}
    return out


def declines_for(changes, history):
    """Sustained decline: worse than baseline in this check-in and the one before."""
    prev = history[-1].get("changes", {}) if history else {}
    out = []
    for key, ch in changes.items():
        before = prev.get(key)
        if ch and ch["worse"] and before and before["worse"]:
            label, unit, *_ = TRACKED[key]
            out.append(
                {
                    "id": key,
                    "text": f"{label} worse than the baseline two check-ins in a row "
                    f"({ch['baseline']:g}{unit} baseline, change {ch['change']:+g}{unit})",
                }
            )
    return out


def level_for(flags, declines):
    """Our summary (not STEADI's): green = no flags; amber = 1 flag or a sustained decline; red = 2+ flags."""
    if len(flags) >= 2:
        return "red"
    if flags or declines:
        return "amber"
    return "green"


def alert_for(name, level, flags, declines):
    if level == "green":
        return None
    advice = (
        "Talk to a doctor about fall risk soon, and keep up the exercises most days."
        if level == "red"
        else "Mention these results at the next doctor's visit, and keep up the exercises most days."
    )
    return {
        "level": level,
        "title": f"{name}: this check-in flags increased fall risk",
        "items": [f["text"] for f in flags] + [d["text"] for d in declines],
        "advice": advice,
        "note": "Fall-risk screening with the CDC's STEADI tests. A doctor can do a full fall-risk assessment.",
    }


def evaluate(person, metrics, when):
    """Build a check-in record from its metrics and the person's earlier check-ins."""
    profile, history = person["profile"], person["checkins"]
    flags = flags_for(profile, metrics)
    changes = changes_for(metrics, history)
    declines = declines_for(changes, history)
    level = level_for(flags, declines)
    cutoffs = {"tug_s": TUG_CUTOFF_S, "tandem_s": TANDEM_CUTOFF_S}
    if profile.get("age") and profile.get("sex"):
        cutoffs["chair_stands"], cutoffs["chair_label"] = chair_norm(profile["age"], profile["sex"])
    return {
        "date": when.isoformat(timespec="seconds"),
        "key_questions": {k: bool(profile.get(k)) for k in KEY_QUESTIONS},
        "metrics": metrics,
        "cutoffs": cutoffs,
        "flags": flags,
        "changes": changes,
        "declines": declines,
        "level": level,
        "alert": alert_for(person["name"], level, flags, declines),
    }


def next_stance(logs):
    """Supported-balance progression: move up a stance once every hold at the current one hits its target."""
    for log in reversed(logs):
        holds = log.get("holds") or []
        if holds:
            stance = holds[0]["stance"]
            if all(h["hold_s"] >= h["target_s"] for h in holds):
                return STANCES[min(STANCES.index(stance) + 1, len(STANCES) - 1)]
            return stance
    return STANCES[0]


def make_plan(person):
    """Exercise plan leaning on the weakest area (Section 5): a low chair-stand score adds sit-to-stands,
    a balance flag adds holds."""
    latest = person["checkins"][-1] if person["checkins"] else None
    chair_low = balance_flag = False
    why = "no check-in yet: the standard plan"
    if latest:
        m, cut = latest["metrics"], latest["cutoffs"].get("chair_stands")
        chair_low = cut is not None and m.get("chair_stands") is not None and m["chair_stands"] < cut + CHAIR_LOW_MARGIN
        balance_flag = "balance" in {f["id"] for f in latest["flags"]}
        why = "; ".join(
            [text for on, text in [(chair_low, "more sit-to-stands: chair stands are at or near the STEADI line"),
                                   (balance_flag, "more balance holds: the tandem stance was under 10 s")] if on]
        ) or "no weak area in the latest check-in: the standard plan"
    return {
        "sit_to_stand": {"sets": 3 if chair_low else 2, "reps": EXERCISE_REPS},
        "balance": {"stance": next_stance(person["exercise"]), "holds": 4 if balance_flag else 2,
                    "target_s": EXERCISE_HOLD_S},
        "why": why,
    }


def adherence(logs, today, weeks=8):
    """Exercise days per week (Monday start) for the last `weeks` weeks, oldest first."""
    monday = today - timedelta(days=today.weekday())
    out = []
    for i in range(weeks - 1, -1, -1):
        start = monday - timedelta(weeks=i)
        week = [lg for lg in logs if start <= date.fromisoformat(lg["date"][:10]) < start + timedelta(days=7)]
        out.append(
            {
                "week_start": start.isoformat(),
                "days": len({lg["date"][:10] for lg in week}),
                "sessions": len(week),
                "reps": sum(s["reps"] for lg in week for s in lg["sets"]),
                "hold_s": round(sum(h["hold_s"] for lg in week for h in lg["holds"]), 1),
            }
        )
    recent = {lg["date"][:10] for lg in logs if (today - date.fromisoformat(lg["date"][:10])).days < 7}
    return {"target_days_per_week": TARGET_DAYS_PER_WEEK, "weeks": out, "last_7_days": len(recent)}


def trends(person):
    """Per-metric series for charts, with the STEADI cutoff where one exists."""
    cs = person["checkins"]
    series = {k: [c["metrics"].get(k) for c in cs] for k in TRACKED}
    latest_cut = cs[-1]["cutoffs"] if cs else {}
    return {
        "dates": [c["date"][:10] for c in cs],
        "levels": [c["level"] for c in cs],
        "series": series,
        "cutoffs": {k: latest_cut.get(k) for k in ("tug_s", "chair_stands", "tandem_s")},
    }


def dashboard(person, today):
    """Everything the family dashboard shows for one person."""
    latest = person["checkins"][-1] if person["checkins"] else None
    return {
        "person": {k: person[k] for k in ("id", "name", "simulated", "profile")},
        "latest": latest,
        "level": latest["level"] if latest else None,
        "alert": latest["alert"] if latest else None,
        "trends": trends(person),
        "plan": make_plan(person),
        "adherence": adherence(person["exercise"], today),
        "exercise": person["exercise"][-10:],
    }
```

- [ ] **Step 4: Run the tests and lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: `87 passed`, then `All checks passed!`

- [ ] **Step 5: Commit**

Tick task 3 in `TASKS.md`, then:

```bash
git add src/checkin/steadi.py tests/test_steadi.py TASKS.md
git commit -m "feat: STEADI flags, level, baseline, exercise plan, adherence"
```

---

### Task 4: People store and recordings

**Files:**
- Create: `src/checkin/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Store(root)` with:
    - `.people() -> [{"id", "name", "simulated"}]`, sorted by name then id
    - `.get(pid) -> person`; raises `KeyError`, including for any id that isn't `[a-z0-9-]`
    - `.save(person)` (atomic), `.create(name, profile, simulated=False, pid=None) -> person`, `.recording_path(session_id) -> Path`
  - `write_recording(path, data (n,7), tags [(step_id, t_go, t_end)], source, simulated)`
  - `read_recording(path) -> Recording(data, steps {step_id: (t_go, t_end)}, simulated)`
- Recording format:
  - Header: `# source=<kind> simulated=<0|1>`, then one `# step <id> <t_go> <t_end>` line per step, holding the exact "Go" and end times.
  - Columns: `t,ax,ay,az,gx,gy,gz,step`.

- [ ] **Step 1: Write the failing test** `tests/test_store.py`

```python
import numpy as np
import pytest

from checkin import sim
from checkin.store import Store, read_recording, write_recording


def test_people_round_trip_with_unique_ids(tmp_path):
    store = Store(tmp_path)
    a = store.create("Ana María", {"age": 70})
    b = store.create("Ana María", {"age": 71})
    assert (a["id"], b["id"]) == ("ana-mar-a", "ana-mar-a-2")
    a["checkins"].append({"level": "green"})
    store.save(a)
    assert store.get(a["id"])["checkins"] == [{"level": "green"}]
    assert [p["id"] for p in store.people()] == ["ana-mar-a", "ana-mar-a-2"]


@pytest.mark.parametrize("bad", ["../secrets", "a/b", "", "UPPER", "x" * 80])
def test_ids_cannot_escape_the_data_folder(tmp_path, bad):
    with pytest.raises(KeyError):
        Store(tmp_path).get(bad)


def test_recording_round_trip_keeps_step_windows(tmp_path):
    t, acc, gyro, _ = sim.simulate("tug", seed=1)
    data = np.column_stack([t, acc, gyro])
    path = tmp_path / "r.csv"
    write_recording(path, data, [("tug", 0.0037, 9.0)], "sim", True)
    rec = read_recording(path)
    assert rec.simulated and rec.steps == {"tug": (0.004, 9.0)}  # exact "Go", not the next sample
    assert np.allclose(rec.data, data, atol=1e-3)


def test_a_csv_without_our_columns_is_rejected(tmp_path):
    path = tmp_path / "phone.csv"
    path.write_text("Time (s),Acceleration x (m/s^2)\n0,1\n")
    with pytest.raises(ValueError, match="expected columns"):
        read_recording(path)
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/test_store.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'checkin.store'`.

- [ ] **Step 3: Write** `src/checkin/store.py`

```python
"""People (profile, check-ins, exercise logs) as JSON files, and raw recordings as CSV."""

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

ID_RE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
COLUMNS = ["t", "ax", "ay", "az", "gx", "gy", "gz", "step"]


class Store:
    def __init__(self, root):
        self.root = Path(root)
        (self.root / "people").mkdir(parents=True, exist_ok=True)
        (self.root / "recordings").mkdir(parents=True, exist_ok=True)

    def _path(self, pid):
        if not ID_RE.fullmatch(pid or ""):
            raise KeyError(pid)
        return self.root / "people" / f"{pid}.json"

    def people(self):
        docs = [json.loads(p.read_text()) for p in (self.root / "people").glob("*.json")]
        out = [{"id": d["id"], "name": d["name"], "simulated": d["simulated"]} for d in docs]
        return sorted(out, key=lambda p: (p["name"].lower(), p["id"]))

    def get(self, pid):
        path = self._path(pid)
        if not path.exists():
            raise KeyError(pid)
        return json.loads(path.read_text())

    def save(self, person):
        path = self._path(person["id"])
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(person, indent=1))
        tmp.replace(path)  # atomic: a crash mid-write never leaves half a file

    def create(self, name, profile, simulated=False, pid=None):
        base = pid or re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:50] or "person"
        pid, n = base, 1
        while self._path(pid).exists():
            n += 1
            pid = f"{base}-{n}"
        person = {"id": pid, "name": name, "simulated": simulated, "profile": profile, "checkins": [],
                  "exercise": []}
        self.save(person)
        return person

    def recording_path(self, session_id):
        return self.root / "recordings" / f"{session_id}.csv"


@dataclass
class Recording:
    data: np.ndarray  # (n, 7): t, ax, ay, az (g), gx, gy, gz (deg/s)
    steps: dict  # step id -> (t_go, t_end)
    simulated: bool


def write_recording(path, data, tags, source, simulated):
    """`tags`: list of (step id, t_go, t_end). The header keeps each step's exact "Go" and end times;
    the `step` column marks the same windows for anyone plotting the file."""
    path = Path(path)
    with path.open("w", newline="") as f:
        f.write(f"# source={source} simulated={int(simulated)}\n")
        for sid, a, b in tags:
            f.write(f"# step {sid} {a:.3f} {b:.3f}\n")
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for row in data:
            step = next((sid for sid, a, b in tags if a <= row[0] <= b), "")
            w.writerow([f"{row[0]:.3f}", *(f"{v:.4f}" for v in row[1:7]), step])


def read_recording(path):
    lines = Path(path).read_text().splitlines()
    head = [ln[1:].split() for ln in lines if ln.startswith("#")]
    simulated = any("simulated=1" in parts for parts in head)
    steps = {p[1]: (float(p[2]), float(p[3])) for p in head if len(p) == 4 and p[0] == "step"}
    rows = list(csv.DictReader(ln for ln in lines if not ln.startswith("#")))
    if not rows or set(COLUMNS[:7]) - set(rows[0]):
        raise ValueError(f"{path}: expected columns {','.join(COLUMNS)}")
    data = np.array([[float(r[c]) for c in COLUMNS[:7]] for r in rows])
    return Recording(data, steps, simulated)
```

- [ ] **Step 4: Run the tests and lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: `95 passed`, then `All checks passed!`

- [ ] **Step 5: Commit**

Tick task 4 in `TASKS.md`, then:

```bash
git add src/checkin/store.py tests/test_store.py TASKS.md
git commit -m "feat: JSON people store and tagged CSV recordings"
```

---

### Task 5: Clock and motion sources

**Files:**
- Create: `src/checkin/clock.py`, `src/checkin/sources.py`, `firmware/phyphox/belt-imu.phyphox`
- Test: `tests/test_sources.py`

**Interfaces:**
- Consumes: `sim` (`SimParams`, `Device`, `render`, `idle`, `FS`, `G`, `SIT_PITCH`), `store.read_recording`.
- Produces:
  - `clock.Clock` (`now()` = `time.monotonic()`, async `sleep(s)`) and `clock.FakeClock(t=1000.0)` (public `.t`; `sleep` advances instantly).
  - The motion source interface, which every source implements:
    - `read() -> (n,7) array` of `t` (host clock), `ax ay az` (g), `gx gy gz` (deg/s), holding only samples new since the last call
    - `act(kind, **kw)`: the simulator and CSV replay act out a step from now; hardware sources ignore it
    - `close()`, `kind: str`, `simulated: bool`
  - Sources:
    - `SimSource(clock, params=None, seed=0)`, whose `.truth[kind]` holds each activity's true scores
    - `CsvSource(clock, path)`, where each `act(kind)` jumps to the next unplayed recorded step of that kind
    - `UdpSource(clock, port, host="0.0.0.0")` with `.sock`, `.dropped`
    - `PhyphoxSource(clock, url, fetch=..., poll_s=0.1, start_thread=True)` with `.poll()`, `.error`
  - `open_source(spec, clock, udp_port=4210, seed=0)`, where `spec` is `sim`, `csv:<file>`, `udp`, or `phyphox:<url>`. Also `EMPTY`.

Device clocks are mapped to the host clock per packet: the smallest (arrival − newest sample time) seen is the offset, reset if the device restarts. Mapping per sample would collapse a packet's samples onto its arrival time; `test_udp_source_parses_lines_counts_drops_and_maps_the_clock` pins this. The phyphox `/get?var=threshold|reference` syntax and response shape follow phyphox's remote-interface docs (https://phyphox.org/docs/remote-interface/).

- [ ] **Step 1: Write the failing test** `tests/test_sources.py`

```python
import socket

import numpy as np
import pytest

from checkin import sim
from checkin.clock import FakeClock
from checkin.signals import tug_end
from checkin.sources import CsvSource, PhyphoxSource, SimSource, UdpSource, open_source
from checkin.store import write_recording


def test_sim_source_streams_100_hz_and_acts_on_cue():
    clock = FakeClock()
    src = SimSource(clock, seed=1)
    clock.t += 2.0
    before = src.read()
    assert len(before) == 200 and np.allclose(np.diff(before[:, 0]), 0.01)
    t_go = clock.t
    src.act("tug")
    clock.t += 20.0
    d = np.vstack([before, src.read()])
    assert np.all(np.diff(d[:, 0]) > 0)
    end = tug_end(d[:, 0], d[:, 1:4], d[:, 4:7], t_go)
    assert abs(end - t_go - src.truth["tug"]["tug_s"]) < 0.5


def test_csv_source_replays_each_step_when_cued(tmp_path):
    t, acc, gyro, truth = sim.simulate("tug", seed=2)
    path = tmp_path / "rec.csv"
    write_recording(path, np.column_stack([t + 50.0, acc, gyro]), [("tug", 50.0, 50.0 + t[-1])], "sim", True)
    clock = FakeClock()
    src = CsvSource(clock, path)
    assert src.simulated
    clock.t += 1.0
    idle = src.read()
    t_go = clock.t
    src.act("tug")
    clock.t += 20.0
    d = np.vstack([idle, src.read()])
    assert abs(tug_end(d[:, 0], d[:, 1:4], d[:, 4:7], t_go) - t_go - truth["tug_s"]) < 0.5
    src.act("tug")  # nothing left to play: holds still instead of crashing
    clock.t += 1.0
    assert len(src.read()) == 100


def test_udp_source_parses_lines_counts_drops_and_maps_the_clock():
    clock = FakeClock(t=500.0)
    src = UdpSource(clock, port=0, host="127.0.0.1")
    port = src.sock.getsockname()[1]
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tx.sendto(b"1,1000,0.0,0.0,1.0,0.5,0.0,0.0\n2,1010,0.0,0.0,1.01,0.5,0.0,0.0\n", ("127.0.0.1", port))
    tx.sendto(b"garbage\n5,1040,0.1,0.0,1.0,0.5,0.0,0.0\n", ("127.0.0.1", port))
    rows = np.empty((0, 7))
    for _ in range(100):
        rows = np.vstack([rows, src.read()])
        if len(rows) == 3:
            break
    tx.close()
    src.close()
    assert len(rows) == 3 and src.dropped == 2
    assert rows[:, 0] == pytest.approx([499.96, 499.97, 500.0])  # spacing kept; newest sample = arrival
    assert rows[1, 3] == pytest.approx(1.01)


def phyphox_reply(t0, n, gyro=True):
    t = [t0 + i * 0.01 for i in range(1, n + 1)]
    buf = {"acc_time": t, "accX": [0.0] * n, "accY": [0.0] * n, "accZ": [9.81] * n}
    if gyro:
        buf |= {"gyr_time": t, "gyrX": [0.1] * n, "gyrY": [0.0] * n, "gyrZ": [0.0] * n}
    return {"buffer": {k: {"size": 0, "updateMode": "partial", "buffer": v} for k, v in buf.items()},
            "status": {"measuring": True}}


def test_phyphox_source_converts_units_and_asks_only_for_new_data():
    urls = []
    replies = [phyphox_reply(0.0, 5), phyphox_reply(0.05, 3)]
    clock = FakeClock()
    src = PhyphoxSource(clock, "http://phone:8080/", fetch=lambda u: urls.append(u) or replies.pop(0),
                        start_thread=False)
    src.poll()
    src.poll()
    rows = src.read()
    assert len(rows) == 8 and rows[0, 3] == pytest.approx(1.0) and rows[0, 4] == pytest.approx(5.7296, abs=1e-3)
    assert urls[0].startswith("http://phone:8080/get?accX=0.0|acc_time") and "acc_time=0.05" in urls[1]


def test_phyphox_accelerometer_only_experiment_gives_zero_gyro():
    src = PhyphoxSource(FakeClock(), "http://phone:8080", fetch=lambda u: phyphox_reply(0.0, 4, gyro=False),
                        start_thread=False)
    src.poll()
    assert np.all(src.read()[:, 4:7] == 0.0)


@pytest.mark.parametrize("spec", ["bluetooth", "phyphox"])
def test_open_source_rejects_bad_specs(spec):
    with pytest.raises(ValueError):
        open_source(spec, FakeClock())
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/test_sources.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'checkin.clock'`.

- [ ] **Step 3: Write** `src/checkin/clock.py`

```python
"""The controller and every motion source share one clock, so "Go" and sample times line up."""

import asyncio
import time


class Clock:
    def now(self):
        return time.monotonic()

    async def sleep(self, s):
        await asyncio.sleep(s)


class FakeClock:
    """Test clock: sleep() advances time instantly, so a 3-minute check-in runs in a second."""

    def __init__(self, t=1000.0):
        self.t = t

    def now(self):
        return self.t

    async def sleep(self, s):
        self.t += s
        await asyncio.sleep(0)
```

- [ ] **Step 4: Write** `src/checkin/sources.py`

```python
"""Motion sources. Each one has:

    read() -> (n, 7) array of t (host clock, s), ax, ay, az (g), gx, gy, gz (deg/s), new since the last call
    act(kind, **kw) -> None   the simulator and CSV replay act out a step from now; hardware ignores it
    close() -> None
    kind: str, simulated: bool
"""

import json
import queue
import socket
import threading
import urllib.request

import numpy as np

from . import sim
from .store import read_recording

EMPTY = np.empty((0, 7))


class SimSource:
    kind = "sim"
    simulated = True

    def __init__(self, clock, params=None, seed=0):
        self.clock = clock
        self.p = params or sim.SimParams()
        self.rng = np.random.default_rng(seed)
        self.dev = sim.Device(self.p, self.rng)
        self.n = int(clock.now() * sim.FS)  # next sample index on the 100 Hz grid
        self.pitch = sim.SIT_PITCH
        self.script = None  # (first sample index, acc, gyro, pitch after)
        self.truth = {}  # activity kind -> true scores of its latest run

    def act(self, kind, **kw):
        acc, gyro, truth, after = sim.render(kind, self.p, self.rng, **kw)
        start = max(self.n, int(round(self.clock.now() * sim.FS)))
        self.script = (start, acc, gyro, after)
        self.truth[kind] = truth

    def read(self):
        end = int(self.clock.now() * sim.FS)
        if end <= self.n:
            return EMPTY
        idx = np.arange(self.n, end)
        self.n = end
        acc, gyro = sim.idle(len(idx), self.pitch)
        if self.script:
            start, sa, sg, after = self.script
            k = idx - start
            inside = (k >= 0) & (k < len(sa))
            acc[inside], gyro[inside] = sa[k[inside]], sg[k[inside]]
            past = k >= len(sa)
            if past.any():
                acc[past], gyro[past] = sim.idle(int(past.sum()), after)
                self.pitch, self.script = after, None
        acc, gyro = self.dev(acc, gyro)
        return np.column_stack([idx / sim.FS, acc, gyro])

    def close(self):
        pass


class CsvSource:
    """Replays a recording in real time. Each act() jumps to the next recorded run of that step."""

    kind = "csv"

    def __init__(self, clock, path):
        self.clock = clock
        rec = read_recording(path)
        self.data, self.simulated = rec.data, rec.simulated
        self.starts = sorted((t_go, sid) for sid, (t_go, _) in rec.steps.items())
        self.played = set()
        self.n = int(clock.now() * sim.FS)
        self.pos = 0  # recording row shown when not playing
        self.play = None  # (host sample index at the jump, recording row at the jump)

    def act(self, kind, **kw):
        for t_go, sid in self.starts:
            if sid.split("#")[0] == kind and sid not in self.played:
                self.played.add(sid)
                row = int(np.searchsorted(self.data[:, 0], t_go))
                self.play = (max(self.n, int(round(self.clock.now() * sim.FS))), row)
                return
        print(f"csv source: no unplayed {kind!r} step left in the recording; holding still")

    def read(self):
        end = int(self.clock.now() * sim.FS)
        if end <= self.n:
            return EMPTY
        idx = np.arange(self.n, end)
        self.n = end
        rows = np.full(len(idx), self.pos)
        if self.play:
            k0, r0 = self.play
            live = idx >= k0
            rows[live] = np.minimum(r0 + (idx[live] - k0), len(self.data) - 1)
        self.pos = int(rows[-1])
        return np.column_stack([idx / sim.FS, self.data[rows, 1:7]])

    def close(self):
        pass


class _ClockMap:
    """Maps a device clock to the host clock. Each packet's newest sample was taken just before it
    arrived, so the smallest (arrival - newest sample time) seen so far is the best offset."""

    def __init__(self):
        self.offset = None
        self.last = None

    def update(self, newest_device_t, arrived_host_t):
        if self.last is not None and newest_device_t < self.last - 1.0:
            self.offset = None  # the device restarted
        self.last = newest_device_t
        off = arrived_host_t - newest_device_t
        self.offset = off if self.offset is None else min(self.offset, off)

    def __call__(self, device_t):
        return device_t + self.offset


class UdpSource:
    """ESP32 belt: text datagrams of `seq,ms,ax,ay,az,gx,gy,gz` lines (firmware/PROTOCOL.md)."""

    kind = "udp"
    simulated = False

    def __init__(self, clock, port, host="0.0.0.0"):
        self.clock = clock
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((host, port))
        self.sock.setblocking(False)
        self.map = _ClockMap()
        self.last_seq = None
        self.dropped = 0

    def act(self, kind, **kw):
        pass

    def read(self):
        rows = []
        while True:
            try:
                data, _ = self.sock.recvfrom(65535)
            except (BlockingIOError, InterruptedError):
                break
            packet = []
            for line in data.decode("ascii", "ignore").splitlines():
                parts = line.strip().split(",")
                if len(parts) != 8:
                    continue
                try:
                    seq, ms = int(parts[0]), int(parts[1])
                    packet.append([ms / 1000.0, *(float(v) for v in parts[2:])])
                except ValueError:
                    continue
                if self.last_seq is not None and seq > self.last_seq + 1:
                    self.dropped += seq - self.last_seq - 1
                self.last_seq = seq
            if packet:
                self.map.update(packet[-1][0], self.clock.now())
                rows += packet
        if not rows:
            return EMPTY
        rows = np.array(rows)
        rows[:, 0] = self.map(rows[:, 0])
        return rows

    def close(self):
        self.sock.close()


def _get_json(url, timeout=1.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


class PhyphoxSource:
    """Phone running phyphox with remote access on (firmware/phyphox/belt-imu.phyphox, or the built-in
    "Acceleration with g" experiment for accelerometer only). Polls /get in a background thread."""

    kind = "phyphox"
    simulated = False
    BUFFERS = ("accX", "accY", "accZ", "acc_time", "gyrX", "gyrY", "gyrZ", "gyr_time")

    def __init__(self, clock, url, fetch=_get_json, poll_s=0.1, start_thread=True):
        self.clock = clock
        self.url = url.rstrip("/")
        self.fetch = fetch
        self.poll_s = poll_s
        self.map = _ClockMap()
        self.last_acc = self.last_gyr = 0.0
        self.q = queue.SimpleQueue()
        self.error = None
        self._stop = threading.Event()
        if start_thread:
            try:
                self.fetch(self.url + "/control?cmd=start")
            except OSError as e:
                self.error = str(e)
            threading.Thread(target=self._loop, daemon=True).start()

    def act(self, kind, **kw):
        pass

    def _loop(self):
        while not self._stop.wait(self.poll_s):
            try:
                self.poll()
                self.error = None
            except (OSError, ValueError, KeyError) as e:
                self.error = str(e)

    def poll(self):
        a, g = self.last_acc, self.last_gyr
        q = "&".join(
            [f"acc{c}={a!r}|acc_time" for c in "XYZ"]
            + [f"acc_time={a!r}"]
            + [f"gyr{c}={g!r}|gyr_time" for c in "XYZ"]
            + [f"gyr_time={g!r}"]
        )
        buf = self.fetch(f"{self.url}/get?{q}")["buffer"]
        get = lambda k: np.array(buf.get(k, {}).get("buffer") or [], dtype=float)  # noqa: E731
        at = get("acc_time")
        if len(at) == 0:
            return
        acc = np.column_stack([get(f"acc{c}")[: len(at)] for c in "XYZ"]) / sim.G
        gt = get("gyr_time")
        if len(gt):
            gyro = np.column_stack([np.interp(at, gt, get(f"gyr{c}")[: len(gt)]) for c in "XYZ"])
            gyro = np.degrees(gyro)
            self.last_gyr = float(gt[-1])
        else:
            gyro = np.zeros_like(acc)  # accelerometer-only experiment
        self.last_acc = float(at[-1])
        self.map.update(self.last_acc, self.clock.now())
        rows = np.column_stack([self.map(at), acc, gyro])
        self.q.put(rows[np.isfinite(rows).all(axis=1)])

    def read(self):
        parts = []
        while not self.q.empty():
            parts.append(self.q.get())
        return np.vstack(parts) if parts else EMPTY

    def close(self):
        self._stop.set()


def open_source(spec, clock, udp_port=4210, seed=0):
    """`sim`, `csv:<file>`, `udp`, or `phyphox:<http://phone-ip:8080>`."""
    kind, _, arg = spec.partition(":")
    if kind == "sim":
        return SimSource(clock, seed=seed)
    if kind == "csv":
        return CsvSource(clock, arg)
    if kind == "udp":
        return UdpSource(clock, udp_port)
    if kind == "phyphox" and arg:
        return PhyphoxSource(clock, arg)
    if kind == "phyphox":
        raise ValueError("phyphox needs the address phyphox shows under Remote access, e.g. phyphox:http://192.168.1.23:8080")
    raise ValueError(f"unknown source {spec!r}: use sim, csv:<file>, udp, or phyphox:<url>")
```

- [ ] **Step 5: Write** `firmware/phyphox/belt-imu.phyphox`

Buffer names match phyphox's built-in experiments, so the built-in "Acceleration with g" experiment also works, without the gyroscope.

```xml
<phyphox version="1.7" locale="en">
    <title>Belt IMU</title>
    <category>Fall-risk check-in</category>
    <description>Accelerometer (with gravity) and gyroscope at 100 Hz for the check-in laptop. Turn on Remote access, then run: checkin serve --source phyphox:http://PHONE-IP:8080</description>
    <data-containers>
        <container size="0">acc_time</container>
        <container size="0">accX</container>
        <container size="0">accY</container>
        <container size="0">accZ</container>
        <container size="0">gyr_time</container>
        <container size="0">gyrX</container>
        <container size="0">gyrY</container>
        <container size="0">gyrZ</container>
    </data-containers>
    <input>
        <sensor type="accelerometer" rate="100">
            <output component="x">accX</output>
            <output component="y">accY</output>
            <output component="z">accZ</output>
            <output component="t">acc_time</output>
        </sensor>
        <sensor type="gyroscope" rate="100">
            <output component="x">gyrX</output>
            <output component="y">gyrY</output>
            <output component="z">gyrZ</output>
            <output component="t">gyr_time</output>
        </sensor>
    </input>
    <views>
        <view label="Belt">
            <graph label="Acceleration" labelX="t" unitX="s" labelY="a" unitY="m/s²" partialUpdate="true">
                <input axis="x">acc_time</input>
                <input axis="y">accZ</input>
            </graph>
            <graph label="Gyroscope" labelX="t" unitX="s" labelY="ω" unitY="rad/s" partialUpdate="true">
                <input axis="x">gyr_time</input>
                <input axis="y">gyrZ</input>
            </graph>
        </view>
    </views>
    <export>
        <set name="Accelerometer">
            <data name="Time (s)">acc_time</data>
            <data name="Acceleration x (m/s^2)">accX</data>
            <data name="Acceleration y (m/s^2)">accY</data>
            <data name="Acceleration z (m/s^2)">accZ</data>
        </set>
        <set name="Gyroscope">
            <data name="Time (s)">gyr_time</data>
            <data name="Gyroscope x (rad/s)">gyrX</data>
            <data name="Gyroscope y (rad/s)">gyrY</data>
            <data name="Gyroscope z (rad/s)">gyrZ</data>
        </set>
    </export>
</phyphox>
```

Check the XML: `python3 -c "import xml.dom.minidom as m; m.parse('firmware/phyphox/belt-imu.phyphox'); print('ok')"` → `ok`

- [ ] **Step 6: Run the tests and lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: `102 passed`, then `All checks passed!`

- [ ] **Step 7: Commit**

Tick task 5 in `TASKS.md`, then:

```bash
git add src/checkin/clock.py src/checkin/sources.py firmware/phyphox/belt-imu.phyphox tests/test_sources.py TASKS.md
git commit -m "feat: motion sources (simulator, CSV replay, ESP32 UDP, phyphox)"
```

---

### Task 6: Base stations and protocol

**Files:**
- Create: `src/checkin/base.py`, `firmware/PROTOCOL.md`
- Test: `tests/test_base.py`

**Interfaces:**
- Consumes: nothing (pyserial is imported only when a real port is opened).
- Produces:
  - The base station interface: `cue(name)` with `start|stop|done|error|rep`; `led(color)` with `off|blue|green|amber|red`; `pressed() -> bool` (a press since the last call); `close()`; `kind`; `connected`.
  - `VirtualBase` (all no-ops; the dashboard renders the LED and plays tones). `SerialBase(port)`, where `port` is pyserial-like (`write`, `read`, `in_waiting`, `close`). `SerialBase.open(path, baud=115200)`. `open_base(spec, serial_port=None)`.
- `firmware/PROTOCOL.md` is the single source of truth for the serial lines, the UDP line format, and the cue tone table. The firmware (Tasks 12–13) and the dashboard (Task 11) use it.

- [ ] **Step 1: Write the failing test** `tests/test_base.py`

```python
import pytest

from checkin.base import SerialBase, VirtualBase, open_base


class FakePort:
    def __init__(self):
        self.written = b""
        self.incoming = b""
        self.broken = False

    def write(self, data):
        if self.broken:
            raise OSError("device unplugged")
        self.written += data

    @property
    def in_waiting(self):
        if self.broken:
            raise OSError("device unplugged")
        return len(self.incoming)

    def read(self, n):
        data, self.incoming = self.incoming[:n], self.incoming[n:]
        return data

    def close(self):
        pass


def test_serial_base_speaks_the_protocol():
    port = FakePort()
    base = SerialBase(port)
    assert port.written == b"PING\n" and not base.connected
    base.cue("start")
    base.led("amber")
    assert port.written.endswith(b"CUE start\nLED amber\n")
    port.incoming = b"READY\nBT"
    assert base.pressed() is False and base.connected
    port.incoming = b"N\r\n"  # a line split across reads, with a Windows line ending
    assert base.pressed() is True
    assert base.pressed() is False


def test_serial_base_survives_being_unplugged():
    port = FakePort()
    base = SerialBase(port)
    port.incoming = b"PONG\n"
    base.pressed()
    port.broken = True
    base.cue("stop")
    assert base.pressed() is False and not base.connected


def test_open_base():
    assert isinstance(open_base("virtual"), VirtualBase)
    with pytest.raises(ValueError, match="--serial-port"):
        open_base("serial")
    with pytest.raises(ValueError):
        open_base("bluetooth")
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/test_base.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'checkin.base'`.

- [ ] **Step 3: Write** `src/checkin/base.py`

```python
"""Base stations. Each one has:

    cue(name)   start | stop | done | error | rep   (buzzer)
    led(color)  off | blue | green | amber | red
    pressed() -> bool   the physical button was pressed since the last call
    close()
    kind: str, connected: bool

The dashboard always shows the LED and the on-screen button; with the virtual base it also plays the tones.
"""

import logging

log = logging.getLogger(__name__)
CUES = ("start", "stop", "done", "error", "rep")
COLORS = ("off", "blue", "green", "amber", "red")


class VirtualBase:
    kind = "virtual"
    connected = True

    def cue(self, name):
        pass

    def led(self, color):
        pass

    def pressed(self):
        return False

    def close(self):
        pass


class SerialBase:
    """Arduino base station over USB serial, line protocol in firmware/PROTOCOL.md."""

    kind = "serial"

    def __init__(self, port):
        self.port = port  # pyserial-like: write(bytes), read(n), in_waiting
        self.connected = False
        self._buf = b""
        self._send("PING")

    @classmethod
    def open(cls, path, baud=115200):
        import serial  # only needed with real hardware

        return cls(serial.Serial(path, baud, timeout=0, write_timeout=0.5))

    def _send(self, line):
        try:
            self.port.write((line + "\n").encode())
        except Exception as e:  # unplugged mid-session: keep the session running
            if self.connected:
                log.warning("base station write failed: %s", e)
            self.connected = False

    def cue(self, name):
        self._send(f"CUE {name}")

    def led(self, color):
        self._send(f"LED {color}")

    def pressed(self):
        try:
            waiting = self.port.in_waiting
            self._buf += self.port.read(waiting) if waiting else b""
        except Exception as e:
            if self.connected:
                log.warning("base station read failed: %s", e)
            self.connected = False
            return False
        *lines, self._buf = self._buf.split(b"\n")
        pressed = False
        for raw in lines:
            line = raw.strip().decode("ascii", "ignore")
            if line == "BTN":
                pressed = True
            elif line in ("READY", "PONG"):
                self.connected = True
            elif line.startswith("ERR"):
                log.warning("base station: %s", line)
        return pressed

    def close(self):
        try:
            self.port.close()
        except Exception:
            pass


def open_base(spec, serial_port=None):
    if spec == "virtual":
        return VirtualBase()
    if spec == "serial":
        if not serial_port:
            raise ValueError("--base serial needs --serial-port (e.g. /dev/cu.usbmodem1101 or COM3)")
        return SerialBase.open(serial_port)
    raise ValueError(f"unknown base {spec!r}: use virtual or serial")
```

- [ ] **Step 4: Write** `firmware/PROTOCOL.md`

````markdown
# Device protocols

Two links, both plain text so you can watch them with `arduino-cli monitor` or `nc`.

## Base station ↔ laptop (USB serial)

115200 baud, 8N1. One command per line, ending in `\n` (a trailing `\r` is ignored).

**Laptop → base station**

| Line | Effect |
|---|---|
| `PING` | Replies `PONG` (the laptop sends this on connect) |
| `CUE start` | Two rising beeps: this is the "Go" cue; timing starts when it's sent |
| `CUE stop` | One long low beep: the step is over |
| `CUE done` | Three-note rising melody: the session is saved |
| `CUE error` | Three quick low beeps: something went wrong (step timed out, session cancelled) |
| `CUE rep` | One short beep: an exercise rep was counted |
| `LED off` / `LED blue` / `LED green` / `LED amber` / `LED red` | Blue = session in progress; green/amber/red = the fall-risk level of the last check-in |

**Base station → laptop**

| Line | Meaning |
|---|---|
| `READY` | Sent once at boot |
| `PONG` | Reply to `PING` |
| `BTN` | The button was pressed (debounced, sent on press, not release) |
| `ERR <text>` | Unknown command (the laptop logs it) |

**Cue tones** (frequency Hz, duration ms; `0` Hz = silence). The on-screen base station plays the same table.

| Cue | Notes |
|---|---|
| start | 2000/150, 0/80, 3000/150 |
| stop | 1500/600 |
| done | 2093/150, 2637/150, 3136/250 |
| error | 800/100, 0/80, 800/100, 0/80, 800/100 |
| rep | 2500/80 |

Cues block the Arduino for their length (at most 600 ms), so a button press shorter than a cue can be missed. Nothing in the check-in asks for a press during a cue.

## Belt → laptop (UDP)

The ESP32 sends a datagram every 50 ms (5 samples at 100 Hz) to the network's broadcast address, or to one IP if `UDP_TARGET_IP` is set in `firmware/esp32_imu/config.h`. Port: `UDP_PORT` (default 4210), matching `checkin serve --udp-port`.

Each datagram holds one line per sample:

```
seq,ms,ax,ay,az,gx,gy,gz
```

| Field | Meaning |
|---|---|
| `seq` | Sample counter from boot; a gap means lost samples |
| `ms` | ESP32 `millis()` when the sample was taken (newest sample ≈ send time, 10 ms apart) |
| `ax ay az` | Acceleration in g, including gravity (±8 g range) |
| `gx gy gz` | Angular rate in °/s (±500 °/s range) |

Axes are the MPU-6050's own. The laptop's scoring doesn't care how the belt is mounted.

The laptop maps `ms` to its own clock using the smallest (arrival time − newest sample time) seen, and starts over if `ms` jumps backwards (the belt rebooted).

Watch it live: `nc -ul 4210` (macOS/Linux).
````

- [ ] **Step 5: Run the tests and lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: `105 passed`, then `All checks passed!`

- [ ] **Step 6: Commit**

Tick task 6 in `TASKS.md`, then:

```bash
git add src/checkin/base.py firmware/PROTOCOL.md tests/test_base.py TASKS.md
git commit -m "feat: virtual and serial base stations, device protocol doc"
```

---

### Task 7: Session controller

**Files:**
- Create: `src/checkin/controller.py`
- Test: `tests/test_controller.py`

**Interfaces:**
- Consumes: `signals.tug_end`, `signals.stand_times`, `signals.balance_hold`, `signals.score_step`, `signals.CHAIR_STAND_S`; `steadi.evaluate`, `steadi.metrics_from_steps`, `steadi.make_plan`, `steadi.STANCES`, `steadi.STANCE_LABEL`; `store.write_recording`; `clock.Clock`; any motion source (Task 5) and base station (Task 6).
- Produces: `Controller(source, base, store, clock=None, on_event=None)` with:
  - `.state`, the dict documented under `GET /api/state` in `docs/API.md`, and `.busy`
  - `start(person_id, mode, plan=None)`: queues a session; raises `Busy`, `KeyError`, or `ValueError` (a check-in without age and sex)
  - `press()`, `stop("arms_used" | "cancel")`
  - async `run()` (the server's loop), async `tick()`, and async `run_session(person_id, mode, plan=None) -> record | None`
  - `on_event(event)` receives `{"type": "state", ...}`, `{"type": "cue", "name"}`, and `{"type": "saved", "person_id", "mode", "id"}`
  - Also `CHECKIN_STEPS` and `Busy`.
- Step flow:
  - Every step: wait for a press → `cue("start")` = "Go" → `source.act(...)` → re-run detection on the growing window every 0.25 s → `cue("stop")` → tag `(step_id, t_go, t_end)`.
  - The chair stand runs to Go + 32 s (stop cue at 30 s).
  - Balance stops at the first stance under 10 s.
  - The saved record is `steadi.evaluate(...)` plus `id`, `source`, `simulated`, `recording`, `steps`.

This is the Done-criteria test: `test_full_simulated_checkin_matches_the_simulator` checks TUG within 0.5 s, dual-task cost within 3 points of the configured 25%, an exact chair-stand count, and holds within 1 s. `test_exercise_session_counts_reps_and_times_holds` checks the rep count matches and there's one beep per rep. `drive()` presses the on-screen button whenever a step waits, the way a helper would.

- [ ] **Step 1: Write the failing test** `tests/test_controller.py`

```python
import asyncio

from checkin import sim
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
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/test_controller.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'checkin.controller'`.

- [ ] **Step 3: Write** `src/checkin/controller.py`

```python
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
        """'arms_used' during the chair stand records 0 (STEADI); 'cancel' ends the session without saving."""
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
        pressed, self._pressed = self._pressed, False
        return pressed

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
                    result, cue = signals.score_step(sid, *self._window(t_go), t_go, now), "stop"
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
            result = {**signals.score_step(sid, *self._window(t_go), t_go, now), "arms_used": False}
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
        result = signals.score_step(sid, *self._window(t_go), t_go, t_end)
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
        result = {**signals.score_step(sid, *self._window(t_go), t_go, now), "target": reps}
        self._end(sid, t_go, now, result)
        return result
```

- [ ] **Step 4: Run the tests and lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: `115 passed` (about 1.5 s: the FakeClock runs each 3-minute check-in instantly), then `All checks passed!`

- [ ] **Step 5: Commit**

Tick task 7 in `TASKS.md`, then:

```bash
git add src/checkin/controller.py tests/test_controller.py TASKS.md
git commit -m "feat: session controller for the check-in and exercise mode"
```

---

### Task 8: Simulated: Dad history

**Files:**
- Create: `src/checkin/seed.py`
- Test: `tests/test_seed.py`

**Interfaces:**
- Consumes: `steadi.evaluate`, `steadi.metrics_from_steps`, `steadi.make_plan`; `Store.save`.
- Produces: `DAD_ID = "sim-dad"`, `seed_dad(store, today: date) -> person` (overwrites; the last check-in is `today`).

The story is age 78, male, so the STEADI line is 11 stands:
- Chair stands go 13 → 12 → 11 → 10 (amber) → 10 (amber) → 11 → 12 → 13.
- Before the flag, exercise happens once a week (a pamphlet). After it, most days, following the plan, which adds sit-to-stand sets while chair stands are low.
- Every record is `"simulated": true` and the name is "Simulated: Dad".

- [ ] **Step 1: Write the failing test** `tests/test_seed.py`

```python
from datetime import date

from checkin.seed import seed_dad
from checkin.store import Store


def test_simulated_dad_tells_the_story(tmp_path):
    today = date(2026, 9, 26)
    dad = seed_dad(Store(tmp_path), today)
    assert dad["name"] == "Simulated: Dad" and dad["simulated"]
    levels = [c["level"] for c in dad["checkins"]]
    assert levels == ["green", "green", "green", "amber", "amber", "green", "green", "green"]
    assert [f["id"] for f in dad["checkins"][3]["flags"]] == ["chair_stand"]
    assert dad["checkins"][-1]["date"].startswith("2026-09-26")
    assert all(c["simulated"] for c in dad["checkins"] + dad["exercise"])
    flag_day = dad["checkins"][3]["date"][:10]
    before = [e for e in dad["exercise"] if e["date"][:10] < flag_day]
    after = [e for e in dad["exercise"] if e["date"][:10] > flag_day]
    assert len(before) == 3 and len(after) >= 15
    assert after[0]["plan"]["sit_to_stand"]["sets"] == 3  # leans on chair stands, the weak area
    assert Store(tmp_path).get("sim-dad")["checkins"][-1]["level"] == "green"
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/test_seed.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'checkin.seed'`.

- [ ] **Step 3: Write** `src/checkin/seed.py`

```python
"""The "Simulated: Dad" story: chair stands slip, an amber flag appears, exercise starts, scores recover."""

from datetime import datetime, time, timedelta

from . import steadi

DAD_ID = "sim-dad"
# One row per weekly check-in: TUG s, dual-task TUG s, chair stands, tandem hold s. Age 78, male: norm is 11.
WEEKS = [
    (10.8, 12.6, 13, 10.0),
    (11.0, 12.9, 12, 10.0),
    (11.3, 13.4, 11, 10.0),
    (11.7, 14.0, 10, 10.0),  # below the STEADI average: amber, and the exercise plan starts
    (11.6, 13.8, 10, 10.0),
    (11.3, 13.3, 11, 10.0),
    (11.0, 12.9, 12, 10.0),
    (10.8, 12.6, 13, 10.0),
]
FLAG_WEEK = 3  # index of the first flagged week
HOLD_CAPABILITY = {"feet_together": 30.0, "semi_tandem": 24.0, "tandem": 12.0}  # seconds Dad can hold each


def _steps(tug, dual, stands, tandem):
    bal = lambda stance, hold, sway: {"stance": stance, "hold_s": hold, "broke": hold < 10, "sway": sway,  # noqa: E731
                                      "method": "sensor", "target_s": 10.0}
    return {
        "tug": {"tug_s": tug, "method": "sensor"},
        "dual_tug": {"tug_s": dual, "method": "sensor"},
        "chair_stand": {"stands": stands, "arms_used": False},
        "balance_feet_together": bal("feet_together", 10.0, 0.12),
        "balance_semi_tandem": bal("semi_tandem", 10.0, 0.19),
        "balance_tandem": bal("tandem", tandem, 0.28),
    }


def _exercise_log(person, when):
    plan = steadi.make_plan(person)
    sts, bal = plan["sit_to_stand"], plan["balance"]
    hold = min(bal["target_s"], HOLD_CAPABILITY[bal["stance"]])
    return {
        "id": f"sim-ex-{when:%Y%m%d}", "date": when.isoformat(timespec="seconds"), "source": "sim",
        "simulated": True, "recording": None, "plan": plan,
        "sets": [{"reps": sts["reps"], "target": sts["reps"]} for _ in range(sts["sets"])],
        "holds": [{"stance": bal["stance"], "hold_s": hold, "broke": hold < bal["target_s"], "sway": 0.2,
                   "method": "sensor", "target_s": bal["target_s"]} for _ in range(bal["holds"])],
    }


def seed_dad(store, today):
    """(Re)write the simulated history so its last check-in is `today`."""
    person = {
        "id": DAD_ID, "name": "Simulated: Dad", "simulated": True,
        "profile": {"age": 78, "sex": "male", "fallen": False, "unsteady": False, "worried": False},
        "checkins": [], "exercise": [],
    }
    first = today - timedelta(weeks=len(WEEKS) - 1)
    for i, row in enumerate(WEEKS):
        day = first + timedelta(weeks=i)
        steps = _steps(*row)
        record = steadi.evaluate(person, steadi.metrics_from_steps(steps), datetime.combine(day, time(10, 0)))
        record.update(id=f"sim-{day:%Y%m%d}", source="sim", simulated=True, steps=steps, recording=None)
        person["checkins"].append(record)
        offsets = [2] if i < FLAG_WEEK else [1, 2, 3, 5, 6]  # a pamphlet once a week, then most days
        for d in offsets:
            when = datetime.combine(day + timedelta(days=d), time(9, 30))
            if when.date() < today:
                person["exercise"].append(_exercise_log(person, when))
    store.save(person)
    return person
```

- [ ] **Step 4: Run the tests and lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: `116 passed`, then `All checks passed!`

- [ ] **Step 5: Commit**

Tick task 8 in `TASKS.md`, then:

```bash
git add src/checkin/seed.py tests/test_seed.py TASKS.md
git commit -m "feat: seeded 8-week Simulated: Dad history"
```

---

### Task 9: API server and docs/API.md

**Files:**
- Create: `src/checkin/server.py`, `docs/API.md`, `src/checkin/static/vendor/chart.umd.min.js` (downloaded)
- Test: `tests/test_server.py`

**Interfaces:**
- Consumes: `Controller` (Task 7), `Store` (Task 4), `steadi.dashboard` (Task 3); tests also use `seed_dad`, `SimSource`, `VirtualBase`, `FakeClock`.
- Produces: `create_app(controller, store, today=date.today) -> FastAPI`. The endpoints are exactly those in `docs/API.md`:
  - `GET /api/state`
  - `GET/POST /api/people`, `PUT /api/people/{id}`, `GET /api/people/{id}/dashboard`
  - `POST /api/session`, `POST /api/button`, `POST /api/stop`
  - `WS /ws`
  - `GET /`, which serves `static/index.html` (Task 11)
- Request bodies are validated at the boundary with pydantic: age 18–120; sex `male`/`female`; exercise plan limits.

The real server needs the `websockets` package for `/ws`. `TestClient` doesn't, so without `test_uvicorn_can_serve_the_websocket` a missing `websockets` would only show up in the browser. This happened while checking the plan.

- [ ] **Step 1: Write the failing test** `tests/test_server.py`

```python
import importlib.util
import time
from datetime import date

import pytest
from fastapi.testclient import TestClient

from checkin.base import VirtualBase
from checkin.clock import FakeClock
from checkin.controller import Controller
from checkin.seed import seed_dad
from checkin.server import create_app
from checkin.sources import SimSource
from checkin.store import Store

TODAY = date(2026, 9, 26)
PROFILE = {"name": "Judge", "age": 34, "sex": "female", "fallen": False, "unsteady": False, "worried": True}


@pytest.fixture
def client(tmp_path):
    clock = FakeClock()  # the whole check-in runs in simulated time
    store = Store(tmp_path)
    seed_dad(store, TODAY)
    app = create_app(Controller(SimSource(clock, seed=1), VirtualBase(), store, clock), store, today=lambda: TODAY)
    with TestClient(app) as c:
        yield c


def run_to_done(client, timeout_s=60):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        state = client.get("/api/state").json()
        if state["phase"] in ("done", "stopped"):
            return state
        if any(s["status"] == "waiting" for s in state["steps"]):
            client.post("/api/button")
    raise AssertionError("session did not finish")


def test_people_and_profiles(client):
    assert [p["id"] for p in client.get("/api/people").json()] == ["sim-dad"]
    r = client.post("/api/people", json=PROFILE)
    assert r.status_code == 201 and r.json()["id"] == "judge"
    r = client.put("/api/people/judge", json={**PROFILE, "age": 35})
    assert r.json()["profile"]["age"] == 35
    assert client.put("/api/people/judge", json={**PROFILE, "age": 7}).status_code == 422
    assert client.put("/api/people/sim-dad", json=PROFILE).status_code == 403
    assert client.get("/api/people/..%2Fsecrets/dashboard").status_code == 404


def test_checkin_over_the_api_from_button_to_dashboard(client):
    client.post("/api/people", json=PROFILE)
    assert client.post("/api/session", json={"person_id": "judge", "mode": "checkin"}).status_code == 202
    assert client.post("/api/session", json={"person_id": "judge", "mode": "checkin"}).status_code == 409
    state = run_to_done(client)
    assert state["phase"] == "done" and all(s["status"] == "done" for s in state["steps"])
    d = client.get("/api/people/judge/dashboard").json()
    latest = d["latest"]
    assert latest["simulated"] is True and latest["metrics"]["tug_s"] > 5
    assert latest["cutoffs"]["chair_label"] == "women 60–64 (the youngest STEADI group)"
    assert "key_questions" in [f["id"] for f in latest["flags"]] and d["alert"]["level"] in ("amber", "red")
    assert d["trends"]["dates"] == [latest["date"][:10]]


def test_quick_exercise_and_adherence(client):
    client.post("/api/people", json=PROFILE)
    plan = {"sit_to_stand": {"sets": 1, "reps": 5}, "balance": {"stance": "feet_together", "holds": 0,
                                                                "target_s": 20}}
    assert client.post("/api/session", json={"person_id": "judge", "mode": "exercise", "plan": plan}).status_code == 202
    run_to_done(client)
    d = client.get("/api/people/judge/dashboard").json()
    assert d["exercise"][-1]["sets"][0]["reps"] == 5
    assert d["adherence"]["weeks"][-1]["reps"] == 5


def test_bad_session_requests(client):
    client.post("/api/people", json={**PROFILE, "age": None})
    r = client.post("/api/session", json={"person_id": "judge", "mode": "checkin"})
    assert r.status_code == 400 and "age and sex" in r.json()["detail"]
    assert client.post("/api/session", json={"person_id": "nobody", "mode": "checkin"}).status_code == 404
    bad_plan = {"sit_to_stand": {"sets": 1, "reps": 500}, "balance": {"stance": "feet_together", "holds": 0,
                                                                      "target_s": 20}}
    r = client.post("/api/session", json={"person_id": "judge", "mode": "exercise", "plan": bad_plan})
    assert r.status_code == 422


def test_cancel_over_the_api(client):
    client.post("/api/people", json=PROFILE)
    client.post("/api/session", json={"person_id": "judge", "mode": "checkin"})
    while client.get("/api/state").json()["phase"] != "running":
        pass
    client.post("/api/stop", json={"reason": "cancel"})
    assert run_to_done(client)["phase"] == "stopped"
    assert client.get("/api/people/judge/dashboard").json()["latest"] is None


def test_simulated_dad_dashboard(client):
    d = client.get("/api/people/sim-dad/dashboard").json()
    assert d["person"]["simulated"] and d["level"] == "green"
    assert d["trends"]["levels"].count("amber") == 2 and d["adherence"]["last_7_days"] == 5


def test_websocket_sends_state_then_events(client):
    with client.websocket_connect("/ws") as ws:
        first = ws.receive_json()
        assert first["type"] == "state" and first["source"]["simulated"] is True
        assert ws.receive_json()["type"] == "state"  # the idle heartbeat


def test_uvicorn_can_serve_the_websocket():
    # TestClient doesn't need it, but the real server does: without it /ws fails and the page never updates
    assert importlib.util.find_spec("websockets"), "add the websockets package"
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/test_server.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'checkin.server'`.

- [ ] **Step 3: Vendor Chart.js** (the only download; the page must work offline afterwards)

```bash
mkdir -p src/checkin/static/vendor
curl -fL -o src/checkin/static/vendor/chart.umd.min.js https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js
head -c 120 src/checkin/static/vendor/chart.umd.min.js
```

Expected: about 208 KB, starting with `/*!\n * Chart.js v4.5.1`.

- [ ] **Step 4: Write** `src/checkin/server.py`

```python
"""FastAPI app: the JSON + WebSocket API in docs/API.md, plus the static dashboard."""

import asyncio
import contextlib
from datetime import date
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import steadi
from .controller import Busy

STATIC = Path(__file__).parent / "static"


class ProfileIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    age: int | None = Field(None, ge=18, le=120)
    sex: Literal["male", "female"] | None = None
    fallen: bool = False
    unsteady: bool = False
    worried: bool = False


class SetsIn(BaseModel):
    sets: int = Field(ge=0, le=6)
    reps: int = Field(ge=1, le=20)


class HoldsIn(BaseModel):
    stance: Literal["feet_together", "semi_tandem", "tandem"]
    holds: int = Field(ge=0, le=6)
    target_s: float = Field(gt=0, le=60)


class PlanIn(BaseModel):
    sit_to_stand: SetsIn
    balance: HoldsIn


class SessionIn(BaseModel):
    person_id: str
    mode: Literal["checkin", "exercise"]
    plan: PlanIn | None = None  # exercise only; default is the person's plan


class StopIn(BaseModel):
    reason: Literal["arms_used", "cancel"]


def create_app(controller, store, today=date.today):
    clients: set[asyncio.Queue] = set()

    def broadcast(event):
        for q in list(clients):
            q.put_nowait(event)

    controller.on_event = broadcast

    @contextlib.asynccontextmanager
    async def lifespan(app):
        task = asyncio.create_task(controller.run())
        yield
        task.cancel()
        controller.source.close()
        controller.base.close()

    app = FastAPI(title="Fall-risk check-in", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    def person_or_404(pid):
        try:
            return store.get(pid)
        except KeyError:
            raise HTTPException(404, f"no person {pid!r}") from None

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/state")
    def state():
        return controller.state

    @app.get("/api/people")
    def people():
        return store.people()

    @app.post("/api/people", status_code=201)
    def create_person(body: ProfileIn):
        profile = body.model_dump(exclude={"name"})
        return store.create(body.name, profile)

    @app.put("/api/people/{pid}")
    def update_person(pid: str, body: ProfileIn):
        person = person_or_404(pid)
        if person["simulated"]:
            raise HTTPException(403, "the simulated person is read-only; reseed with `checkin seed`")
        person["name"] = body.name
        person["profile"] = body.model_dump(exclude={"name"})
        store.save(person)
        return person

    @app.get("/api/people/{pid}/dashboard")
    def dashboard(pid: str):
        return steadi.dashboard(person_or_404(pid), today())

    @app.post("/api/session", status_code=202)
    def start_session(body: SessionIn):
        try:
            controller.start(body.person_id, body.mode, body.plan.model_dump() if body.plan else None)
        except Busy as e:
            raise HTTPException(409, str(e)) from None
        except KeyError:
            raise HTTPException(404, f"no person {body.person_id!r}") from None
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        return {"ok": True}

    @app.post("/api/button")
    def button():
        controller.press()
        return {"ok": True}

    @app.post("/api/stop")
    def stop(body: StopIn):
        controller.stop(body.reason)
        return {"ok": True}

    @app.websocket("/ws")
    async def ws(socket: WebSocket):
        await socket.accept()
        q = asyncio.Queue()
        clients.add(q)
        try:
            await socket.send_json({"type": "state", **controller.state})
            while True:
                await socket.send_json(await q.get())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            clients.discard(q)

    return app
```

- [ ] **Step 5: Write** `docs/API.md`

````markdown
# Check-in API

Everything the dashboard shows comes from here, so the UI can be rebuilt without touching the backend.
Served by `uv run checkin serve` at `http://<laptop>:8000`. JSON everywhere; no auth (it's on the home network and never leaves it).

Units: seconds (`_s`), percent (`_pct`), sway in m/s² (RMS horizontal acceleration at the lower back).
`null` means "not measured" (for example the belt dropped out); it never means zero.
Anything with `"simulated": true` must be labelled "Simulated" wherever it's shown.

## Live state

### `GET /api/state`

The session controller's current state. The same object arrives over the WebSocket as `{"type": "state", ...}`.

```json
{
  "mode": "checkin",
  "person_id": "guest",
  "phase": "running",
  "step": "chair_stand",
  "prompt": "Sit in the middle of the armless chair, arms crossed on your chest. On 'Go', ...",
  "steps": [
    {"id": "tug", "label": "Timed Up and Go", "status": "done", "result": {"tug_s": 10.43, "method": "sensor"}},
    {"id": "dual_tug", "label": "Timed Up and Go while naming animals", "status": "done",
     "result": {"tug_s": 12.51, "method": "sensor"}},
    {"id": "chair_stand", "label": "30-second chair stand", "status": "running", "result": null},
    {"id": "balance_feet_together", "label": "Balance: feet together", "status": "pending", "result": null}
  ],
  "live": {"elapsed_s": 9.8, "reps": 4},
  "led": "blue",
  "base": "virtual",
  "base_connected": true,
  "source": {"kind": "sim", "simulated": true, "rate_hz": 99.9},
  "last_record": null
}
```

| Field | Values |
|---|---|
| `mode` | `idle`, `checkin`, `exercise` |
| `phase` | `idle`, `running`, `done` (saved; `last_record` holds the record), `stopped` (cancelled or failed; nothing saved) |
| `steps[].status` | `pending`, `waiting` (press the button), `running` (timing), `done`, `failed` (not measured), `skipped` (balance stopped at an earlier stance) |
| `live` | `elapsed_s` since "Go"; `reps` counted so far (chair stand, sit-to-stands); `target` reps (exercise) |
| `led` | `off`, `blue` (session in progress), `green`, `amber`, `red` (level of the check-in just saved) |
| `base` | `virtual` (the page plays the tones) or `serial` (the Arduino does) |
| `source.kind` | `sim`, `csv`, `udp`, `phyphox` |

Step ids: check-in `tug`, `dual_tug`, `chair_stand`, `balance_feet_together`, `balance_semi_tandem`, `balance_tandem`;
exercise `sit_to_stand#1`, `sit_to_stand#2`, …, `hold_<stance>#1`, ….

Step results:

| Step | Result |
|---|---|
| `tug`, `dual_tug` | `{"tug_s": 10.43, "method": "sensor" \| "button" \| "timeout"}` (`button` = the helper pressed when seated; `timeout` = `tug_s: null` after 60 s) |
| `chair_stand` | `{"stands": 12, "arms_used": false}` (`arms_used: true` records 0, per STEADI) |
| `balance_*`, `hold_*` | `{"stance": "tandem", "hold_s": 6.6, "broke": true, "sway": 0.371, "method": "sensor" \| "button", "target_s": 10.0}` |
| `sit_to_stand#N` | `{"reps": 5, "target": 5}` |
| any, sensor dropped out | `{"error": "no sensor data" \| "sensor data dropped out"}` |

### `WS /ws`

Sends the state on connect, then events:

| Event | When |
|---|---|
| `{"type": "state", ...}` | Any state change; about 4 per second while a step runs, once a second when idle |
| `{"type": "cue", "name": "start" \| "stop" \| "done" \| "error" \| "rep"}` | A buzzer cue. Play it only when `state.base == "virtual"`; tones are in `firmware/PROTOCOL.md` |
| `{"type": "saved", "person_id": "guest", "mode": "checkin", "id": "20260926-100516-checkin"}` | A session was saved: refetch that person's dashboard |

## Controls

| Request | Body | Response |
|---|---|---|
| `POST /api/session` | `{"person_id": "guest", "mode": "checkin"}` | `202`; `409` if a session is running; `404` unknown person; `400` check-in without age and sex |
| `POST /api/session` | `{"person_id": "guest", "mode": "exercise", "plan": {...}}` | `plan` is optional (default: the person's plan, below); `422` if out of range |
| `POST /api/button` | none | The on-screen button: starts the waiting step; during a TUG it stops the clock (stopwatch fallback); during a balance stance it marks the stance as broken |
| `POST /api/stop` | `{"reason": "arms_used"}` | During the chair stand: stop and record 0 stands (STEADI) |
| `POST /api/stop` | `{"reason": "cancel"}` | End the session; nothing is saved |

Exercise `plan` limits: `sit_to_stand.sets` 0–6, `reps` 1–20; `balance.stance` one of `feet_together`, `semi_tandem`, `tandem`; `holds` 0–6; `target_s` above 0, at most 60.
Quick demo (5 sit-to-stands, no holds):
`{"sit_to_stand": {"sets": 1, "reps": 5}, "balance": {"stance": "feet_together", "holds": 0, "target_s": 20}}`

## People

| Request | Body | Response |
|---|---|---|
| `GET /api/people` | | `[{"id": "guest", "name": "Guest", "simulated": false}, ...]` sorted by name |
| `POST /api/people` | profile (below) | `201` with the new person; the id is made from the name |
| `PUT /api/people/{id}` | profile | The updated person; `403` for the simulated person; `422` if invalid |

Profile body (step 0 of the check-in):

```json
{"name": "Pat", "age": 78, "sex": "male", "fallen": false, "unsteady": false, "worried": true}
```

`age` 18–120 or `null`; `sex` `"male"`, `"female"`, or `null` (both are needed for the STEADI chair-stand norm before a check-in). The three booleans are the STEADI key questions.

### `GET /api/people/{id}/dashboard`

Everything the family view shows for one person.

```json
{
  "person": {"id": "sim-dad", "name": "Simulated: Dad", "simulated": true,
             "profile": {"age": 78, "sex": "male", "fallen": false, "unsteady": false, "worried": false}},
  "latest": { "...": "the latest check-in record, below" },
  "level": "green",
  "alert": null,
  "trends": {
    "dates": ["2026-08-08", "..."],
    "levels": ["green", "..."],
    "series": {"tug_s": [10.8, "..."], "dual_task_cost_pct": [16.7, "..."], "chair_stands": [13, "..."],
               "tandem_s": [10.0, "..."]},
    "cutoffs": {"tug_s": 12.0, "chair_stands": 11, "tandem_s": 10.0}
  },
  "plan": {"sit_to_stand": {"sets": 3, "reps": 8}, "balance": {"stance": "tandem", "holds": 2, "target_s": 20.0},
           "why": "more sit-to-stands: chair stands are at or near the STEADI line"},
  "adherence": {"target_days_per_week": 5, "last_7_days": 5,
                "weeks": [{"week_start": "2026-09-21", "days": 4, "sessions": 4, "reps": 96, "hold_s": 96.0}]},
  "exercise": [ "... the last 10 exercise logs, below" ]
}
```

`trends.cutoffs` are STEADI lines for charts: TUG flags at 12 s or more; chair stands flag below the number; tandem flags below 10 s. `adherence.weeks` covers the last 8 weeks (Monday start), oldest first.

### Check-in record

```json
{
  "id": "20260829-100000-checkin",
  "date": "2026-08-29T10:00:00",
  "source": "sim",
  "simulated": true,
  "recording": "20260829-100000-checkin.csv",
  "key_questions": {"fallen": false, "unsteady": false, "worried": false},
  "metrics": {"tug_s": 11.7, "dual_tug_s": 14.0, "dual_task_cost_pct": 19.7, "chair_stands": 10,
              "feet_together_s": 10.0, "feet_together_sway": 0.12, "semi_tandem_s": 10.0, "semi_tandem_sway": 0.19,
              "tandem_s": 10.0, "tandem_sway": 0.28},
  "cutoffs": {"tug_s": 12.0, "tandem_s": 10.0, "chair_stands": 11, "chair_label": "men 75–79"},
  "flags": [{"id": "chair_stand", "text": "10 chair stands in 30 s, below the STEADI average of 11 for men 75–79"}],
  "changes": {"tug_s": {"baseline": 11.03, "change": 0.67, "worse": false},
              "dual_task_cost_pct": {"baseline": 17.53, "change": 2.17, "worse": false},
              "chair_stands": {"baseline": 12, "change": -2, "worse": true},
              "tandem_s": {"baseline": 10.0, "change": 0.0, "worse": false}},
  "declines": [],
  "level": "amber",
  "alert": {"level": "amber", "title": "Simulated: Dad: this check-in flags increased fall risk",
            "items": ["10 chair stands in 30 s, below the STEADI average of 11 for men 75–79"],
            "advice": "Mention these results at the next doctor's visit, and keep up the exercises most days.",
            "note": "Fall-risk screening with the CDC's STEADI tests. A doctor can do a full fall-risk assessment."},
  "steps": {"tug": {"tug_s": 11.7, "method": "sensor"}, "...": "step results, keyed by step id"}
}
```

- `flags[].id`: `key_questions` (any "yes"; one flag naming the answers), `tug`, `chair_stand`, `balance`.
- `level`: green = no flags; amber = 1 flag or a sustained decline; red = 2 or more flags (our summary, not STEADI's).
- `changes`: vs. the rolling baseline (mean of up to 4 earlier check-ins; `null` until there are 2). `worse` = past the threshold: TUG +10%, dual-task cost +10 points, chair stands −2, tandem −3 s.
- `declines`: metrics worse than baseline in this check-in and the one before (`[{"id": "chair_stands", "text": "..."}]`).
- `alert`: `null` when green. `advice` says when to see a doctor.
- `chair_label` says when the person's age is outside the STEADI table (for example "women 60–64 (the youngest STEADI group)").
- `recording` is a file in `data/recordings/`; `checkin replay` re-scores it.

### Exercise log

```json
{
  "id": "20260926-100853-exercise", "date": "2026-09-26T10:08:53", "source": "sim", "simulated": true,
  "recording": "20260926-100853-exercise.csv",
  "plan": {"sit_to_stand": {"sets": 1, "reps": 5}, "balance": {"stance": "feet_together", "holds": 0, "target_s": 20}},
  "sets": [{"reps": 5, "target": 5}],
  "holds": [{"stance": "feet_together", "hold_s": 20.0, "broke": false, "sway": 0.15, "method": "sensor",
             "target_s": 20.0}]
}
```

Balance holds move up a stance (feet together → semi-tandem → tandem) once every hold in the latest session reaches its target.

## Files

- `data/people/<id>.json`: `{"id", "name", "simulated", "profile", "checkins": [...], "exercise": [...]}`
- `data/recordings/<session id>.csv`: first line `# source=<kind> simulated=<0|1>`, then `t,ax,ay,az,gx,gy,gz,step` (s, g, °/s; `step` is the step id for samples from its "Go" to its end, blank otherwise)
````

- [ ] **Step 6: Run the tests and lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: `124 passed`, then `All checks passed!`

- [ ] **Step 7: Commit**

Tick task 9 in `TASKS.md`, then:

```bash
git add src/checkin/server.py src/checkin/static/vendor/chart.umd.min.js docs/API.md tests/test_server.py TASKS.md
git commit -m "feat: JSON + WebSocket API with docs, vendored Chart.js"
```

---

### Task 10: CLI

**Files:**
- Create: `src/checkin/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `open_source`, `open_base`, `Controller`, `Clock`, `create_app`, `Store`, `seed_dad`, `score_step`, `read_recording`, `steadi.metrics_from_steps`, `steadi.chair_norm`, `steadi.flags_for`.
- Produces:
  - `main(argv=None)` for the `checkin` entry point in `pyproject.toml`
  - `replay(path, age=None, sex=None) -> {"file", "simulated", "steps", "metrics"?, "cutoffs"?, "flags"?}`, which `checkin replay` prints as JSON
  - `checkin serve` seeds `sim-dad` and a blank `guest` on first run
  - `checkin seed` rewrites Dad's history to end today
- Settings are flags with environment fallbacks: `--udp-port` (`CHECKIN_UDP_PORT`, 4210), `--serial-port` (`CHECKIN_SERIAL_PORT`), `--data` (`CHECKIN_DATA`, `data/`), `--host` (0.0.0.0 so the tablet can connect), `--port` (8000).

- [ ] **Step 1: Write the failing test** `tests/test_cli.py`

```python
import json

import numpy as np
import pytest

from checkin import sim
from checkin.cli import main
from checkin.store import write_recording


def test_replay_scores_a_recording(tmp_path, capsys):
    p = sim.SimParams(stand_cycle_s=3.0)
    t1, a1, g1, tug = sim.simulate("tug", p, seed=1)
    t2, a2, g2, chair = sim.simulate("chair_stand", p, seed=2)
    t2 = t2 + t1[-1] + 2.0
    data = np.vstack([np.column_stack([t1, a1, g1]), np.column_stack([t2, a2, g2])])
    go2 = t2[100]  # simulate() puts 1 s of stillness before "Go"
    path = tmp_path / "rec.csv"
    write_recording(path, data, [("tug", 0.0, t1[-1]), ("chair_stand", go2, go2 + 32.0)], "udp", False)
    main(["replay", str(path), "--age", "70", "--sex", "female"])
    out = json.loads(capsys.readouterr().out)
    assert abs(out["steps"]["tug"]["tug_s"] - tug["tug_s"]) < 0.5
    assert out["steps"]["chair_stand"]["stands"] == chair["stands"] == 10
    assert out["simulated"] is False and out["flags"] == []


def test_replay_explains_an_untagged_file(tmp_path):
    path = tmp_path / "raw.csv"
    write_recording(path, np.zeros((20, 7)), [], "udp", False)
    with pytest.raises(SystemExit, match="no step tags"):
        main(["replay", str(path)])


def test_seed_writes_the_simulated_history(tmp_path, capsys):
    main(["seed", "--data", str(tmp_path)])
    doc = json.loads((tmp_path / "people" / "sim-dad.json").read_text())
    assert doc["simulated"] and len(doc["checkins"]) == 8
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/test_cli.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'checkin.cli'`.

- [ ] **Step 3: Write** `src/checkin/cli.py`

```python
"""`checkin serve | replay | seed`."""

import argparse
import json
import logging
import os
from datetime import date
from pathlib import Path

DATA = Path(os.environ.get("CHECKIN_DATA", "data"))


def replay(path, age=None, sex=None):
    """Score every tagged step in a recording; with age and sex, also the STEADI flags."""
    from . import steadi
    from .signals import score_step
    from .store import read_recording

    rec = read_recording(path)
    if not rec.steps:
        raise SystemExit(f"{path}: no step tags; record a session with `checkin serve` first")
    t, acc, gyro = rec.data[:, 0], rec.data[:, 1:4], rec.data[:, 4:7]
    steps = {}
    for sid, (t_go, t_end) in sorted(rec.steps.items(), key=lambda kv: kv[1][0]):
        keep = (t >= t_go - 1.0) & (t <= t_end)
        steps[sid] = score_step(sid, t[keep], acc[keep], gyro[keep], t_go, t_end)
    out = {"file": str(path), "simulated": rec.simulated, "steps": steps}
    if "tug" in steps or "chair_stand" in steps:
        out["metrics"] = steadi.metrics_from_steps(steps)
        if age and sex:
            profile = {"age": age, "sex": sex}
            out["cutoffs"] = {"chair_stands": steadi.chair_norm(age, sex), "tug_s": steadi.TUG_CUTOFF_S,
                              "tandem_s": steadi.TANDEM_CUTOFF_S}
            out["flags"] = steadi.flags_for(profile, out["metrics"])
    return out


def serve(args):
    import uvicorn

    from .base import open_base
    from .clock import Clock
    from .controller import Controller
    from .seed import DAD_ID, seed_dad
    from .server import create_app
    from .sources import open_source
    from .store import Store

    store = Store(args.data)
    ids = {p["id"] for p in store.people()}
    if DAD_ID not in ids:
        seed_dad(store, date.today())
    if "guest" not in ids:
        store.create("Guest", {"age": None, "sex": None, "fallen": False, "unsteady": False, "worried": False},
                     pid="guest")
    clock = Clock()
    source = open_source(args.source, clock, udp_port=args.udp_port)
    base = open_base(args.base, args.serial_port)
    app = create_app(Controller(source, base, store, clock), store)
    print(f"Dashboard: http://localhost:{args.port}  (source={args.source}, base={args.base})")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="checkin", description="STEADI fall-risk screening check-in")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("serve", help="run the session controller and dashboard")
    s.add_argument("--source", default="sim", help="sim | csv:<file> | udp | phyphox:<http://phone-ip:8080>")
    s.add_argument("--base", default="virtual", help="virtual | serial")
    s.add_argument("--serial-port", default=os.environ.get("CHECKIN_SERIAL_PORT"),
                   help="base station port, e.g. /dev/cu.usbmodem1101 or COM3 (env CHECKIN_SERIAL_PORT)")
    s.add_argument("--udp-port", type=int, default=int(os.environ.get("CHECKIN_UDP_PORT", "4210")),
                   help="port the belt broadcasts to (env CHECKIN_UDP_PORT, default 4210)")
    s.add_argument("--host", default="0.0.0.0", help="0.0.0.0 lets the tablet on the same network connect")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--data", type=Path, default=DATA)
    r = sub.add_parser("replay", help="score a recording made by `checkin serve`")
    r.add_argument("file", type=Path)
    r.add_argument("--age", type=int)
    r.add_argument("--sex", choices=["male", "female"])
    d = sub.add_parser("seed", help="rewrite the 'Simulated: Dad' history ending today")
    d.add_argument("--data", type=Path, default=DATA)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.cmd == "serve":
        serve(args)
    elif args.cmd == "replay":
        print(json.dumps(replay(args.file, args.age, args.sex), indent=2))
    elif args.cmd == "seed":
        from .seed import seed_dad
        from .store import Store

        seed_dad(Store(args.data), date.today())
        print(f"Wrote {args.data / 'people' / 'sim-dad.json'}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests, lint, and the entry point**

Run: `uv run pytest -q && uv run ruff check . && uv run checkin --help`
Expected: `127 passed`, `All checks passed!`, then usage listing `{serve,replay,seed}`.

- [ ] **Step 5: Commit**

Tick task 10 in `TASKS.md`, then:

```bash
git add src/checkin/cli.py tests/test_cli.py TASKS.md
git commit -m "feat: checkin serve, replay, and seed commands"
```

---

### Task 11: Dashboard page

**Files:**
- Create: `src/checkin/static/index.html`, `src/checkin/static/app.js`
- Modify: `tests/test_server.py` (add one test)

**Interfaces:**
- Consumes: only `docs/API.md` (`/api/*`, `/ws`) and the cue tone table in `firmware/PROTOCOL.md`.
- Produces: a bare-bones, unstyled page with:
  - person picker, and the profile form with the three key questions (step 0)
  - on-screen Button, LED, sensor rate, and the "Simulated" tag
  - start, quick-exercise, arms-used, and cancel controls
  - live step progress
  - family alert
  - results vs. STEADI cutoffs with change from baseline
  - four trend charts with cutoff lines
  - exercise plan and adherence chart
  - recent sessions

  Tones play through WebAudio only when `state.base == "virtual"`. All text goes in with `textContent` (names are user input).

- [ ] **Step 1: Add the failing test**

Append to `tests/test_server.py`:

```python
def test_index_page_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "<html" in r.text.lower()
```

- [ ] **Step 2: Run it to see it fail**

Run: `uv run pytest tests/test_server.py -q -k index`
Expected: FAIL (`index.html` doesn't exist yet).

- [ ] **Step 3: Write** `src/checkin/static/index.html`

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fall-risk check-in</title>
<!-- Bare-bones on purpose: every value here comes from the API in docs/API.md, so this page can be replaced. -->
<style>
  body { font-family: system-ui, sans-serif; margin: 1rem; max-width: 60rem; }
  section { border-top: 1px solid #ccc; padding: 0.5rem 0 1rem; }
  table { border-collapse: collapse; }
  th, td { border: 1px solid #ccc; padding: 0.2rem 0.5rem; text-align: left; vertical-align: top; }
  .led { display: inline-block; width: 1.1rem; height: 1.1rem; border-radius: 50%; border: 1px solid #333;
         vertical-align: middle; background: #eee; }
  .led.blue { background: #2563eb; } .led.green { background: #16a34a; }
  .led.amber { background: #f59e0b; } .led.red { background: #dc2626; }
  .tag { background: #fde68a; padding: 0 0.3rem; }
  .flag { color: #b91c1c; font-weight: bold; }
  #button { font-size: 1.4rem; padding: 0.8rem 2rem; }
  .chart { max-width: 34rem; }
  label { margin-right: 0.8rem; }
</style>
</head>
<body>
<h1>Fall-risk check-in</h1>
<p>Fall-risk screening with the CDC's STEADI tests: it flags increased fall risk and tracks change from baseline.</p>

<section>
  <label>Person <select id="person"></select></label> <span id="person-tag"></span>
  <details id="profile-box">
    <summary>Profile and STEADI key questions (step 0)</summary>
    <form id="profile">
      <p>
        <label>Name <input name="name" required maxlength="60"></label>
        <label>Age <input name="age" type="number" min="18" max="120"></label>
        <label>Sex (for the chair-stand norm)
          <select name="sex"><option value="">–</option><option value="male">Male</option>
            <option value="female">Female</option></select></label>
      </p>
      <fieldset>
        <legend>STEADI key questions</legend>
        <label><input type="checkbox" name="fallen"> Fallen in the past year?</label><br>
        <label><input type="checkbox" name="unsteady"> Feels unsteady when standing or walking?</label><br>
        <label><input type="checkbox" name="worried"> Worries about falling?</label>
      </fieldset>
      <p><button type="submit">Save profile</button> <button type="button" id="new-person">Save as new person</button>
        <span id="profile-msg"></span></p>
    </form>
  </details>
</section>

<section>
  <h2>Base station</h2>
  <p>LED <span id="led" class="led"></span> · base: <span id="base"></span> · sensor: <span id="source"></span></p>
  <p><button id="button">Button</button></p>
  <p>
    <button id="start-checkin">Start check-in</button>
    <button id="start-exercise">Start exercise (plan)</button>
    <button id="start-quick">Quick exercise: 5 sit-to-stands</button>
    <button id="arms-used">Arms used: chair stand scores 0</button>
    <button id="cancel">Cancel session</button>
  </p>
  <p id="msg"></p>
</section>

<section>
  <h2>Step progress</h2>
  <p id="prompt"></p>
  <p id="live"></p>
  <ul id="steps"></ul>
</section>

<section>
  <h2>Family alert</h2>
  <div id="alert"></div>
</section>

<section>
  <h2>Latest check-in vs. STEADI cutoffs</h2>
  <div id="results"></div>
</section>

<section>
  <h2>Trends</h2>
  <div class="chart"><canvas id="chart-tug"></canvas></div>
  <div class="chart"><canvas id="chart-chair"></canvas></div>
  <div class="chart"><canvas id="chart-tandem"></canvas></div>
  <div class="chart"><canvas id="chart-cost"></canvas></div>
</section>

<section>
  <h2>Exercise</h2>
  <p id="plan"></p>
  <div class="chart"><canvas id="chart-adherence"></canvas></div>
  <div id="sessions"></div>
</section>

<script src="/static/vendor/chart.umd.min.js"></script>
<script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Write** `src/checkin/static/app.js`

```javascript
"use strict";
// Bare-bones dashboard: renders GET /api/people/{id}/dashboard and the /ws state stream (docs/API.md).

const $ = (id) => document.getElementById(id);
const QUICK_PLAN = { sit_to_stand: { sets: 1, reps: 5 }, balance: { stance: "feet_together", holds: 0, target_s: 20 } };
// Buzzer cues from firmware/PROTOCOL.md: [frequency Hz (0 = silence), milliseconds]
const CUES = {
  start: [[2000, 150], [0, 80], [3000, 150]],
  stop: [[1500, 600]],
  done: [[2093, 150], [2637, 150], [3136, 250]],
  error: [[800, 100], [0, 80], [800, 100], [0, 80], [800, 100]],
  rep: [[2500, 80]],
};
const STEP_UNITS = { tug_s: " s", stands: " stands", hold_s: " s held" };

let personId = null;
let state = null;
let audio = null;
const charts = {};

function h(tag, text, attrs = {}) {
  const el = document.createElement(tag);
  if (text !== undefined && text !== null) el.textContent = text;
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

async function api(method, path, body) {
  const r = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : `${r.status} ${JSON.stringify(data.detail)}`);
  return data;
}

function say(text) {
  $("msg").textContent = text;
}

function play(name) {
  if (!state || state.base !== "virtual" || !audio) return; // a real base station beeps by itself
  let t = audio.currentTime;
  for (const [freq, ms] of CUES[name] || []) {
    if (freq) {
      const osc = audio.createOscillator();
      const gain = audio.createGain();
      osc.type = "square";
      osc.frequency.value = freq;
      gain.gain.value = 0.05;
      osc.connect(gain).connect(audio.destination);
      osc.start(t);
      osc.stop(t + ms / 1000);
    }
    t += ms / 1000;
  }
}

// ---- live state ---------------------------------------------------------------------------------
function stepSummary(r) {
  if (!r) return "";
  if (r.error) return `not measured: ${r.error}`;
  const parts = [];
  for (const [k, unit] of Object.entries(STEP_UNITS)) {
    if (k in r) parts.push(r[k] === null ? "not measured" : `${r[k]}${unit}`);
  }
  if ("reps" in r) parts.push(`${r.reps} of ${r.target} reps`);
  if (r.sway !== undefined) parts.push(`sway ${r.sway} m/s²`);
  if (r.method && r.method !== "sensor") parts.push(`(${r.method})`);
  if (r.arms_used) parts.push("(arms used)");
  return parts.join(" ");
}

function renderState(s) {
  state = s;
  $("led").className = `led ${s.led}`;
  $("base").textContent = `${s.base}${s.base_connected ? "" : " (not connected)"}`;
  const src = s.source;
  $("source").textContent = `${src.kind}, ${src.rate_hz} Hz`;
  if (src.simulated) $("source").append(" ", h("span", "Simulated", { class: "tag" }));
  $("prompt").textContent = s.prompt || "";
  const live = s.live || {};
  $("live").textContent = [
    live.elapsed_s !== undefined ? `${live.elapsed_s} s` : "",
    live.reps !== undefined ? `${live.reps}${live.target ? ` of ${live.target}` : ""} counted` : "",
  ].filter(Boolean).join(" · ");
  const list = $("steps");
  list.replaceChildren();
  for (const step of s.steps) {
    list.append(h("li", `${step.label}: ${step.status}${step.result ? ` — ${stepSummary(step.result)}` : ""}`));
  }
  const busy = s.phase === "running";
  for (const id of ["start-checkin", "start-exercise", "start-quick"]) $(id).disabled = busy;
  $("cancel").disabled = $("arms-used").disabled = !busy;
}

function connect() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onmessage = (e) => {
    const ev = JSON.parse(e.data);
    if (ev.type === "state") renderState(ev);
    else if (ev.type === "cue") play(ev.name);
    else if (ev.type === "saved" && ev.person_id === personId) loadDashboard();
  };
  ws.onclose = () => {
    $("source").textContent = "server disconnected, retrying…";
    setTimeout(connect, 1000);
  };
}

// ---- dashboard ----------------------------------------------------------------------------------
async function loadPeople() {
  const people = await api("GET", "/api/people");
  const sel = $("person");
  sel.replaceChildren(...people.map((p) => new Option(p.name, p.id)));
  if (!people.some((p) => p.id === personId)) personId = (people.find((p) => !p.simulated) || people[0] || {}).id;
  sel.value = personId;
  await loadDashboard();
}

async function loadDashboard() {
  if (!personId) return;
  const d = await api("GET", `/api/people/${encodeURIComponent(personId)}/dashboard`);
  renderProfile(d.person);
  renderAlert(d.alert, d.latest);
  renderResults(d.latest);
  renderTrends(d.trends);
  renderExercise(d.plan, d.adherence, d.exercise);
}

function renderProfile(person) {
  $("person-tag").replaceChildren(person.simulated ? h("span", "Simulated", { class: "tag" }) : "");
  const f = $("profile");
  f.name.value = person.name;
  f.age.value = person.profile.age ?? "";
  f.sex.value = person.profile.sex ?? "";
  for (const k of ["fallen", "unsteady", "worried"]) f[k].checked = !!person.profile[k];
  if (!person.simulated && !(person.profile.age && person.profile.sex)) $("profile-box").open = true;
}

function renderAlert(alert, latest) {
  const box = $("alert");
  box.replaceChildren();
  if (!latest) {
    box.append(h("p", "No check-in yet."));
    return;
  }
  if (!alert) {
    box.append(h("p", "No flags in the latest check-in. Keep up the exercises most days."));
    return;
  }
  box.append(h("p", `${alert.level.toUpperCase()}: ${alert.title}`, { class: "flag" }));
  const ul = h("ul");
  for (const item of alert.items) ul.append(h("li", item));
  box.append(ul, h("p", alert.advice), h("p", alert.note));
}

function change(latest, key) {
  const c = latest.changes[key];
  if (!c) return "not enough history";
  return `${c.change > 0 ? "+" : ""}${c.change} vs. baseline ${c.baseline}${c.worse ? " (worse)" : ""}`;
}

function renderResults(latest) {
  const box = $("results");
  box.replaceChildren();
  if (!latest) {
    box.append(h("p", "No check-in yet."));
    return;
  }
  const m = latest.metrics;
  const flagged = new Set(latest.flags.map((f) => f.id));
  const fmt = (v, unit) => (v === null || v === undefined ? "not measured" : `${v}${unit}`);
  const header = h("p", `${latest.date.replace("T", " ")} · level ${latest.level} · source ${latest.source} `);
  if (latest.simulated) header.append(h("span", "Simulated", { class: "tag" }));
  const table = h("table");
  const head = h("tr");
  head.append(h("th", "Test"), h("th", "Result"), h("th", "STEADI flags when"), h("th", "Flag"),
    h("th", "Change from baseline"));
  table.append(head);
  const yes = Object.entries(latest.key_questions).filter(([, v]) => v).map(([k]) => k);
  const rows = [
    ["Key questions", yes.length ? `yes: ${yes.join(", ")}` : "all no", "any yes", "key_questions", null],
    ["Timed Up and Go", fmt(m.tug_s, " s"), `${latest.cutoffs.tug_s} s or more`, "tug", "tug_s"],
    ["TUG naming animals", fmt(m.dual_tug_s, " s"), "(ours: tracked vs. baseline)", null, null],
    ["Dual-task cost", fmt(m.dual_task_cost_pct, "%"), "(ours: tracked vs. baseline)", null, "dual_task_cost_pct"],
    ["30-second chair stand", fmt(m.chair_stands, " stands"),
      latest.cutoffs.chair_stands ? `under ${latest.cutoffs.chair_stands} (${latest.cutoffs.chair_label})` : "needs age and sex",
      "chair_stand", "chair_stands"],
    ["Balance: feet together", `${fmt(m.feet_together_s, " s")}, sway ${fmt(m.feet_together_sway, " m/s²")}`, "", null, null],
    ["Balance: semi-tandem", `${fmt(m.semi_tandem_s, " s")}, sway ${fmt(m.semi_tandem_sway, " m/s²")}`, "", null, null],
    ["Balance: tandem", `${fmt(m.tandem_s, " s")}, sway ${fmt(m.tandem_sway, " m/s²")}`,
      `under ${latest.cutoffs.tandem_s} s`, "balance", "tandem_s"],
  ];
  for (const [name, value, cutoff, flagId, changeKey] of rows) {
    const tr = h("tr");
    const isFlag = flagId && flagged.has(flagId);
    tr.append(h("td", name), h("td", value), h("td", cutoff), h("td", isFlag ? "FLAG" : "", isFlag ? { class: "flag" } : {}),
      h("td", changeKey ? change(latest, changeKey) : ""));
    table.append(tr);
  }
  box.append(header, table);
}

function lineChart(id, label, dates, values, cutoff, cutoffLabel) {
  charts[id]?.destroy();
  const datasets = [{ label, data: values, spanGaps: true }];
  if (cutoff !== null && cutoff !== undefined) {
    datasets.push({ label: cutoffLabel, data: dates.map(() => cutoff), borderDash: [6, 4], pointRadius: 0 });
  }
  charts[id] = new Chart($(id), { type: "line", data: { labels: dates, datasets }, options: { animation: false } });
}

function renderTrends(t) {
  const s = t.series;
  const c = t.cutoffs;
  lineChart("chart-tug", "Timed Up and Go (s)", t.dates, s.tug_s, c.tug_s, "STEADI cutoff (12 s)");
  lineChart("chart-chair", "Chair stands in 30 s", t.dates, s.chair_stands, c.chair_stands, "STEADI below-average line");
  lineChart("chart-tandem", "Tandem stance (s)", t.dates, s.tandem_s, c.tandem_s, "STEADI cutoff (10 s)");
  lineChart("chart-cost", "Dual-task cost (%)", t.dates, s.dual_task_cost_pct, null, "");
}

function renderExercise(plan, adherence, sessions) {
  const sts = plan.sit_to_stand;
  const bal = plan.balance;
  $("plan").textContent = `Plan: ${sts.sets} sets of ${sts.reps} sit-to-stands; ${bal.holds} supported holds of ` +
    `${bal.target_s} s (${bal.stance.replace("_", " ")}). Why: ${plan.why}. ` +
    `Exercise days in the last 7: ${adherence.last_7_days} of ${adherence.target_days_per_week} planned.`;
  const weeks = adherence.weeks;
  charts.adherence?.destroy();
  charts.adherence = new Chart($("chart-adherence"), {
    type: "bar",
    data: {
      labels: weeks.map((w) => w.week_start),
      datasets: [
        { type: "bar", label: "Exercise days per week", data: weeks.map((w) => w.days) },
        { type: "line", label: "Target", data: weeks.map(() => adherence.target_days_per_week), pointRadius: 0,
          borderDash: [6, 4] },
      ],
    },
    options: { animation: false, scales: { y: { min: 0, max: 7 } } },
  });
  const box = $("sessions");
  box.replaceChildren(h("h3", "Recent sessions"));
  const ul = h("ul");
  for (const e of [...sessions].reverse()) {
    const reps = e.sets.map((s) => s.reps).join(" + ");
    const holds = e.holds.map((x) => `${x.hold_s} s`).join(", ");
    const li = h("li", `${e.date.replace("T", " ")}: sit-to-stands ${reps || "none"}; holds ${holds || "none"} `);
    if (e.simulated) li.append(h("span", "Simulated", { class: "tag" }));
    ul.append(li);
  }
  box.append(ul);
}

// ---- controls -----------------------------------------------------------------------------------
async function run(fn) {
  try {
    say("");
    await fn();
  } catch (e) {
    say(e.message);
  }
}

function profileBody() {
  const f = $("profile");
  return {
    name: f.name.value.trim(),
    age: f.age.value ? Number(f.age.value) : null,
    sex: f.sex.value || null,
    fallen: f.fallen.checked,
    unsteady: f.unsteady.checked,
    worried: f.worried.checked,
  };
}

function startSession(body) {
  return run(async () => {
    await api("POST", "/api/session", { person_id: personId, ...body });
    say("Press the button when ready.");
  });
}

$("button").onclick = () => {
  audio = audio || new AudioContext(); // browsers only allow sound after a click
  run(() => api("POST", "/api/button"));
};
$("start-checkin").onclick = () => startSession({ mode: "checkin" });
$("start-exercise").onclick = () => startSession({ mode: "exercise" });
$("start-quick").onclick = () => startSession({ mode: "exercise", plan: QUICK_PLAN });
$("arms-used").onclick = () => run(() => api("POST", "/api/stop", { reason: "arms_used" }));
$("cancel").onclick = () => run(() => api("POST", "/api/stop", { reason: "cancel" }));
$("person").onchange = (e) => {
  personId = e.target.value;
  run(loadDashboard);
};
$("profile").onsubmit = (e) => {
  e.preventDefault();
  run(async () => {
    await api("PUT", `/api/people/${encodeURIComponent(personId)}`, profileBody());
    $("profile-msg").textContent = "Saved.";
    await loadPeople();
  });
};
$("new-person").onclick = () => run(async () => {
  const p = await api("POST", "/api/people", profileBody());
  personId = p.id;
  $("profile-msg").textContent = `Created ${p.name}.`;
  await loadPeople();
});

connect();
run(loadPeople);
```

- [ ] **Step 5: Run the tests and lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: `128 passed`, then `All checks passed!`

- [ ] **Step 6: Drive a check-in and an exercise session in a browser** (Done criterion; no hardware)

Start `uv run checkin serve --source sim --base virtual`. In the Claude desktop app, use the `checkin-sim` preview config in `.claude/launch.json`, which already exists from planning. Open http://localhost:8000.

1. Sensor line reads `sim, ~100 Hz` with a Simulated tag. Person = Guest; the profile opens because age and sex are missing.
2. Set age 72 and sex Female, then **Save profile** → "Saved."
3. **Start check-in**, then click **Button** whenever a step shows `waiting` (6 presses, about 90 s in total). While steps run, the prompt, elapsed seconds, and the live chair-stand count update.
4. The check-in ends with "All done". It should show:
   - TUG about 10.4 s, dual-task TUG about 12.5 s, 12 stands, and three stances at 10 s, all `done`
   - a results table with cutoffs ("under 10 (women 70–74)") and a Simulated tag
5. **Quick exercise: 5 sit-to-stands**, then **Button** → the count rises to 5, "5 of 5 reps", and the log appears under Recent sessions.
6. Switch to **Simulated: Dad**. Check:
   - the chair chart dips to 10 against the 11 line
   - the adherence bars rise to about 5 days a week after the flag
   - every session is tagged Simulated
7. Run `uv run checkin replay data/recordings/<the new>-checkin.csv --age 72 --sex female`. Its `steps` should match the dashboard, and full stances should read `10.0`.

If the browser pane is hidden, screenshots come back blank. Read the page with `get_page_text` instead, and check the charts with `Chart.getChart(canvas).data`.

- [ ] **Step 7: Commit**

Tick task 11 in `TASKS.md`, then:

```bash
git add src/checkin/static/index.html src/checkin/static/app.js tests/test_server.py TASKS.md
git commit -m "feat: bare-bones dashboard driven entirely by the API"
```

---

### Task 12: Base station firmware

**Files:**
- Create: `firmware/base_station/base_station.ino`

**Interfaces:**
- Consumes: `firmware/PROTOCOL.md` (Task 6) and the pins in `docs/PARTS_LIST.md` Section 2. It can be written before Task 6 by copying the protocol table from there.
- Produces: 115200-baud serial.
  - Prints `READY` at boot, `PONG` in reply to `PING`, `BTN` on a debounced press, and `ERR …` for unknown commands.
  - Accepts `CUE <start|stop|done|error|rep>` and `LED <off|blue|green|amber|red>`.
  - `COMMON_ANODE` switches the LED type.

- [ ] **Step 1: Write** `firmware/base_station/base_station.ino`

```cpp
// Base station: start button, RGB LED, passive buzzer.
// Pins: docs/PARTS_LIST.md Section 2. Serial protocol and cue tones: firmware/PROTOCOL.md.

const uint8_t BUTTON_PIN = 2;  // D2 -> button -> GND, internal pull-up
const uint8_t LED_R = 9, LED_G = 6, LED_B = 5;  // each via 470 ohm; not D3/D11 (tone() uses their timer on AVR)
const uint8_t BUZZER_PIN = 8;  // via NPN transistor on an Uno R4; a small piezo can go direct on an Uno R3/Nano
const bool COMMON_ANODE = false;  // true if the LED's longest leg goes to 5V instead of GND
const unsigned long DEBOUNCE_MS = 30;

struct Note {
  uint16_t hz;  // 0 = silence
  uint16_t ms;
};
// Tune these to the buzzer's loudest frequency (usually 2-4 kHz). Keep in sync with PROTOCOL.md.
const Note CUE_START[] = {{2000, 150}, {0, 80}, {3000, 150}};
const Note CUE_STOP[] = {{1500, 600}};
const Note CUE_DONE[] = {{2093, 150}, {2637, 150}, {3136, 250}};
const Note CUE_ERROR[] = {{800, 100}, {0, 80}, {800, 100}, {0, 80}, {800, 100}};
const Note CUE_REP[] = {{2500, 80}};

String line;
bool lastPressed = false;
unsigned long lastChange = 0;

// ponytail: blocks up to 600 ms; a press shorter than a cue is missed. Make it non-blocking if that bites.
void play(const Note* notes, size_t n) {
  for (size_t i = 0; i < n; i++) {
    if (notes[i].hz) tone(BUZZER_PIN, notes[i].hz, notes[i].ms);
    delay(notes[i].ms);
  }
  noTone(BUZZER_PIN);
}
#define PLAY(cue) play(cue, sizeof(cue) / sizeof(cue[0]))

void setLed(uint8_t r, uint8_t g, uint8_t b) {
  if (COMMON_ANODE) {
    r = 255 - r;
    g = 255 - g;
    b = 255 - b;
  }
  analogWrite(LED_R, r);
  analogWrite(LED_G, g);
  analogWrite(LED_B, b);
}

void handle(const String& cmd) {
  if (cmd == "PING") Serial.println("PONG");
  else if (cmd == "CUE start") PLAY(CUE_START);
  else if (cmd == "CUE stop") PLAY(CUE_STOP);
  else if (cmd == "CUE done") PLAY(CUE_DONE);
  else if (cmd == "CUE error") PLAY(CUE_ERROR);
  else if (cmd == "CUE rep") PLAY(CUE_REP);
  else if (cmd == "LED off") setLed(0, 0, 0);
  else if (cmd == "LED blue") setLed(0, 0, 255);
  else if (cmd == "LED green") setLed(0, 255, 0);
  else if (cmd == "LED amber") setLed(255, 80, 0);
  else if (cmd == "LED red") setLed(255, 0, 0);
  else {
    Serial.print("ERR unknown command: ");
    Serial.println(cmd);
  }
}

void setup() {
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(LED_R, OUTPUT);
  pinMode(LED_G, OUTPUT);
  pinMode(LED_B, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  setLed(0, 0, 0);
  Serial.begin(115200);
  Serial.println("READY");
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      line.trim();
      if (line.length()) handle(line);
      line = "";
    } else if (line.length() < 40) {
      line += c;
    }
  }
  bool pressed = digitalRead(BUTTON_PIN) == LOW;
  if (pressed != lastPressed && millis() - lastChange > DEBOUNCE_MS) {
    lastChange = millis();
    lastPressed = pressed;
    if (pressed) Serial.println("BTN");
  }
}
```

- [ ] **Step 2: Compile for every board the team might use**

```bash
arduino-cli compile --fqbn arduino:renesas_uno:minima firmware/base_station
arduino-cli compile --fqbn arduino:avr:uno firmware/base_station
arduino-cli compile --fqbn arduino:avr:nano firmware/base_station
```

Expected: each ends with `Sketch uses … bytes` and no errors (about 44.7 KB on the R4, 6.5 KB on AVR).

- [ ] **Step 3: If an Arduino is plugged in** (skip otherwise, and say so under Found)

Upload, open `arduino-cli monitor -p <port> -c baudrate=115200`, then:
- type `PING` → `PONG`
- type `CUE start` → two rising beeps
- type `LED amber` → amber
- press the button → `BTN`

- [ ] **Step 4: Commit**

Tick task 12 in `TASKS.md`, then:

```bash
git add firmware/base_station/base_station.ino TASKS.md
git commit -m "feat: Arduino base station firmware (button, RGB LED, buzzer cues)"
```

---

### Task 13: ESP32 belt firmware

**Files:**
- Create: `firmware/esp32_imu/esp32_imu.ino`, `firmware/esp32_imu/config.h`, `firmware/esp32_imu/secrets.example.h`

**Interfaces:**
- Consumes: the UDP line format in `firmware/PROTOCOL.md` (Task 6) and the wiring in `docs/PARTS_LIST.md` Section 1.
- Produces: datagrams of 5 lines of `seq,ms,ax,ay,az,gx,gy,gz` every 50 ms.
  - Destination: `UDP_PORT` (4210), broadcast by default or unicast to `UDP_TARGET_IP`.
  - Accelerometer in g (±8 g); gyroscope in °/s (±500 °/s).
  - The sketch reads MPU-6050 registers directly: 100 Hz via `SMPLRT_DIV = 9`, 44 Hz low-pass filter, FIFO holding accel + gyro. So a clone with an unexpected WHO_AM_I only prints a warning.
  - FIFO overflow or misalignment resets the FIFO; a lost I2C chip is retried every second; the FIFO keeps draining while Wi-Fi is down.
  - `secrets.h` is git-ignored. Without it the sketch still builds from `secrets.example.h`.

- [ ] **Step 1: Write** `firmware/esp32_imu/config.h`

```cpp
#pragma once
// Belt settings. Wi-Fi name and password go in secrets.h (git-ignored): copy secrets.example.h.
#if __has_include("secrets.h")
#include "secrets.h"
#else
#include "secrets.example.h"  // placeholders: builds, but won't join Wi-Fi
#endif

#define UDP_PORT 4210    // must match `checkin serve --udp-port` (default 4210)
#define UDP_TARGET_IP "" // "" = broadcast to the network; set the laptop's IP if the hotspot drops broadcasts
#define I2C_SDA 21       // classic ESP32 defaults; ESP32-S2/S3/C3: wire any two free pins and set them here
#define I2C_SCL 22
#define MPU_ADDR 0x68    // AD0 to GND or unconnected; 0x69 if AD0 is tied high
#define BATCH_SAMPLES 5  // samples per UDP packet: 5 at 100 Hz = one packet every 50 ms
```

- [ ] **Step 2: Write** `firmware/esp32_imu/secrets.example.h`

```cpp
#pragma once
// Copy this file to secrets.h and fill it in. The belt, laptop, and tablet must share this network.
#define WIFI_SSID "your-hotspot-name"
#define WIFI_PASSWORD "your-hotspot-password"
```

- [ ] **Step 3: Write** `firmware/esp32_imu/esp32_imu.ino`

```cpp
// Belt unit: MPU-6050 at +/-8 g, +/-500 deg/s, 100 Hz through the FIFO, sent as UDP text lines.
// Wiring: docs/PARTS_LIST.md Section 1. Packet format: firmware/PROTOCOL.md. Settings: config.h.
// Talks to the chip's registers directly, so clone chips with an unexpected WHO_AM_I still work.
#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>

#include "config.h"

enum : uint8_t {
  SMPLRT_DIV = 0x19,
  CONFIG = 0x1A,
  GYRO_CONFIG = 0x1B,
  ACCEL_CONFIG = 0x1C,
  FIFO_EN = 0x23,
  INT_STATUS = 0x3A,
  USER_CTRL = 0x6A,
  PWR_MGMT_1 = 0x6B,
  FIFO_COUNTH = 0x72,
  FIFO_R_W = 0x74,
  WHO_AM_I = 0x75,
};
const float ACC_LSB_PER_G = 4096.0;   // +/-8 g
const float GYRO_LSB_PER_DPS = 65.5;  // +/-500 deg/s
const int SAMPLE_BYTES = 12;          // accel x, y, z then gyro x, y, z; big-endian int16
const uint32_t SAMPLE_MS = 10;        // 100 Hz

WiFiUDP udp;
IPAddress unicastIp;
bool unicast = false;
bool mpuReady = false;
uint32_t seq = 0;

bool writeReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

bool readRegs(uint8_t reg, uint8_t* buf, size_t n) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((uint16_t)MPU_ADDR, n) != n) return false;
  for (size_t i = 0; i < n; i++) buf[i] = Wire.read();
  return true;
}

void resetFifo() {
  writeReg(USER_CTRL, 0x04);  // FIFO_RESET
  writeReg(USER_CTRL, 0x40);  // FIFO_EN
}

bool setupMpu() {
  uint8_t who = 0;
  if (!readRegs(WHO_AM_I, &who, 1)) {
    Serial.printf("No MPU-6050 at 0x%02X: check wiring and I2C_SDA=%d, I2C_SCL=%d in config.h\n", MPU_ADDR, I2C_SDA,
                  I2C_SCL);
    return false;
  }
  if (who != 0x68) Serial.printf("WHO_AM_I is 0x%02X, not 0x68 (probably a clone); continuing\n", who);
  writeReg(PWR_MGMT_1, 0x80);  // reset the chip
  delay(100);
  bool ok = writeReg(PWR_MGMT_1, 0x01)   // wake up, clock from the X gyro
            && writeReg(CONFIG, 0x03)       // built-in low-pass filter at 44 Hz (gyro output 1 kHz)
            && writeReg(SMPLRT_DIV, 9)      // 1 kHz / (1 + 9) = 100 Hz
            && writeReg(GYRO_CONFIG, 0x08)  // +/-500 deg/s
            && writeReg(ACCEL_CONFIG, 0x10) // +/-8 g
            && writeReg(FIFO_EN, 0x78);     // accel and gyro x, y, z into the FIFO
  resetFifo();
  Serial.println(ok ? "MPU-6050 streaming at 100 Hz" : "MPU-6050 setup failed; retrying");
  return ok;
}

void connectWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // power saving delays and drops packets
  WiFi.setAutoReconnect(true);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("Joining Wi-Fi \"%s\"", WIFI_SSID);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("IP %s, sending to %s:%d\n", WiFi.localIP().toString().c_str(),
                  unicast ? UDP_TARGET_IP : "broadcast", UDP_PORT);
  } else {
    Serial.println("Wi-Fi not connected yet; will keep trying in the background");
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);
  unicast = strlen(UDP_TARGET_IP) > 0 && unicastIp.fromString(UDP_TARGET_IP);
  Wire.begin(I2C_SDA, I2C_SCL, 400000);
  connectWifi();
  mpuReady = setupMpu();
}

void loop() {
  if (!mpuReady) {
    delay(1000);
    mpuReady = setupMpu();
    return;
  }
  uint8_t status = 0, cnt[2];
  if (readRegs(INT_STATUS, &status, 1) && (status & 0x10)) {
    Serial.println("FIFO overflowed; resetting");
    resetFifo();
    return;
  }
  if (!readRegs(FIFO_COUNTH, cnt, 2)) {
    Serial.println("Lost the MPU-6050 on I2C");
    mpuReady = false;
    return;
  }
  uint16_t count = (cnt[0] << 8) | cnt[1];
  if (count % SAMPLE_BYTES) {  // out of step with sample boundaries: start clean
    resetFifo();
    return;
  }
  int n = count / SAMPLE_BYTES;
  if (n < BATCH_SAMPLES) {
    delay(2);
    return;
  }
  uint32_t now = millis();  // the newest sample in the FIFO was taken within the last 10 ms
  bool send = WiFi.status() == WL_CONNECTED;  // keep draining the FIFO even when Wi-Fi is down
  if (send) udp.beginPacket(unicast ? unicastIp : WiFi.broadcastIP(), UDP_PORT);
  for (int i = 0; i < n; i++) {
    uint8_t b[SAMPLE_BYTES];
    if (!readRegs(FIFO_R_W, b, SAMPLE_BYTES)) {
      mpuReady = false;
      break;
    }
    int16_t v[6];
    for (int k = 0; k < 6; k++) v[k] = (int16_t)((b[2 * k] << 8) | b[2 * k + 1]);
    uint32_t t = now - (uint32_t)(n - 1 - i) * SAMPLE_MS;
    if (send) {
      udp.printf("%lu,%lu,%.4f,%.4f,%.4f,%.3f,%.3f,%.3f\n", (unsigned long)seq, (unsigned long)t,
                 v[0] / ACC_LSB_PER_G, v[1] / ACC_LSB_PER_G, v[2] / ACC_LSB_PER_G, v[3] / GYRO_LSB_PER_DPS,
                 v[4] / GYRO_LSB_PER_DPS, v[5] / GYRO_LSB_PER_DPS);
    }
    seq++;
  }
  if (send) udp.endPacket();
}
```

- [ ] **Step 4: Compile for a classic ESP32 and an ESP32-S3**, without and with a `secrets.h`

```bash
arduino-cli compile --fqbn esp32:esp32:esp32 firmware/esp32_imu
arduino-cli compile --fqbn esp32:esp32:esp32s3 firmware/esp32_imu
printf '#pragma once\n#define WIFI_SSID "x"\n#define WIFI_PASSWORD "y"\n' > firmware/esp32_imu/secrets.h
arduino-cli compile --fqbn esp32:esp32:esp32 firmware/esp32_imu
rm firmware/esp32_imu/secrets.h
```

Expected: each ends with `Sketch uses … bytes` (about 915 KB, 69%). The first ESP32 compile takes a minute or two.

- [ ] **Step 5: If an ESP32 + MPU-6050 are wired** (skip otherwise, and say so under Found)

1. Create a real `secrets.h`, upload, and watch the serial monitor: expect `MPU-6050 streaming at 100 Hz`.
2. Run `nc -ul 4210` and check the lines arrive.
3. Run `uv run checkin serve --source udp --base virtual` and check the dashboard's sensor line reads about 100 Hz.

- [ ] **Step 6: Commit** (never `secrets.h`)

Tick task 13 in `TASKS.md`, then:

```bash
git add firmware/esp32_imu/esp32_imu.ino firmware/esp32_imu/config.h firmware/esp32_imu/secrets.example.h TASKS.md
git commit -m "feat: ESP32 belt firmware streaming MPU-6050 FIFO over UDP"
```

---

### Task 14: README and final verification

**Files:**
- Create: `README.md`, `.claude/launch.json`

**Interfaces:**
- Consumes: everything.
- Produces: a README covering each hardware combination (sim/virtual, UDP/virtual, UDP/serial, phyphox, CSV replay, sim/serial) plus the check-in procedure; and a desktop-app preview config.

- [ ] **Step 1: Write** `README.md`

````markdown
# Fall-risk check-in

Fall-risk screening at home with the CDC's STEADI algorithm: screen (three key questions) → assess (Timed Up and Go, dual-task TUG, 30-second chair stand, balance stances, scored by a lower-back sensor) → intervene (coached sit-to-stands and supported balance holds, counted and timed by the sensor) → track (a family dashboard with flags, change from baseline, and exercise adherence).

It flags increased fall risk and tracks change from baseline. It does not diagnose anything or say when someone will fall.

Spec: `docs/COMPETITION.md`. Wiring: `docs/PARTS_LIST.md`. API: `docs/API.md`. Device protocols: `firmware/PROTOCOL.md`.

## Quick start (no hardware)

```bash
uv sync
uv run checkin serve --source sim --base virtual
```

Open http://localhost:8000. Pick **Guest**, set age and sex in the profile, then **Start check-in** and press the on-screen **Button** at each step. The simulated sensor acts out each step when you press. Everything it produces is labelled "Simulated". **Simulated: Dad** shows eight weeks of history.

Tablet on the same network: http://LAPTOP-IP:8000 (the server listens on all interfaces; macOS asks once to allow incoming connections).

## Hardware combinations

Every device sits behind the same interface, so mix and match:

| Sensor (`--source`) | Base station (`--base`) | Use it for |
|---|---|---|
| `sim` | `virtual` | Development and a demo with no hardware |
| `udp` (ESP32 belt) | `virtual` | Belt works, Arduino not wired yet |
| `udp` (ESP32 belt) | `serial` | The full build |
| `phyphox:http://PHONE-IP:8080` | `serial` or `virtual` | Backup if the belt fails |
| `csv:data/recordings/FILE.csv` | either | Replay a real recorded session through the live dashboard |
| `sim` | `serial` | Test the Arduino on its own |

Settings are flags or environment variables, never code: `--udp-port` / `CHECKIN_UDP_PORT` (default 4210), `--serial-port` / `CHECKIN_SERIAL_PORT`, `--port` (default 8000), `--data` (default `data/`).

### 1. Simulator + on-screen base station

```bash
uv run checkin serve --source sim --base virtual
```

The page plays the buzzer tones (click the Button once so the browser allows sound) and shows the LED.

### 2. ESP32 belt (UDP)

Wiring: `docs/PARTS_LIST.md` Section 1 (MPU-6050 VCC→3V3, GND→GND, SDA→GPIO 21, SCL→GPIO 22).

```bash
cp firmware/esp32_imu/secrets.example.h firmware/esp32_imu/secrets.h   # then put in the hotspot name and password
arduino-cli compile --fqbn esp32:esp32:esp32 firmware/esp32_imu
arduino-cli board list                                                  # find the port, e.g. /dev/cu.usbserial-0001
arduino-cli upload --fqbn esp32:esp32:esp32 -p /dev/cu.usbserial-0001 firmware/esp32_imu
arduino-cli monitor -p /dev/cu.usbserial-0001 -c baudrate=115200        # expect "MPU-6050 streaming at 100 Hz"
uv run checkin serve --source udp --base virtual
```

The dashboard's sensor line should read about 100 Hz. Settings live in `firmware/esp32_imu/config.h`:

- **ESP32-S2/S3/C3 boards:** wire SDA/SCL to any two free pins and set `I2C_SDA`/`I2C_SCL`. Compile with that board's FQBN, e.g. `esp32:esp32:esp32s3`.
- **Hotspot drops broadcast packets** (sensor stuck at 0 Hz while the serial monitor says it's streaming): set `UDP_TARGET_IP` to the laptop's IP.
- **Clone chip:** a WHO_AM_I other than 0x68 is reported and ignored.
- **Other UDP port:** change `UDP_PORT` and pass the same `--udp-port`.
- **Watch raw packets:** `nc -ul 4210`.
- **"Brownout detector was triggered":** weak power; use the power bank and a short cable (`docs/PARTS_LIST.md` Section 6).

### 3. Arduino base station (USB serial)

Wiring: `docs/PARTS_LIST.md` Section 2 (button D2→GND, LED R/G/B on D9/D6/D5 via 470 Ω, buzzer on D8 via the transistor on an Uno R4). For a common-anode LED set `COMMON_ANODE = true` in the sketch.

```bash
arduino-cli compile --fqbn arduino:renesas_uno:minima firmware/base_station   # Uno R4 Minima; arduino:avr:uno or arduino:avr:nano for classic boards
arduino-cli upload --fqbn arduino:renesas_uno:minima -p /dev/cu.usbmodem1101 firmware/base_station
uv run checkin serve --source udp --base serial --serial-port /dev/cu.usbmodem1101
```

Check it by hand first: `arduino-cli monitor -p /dev/cu.usbmodem1101 -c baudrate=115200`, type `CUE start` (two beeps) and `LED amber`, and press the button (prints `BTN`). On Windows the port is `COM3` or similar.

### 4. Phone backup (phyphox)

1. Install phyphox and load `firmware/phyphox/belt-imu.phyphox` (accelerometer + gyroscope at 100 Hz). The built-in "Acceleration with g" experiment also works but has no gyroscope.
2. Menu → **Allow remote access**. phyphox shows an address like `http://192.168.1.23:8080` (port 80 on iPhones).
3. Put the phone in a belt pouch at the lower back, any orientation.

```bash
uv run checkin serve --source phyphox:http://192.168.1.23:8080 --base serial --serial-port /dev/cu.usbmodem1101
```

### 5. Replay a recording

Every session saves its raw stream to `data/recordings/`. To re-score one (for example after tuning thresholds in `src/checkin/signals.py`):

```bash
uv run checkin replay data/recordings/20260926-100516-checkin.csv --age 72 --sex female
```

Or play it back through the live dashboard, one step per button press:

```bash
uv run checkin serve --source csv:data/recordings/20260926-100516-checkin.csv --base virtual
```

## Running a check-in

1. Profile (step 0): age, sex, and the three STEADI key questions.
2. Setup per STEADI: an arm chair for the TUG, an armless ~17-inch chair for the chair stand, a 3 m taped line, a counter for balance. A family member stands by for the whole check-in.
3. **Start check-in.** At each step the helper presses the button when the person is ready. The "Go" beeps start the timing.
   - During a TUG, a press stops the clock (the stopwatch fallback if sit-down detection misses).
   - During a balance stance, a press marks the stance as broken.
   - During the chair stand, **Arms used** stops it and records 0 (STEADI).
4. Results, flags, and change from baseline appear on the dashboard. The LED shows green/amber/red.

Exercise mode (**Start exercise**) runs the person's plan: sit-to-stand sets (a beep per rep) and counter-supported balance holds. **Quick exercise** runs one set of 5 for demos.

## Development

```bash
uv run pytest            # includes a full simulated check-in scored against the simulator's true values
uv run ruff check .
uv run checkin seed      # rewrite the "Simulated: Dad" history so it ends today
```

Scoring thresholds are named constants at the top of `src/checkin/signals.py`; tune them on real recordings with `checkin replay`.
````

- [ ] **Step 2: Confirm** `.claude/launch.json` (created during planning) reads exactly:

```json
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "checkin-sim",
      "runtimeExecutable": "uv",
      "runtimeArgs": ["run", "checkin", "serve", "--source", "sim", "--base", "virtual"],
      "port": 8000
    }
  ]
}
```

- [ ] **Step 3: Verify every Done criterion from a clean tree**

```bash
rm -rf .venv data && uv sync
uv run pytest
uv run ruff check .
arduino-cli compile --fqbn arduino:renesas_uno:minima firmware/base_station
arduino-cli compile --fqbn esp32:esp32:esp32 firmware/esp32_imu
```

Expected:
- `128 passed`, including `test_full_simulated_checkin_matches_the_simulator` and `test_exercise_session_counts_reps_and_times_holds`
- `All checks passed!`
- both sketches report `Sketch uses …`

Then repeat Task 11 Step 6 (browser check-in, quick exercise, and `checkin replay` on the new recording).

- [ ] **Step 4: Commit**

Tick task 14 in `TASKS.md`, then:

```bash
git add README.md .claude/launch.json TASKS.md
git commit -m "docs: README for every hardware combination; preview config"
```

- [ ] **Step 5: Report** with the three headings from CLAUDE.md.

Under **Found**, mark each adapter that wasn't tested against real hardware and say what was tested instead:
- **`UdpSource`:** loopback UDP datagrams in the PROTOCOL.md format, including a garbage line, a sequence gap, and batched timestamps. No real ESP32.
- **`PhyphoxSource`** and `belt-imu.phyphox`: a stubbed fetch returning phyphox's documented `/get` JSON, plus an accelerometer-only reply. The experiment file was only checked as XML; it was never loaded on a phone.
- **`SerialBase`:** a fake port covering split lines, `\r\n`, `READY`/`PONG`, and unplugging mid-session. No real Arduino.
- **`base_station.ino` and `esp32_imu.ino`:** compile-only (unless Task 12 Step 3 and Task 13 Step 5 ran on hardware).
- **Scoring thresholds:** tuned on the simulator only. They need real recordings (`checkin replay`) before judging.

Also list:
- The Decisions section above, if the user hasn't confirmed it.
- Slow walkers: the simulator's worst TUG error is −0.6 s on a 25 s dual-task TUG at 0.6 m/s (2.4%, within the published 4% IMU agreement).
