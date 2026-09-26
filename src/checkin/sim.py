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
