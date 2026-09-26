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
    # No break seen and the data reaches t_end (short tail gaps allowed, as mid-stance): held to the end.
    # Trade-off: a break inside a lost tail of <= MAX_GAP_S goes unseen, instead of every lost tail reading
    # as a short hold and a false balance flag. Longer gaps are "not measured" (data_error).
    stop = t[idx[0]] if len(idx) else (t_end if t[-1] >= t_end - MAX_GAP_S else t[-1])
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
