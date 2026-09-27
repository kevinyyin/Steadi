"""Belt vs hand ground truth: pair each recorded step with a stopwatch time or hand count, and measure agreement.

Ground truth is a CSV next to the recordings (docs/VALIDATION.md):
    recording,step,truth,person,who,notes
    20260927-101500-checkin.csv,tug,11.84,allen,kevin stopwatch,
The belt value is always re-scored from the raw recording (`checkin replay`), never typed in by hand.
"""

import csv
from pathlib import Path

import numpy as np

from . import sim, steadi
from .controller import BALANCE_S
from .store import read_recording, write_recording

FIELDS = ["recording", "step", "truth", "person", "who", "notes"]

# measure id -> (label, what the belt reports, unit, "time" or "count")
MEASURES = {
    "tug": ("Timed Up and Go", "tug_s", "s", "time"),
    "dual_tug": ("Dual-task Timed Up and Go", "tug_s", "s", "time"),
    "chair_stand": ("30-second chair stand", "stands", "stands", "count"),
    "sit_to_stand": ("Sit-to-stand reps (exercise)", "reps", "reps", "count"),
    "balance": ("Balance hold", "hold_s", "s", "time"),
}
TOL = {"time": 1.0, "count": 1}  # "within tolerance" = |belt - truth| <= this; override with --tol-time/--tol-count


def measure_of(step):
    kind = step.split("#")[0]
    if kind.startswith(("balance_", "hold_")):
        return "balance"
    return kind if kind in MEASURES else None


def cutoff_of(step):
    """(STEADI cutoff, True if at-or-above the cutoff is the flagged side) for steps that have one."""
    kind = step.split("#")[0]
    if kind == "tug":
        return steadi.TUG_CUTOFF_S, True
    if kind == "balance_tandem":
        return steadi.TANDEM_CUTOFF_S, False
    return None


def read_truth(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as f:  # Excel's "CSV UTF-8" starts with a BOM
        rows = list(csv.DictReader(f))
    if rows and {"recording", "step", "truth"} - set(rows[0]):
        raise SystemExit(f"{path}: needs columns {','.join(FIELDS)}")
    return rows


def write_template(recordings, out):
    """Append a blank row for every tagged step in `recordings/*.csv` not already in `out`. Returns rows added.

    No belt values go in the template: whoever types the stopwatch number shouldn't see the belt's first.
    """
    out = Path(out)
    have = {(r["recording"], r["step"]) for r in read_truth(out)} if out.exists() else set()
    new = []
    for path in sorted(Path(recordings).glob("*.csv")):
        try:
            rec = read_recording(path)
        except ValueError:
            continue
        for sid, _ in sorted(rec.steps.items(), key=lambda kv: kv[1][0]):
            if measure_of(sid) and (path.name, sid) not in have:
                new.append({"recording": path.name, "step": sid, "truth": "", "person": "", "who": "",
                            "notes": "simulated" if rec.simulated else ""})
    out.parent.mkdir(parents=True, exist_ok=True)
    fresh = not out.exists() or out.stat().st_size == 0
    with out.open("a", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        if fresh:
            w.writeheader()
        w.writerows(new)
    return len(new)


def _find(name, truth_path, recordings):
    here = Path(truth_path).parent
    for base in (here, here / "recordings", Path(recordings) if recordings else None):
        if base is not None and (base / name).exists():
            return base / name
    if Path(name).exists():
        return Path(name)
    raise SystemExit(f"recording {name!r} not found next to {truth_path} or in {recordings}")


def pair(truth_path, recordings=None):
    """One dict per ground-truth row with a number in `truth`: the belt's re-scored value next to it."""
    from .cli import replay

    scored, out = {}, []
    for i, row in enumerate(read_truth(truth_path), start=2):
        row["step"] = row["step"].strip()
        text = (row.get("truth") or "").strip()
        measure = measure_of(row["step"])
        if not text or measure is None:
            continue
        try:
            truth = float(text)
        except ValueError:
            raise SystemExit(f"{truth_path} row {i}: truth {text!r} isn't a number") from None
        name = row["recording"].strip()
        if name not in scored:
            path = _find(name, truth_path, recordings)
            scored[name] = replay(path)
        rec = scored[name]
        label, key, unit, kind = MEASURES[measure]
        result = rec["steps"].get(row["step"])
        if result is None:
            why = "step not in recording"
        elif "error" in result:
            why = result["error"]
        elif result.get("method") == "window end":  # the helper's button ended it: that's a stopwatch, not the belt
            why = "belt didn't detect the sit-down"
        elif (row["step"].startswith("balance_") and result.get("broke") is False
              and result["hold_s"] < BALANCE_S - 0.05):
            why = "ended by the button"  # the helper stopped the stance: human timing, not the belt
        else:
            why = None
        belt = None if why else float(result[key])
        out.append({
            "recording": name, "step": row["step"], "measure": measure, "person": (row.get("person") or "").strip(),
            "who": (row.get("who") or "").strip(), "notes": (row.get("notes") or "").strip(),
            "truth": truth, "belt": belt, "diff": None if belt is None else round(belt - truth, 3),
            "not_scored": why,
            "simulated": bool(rec["simulated"]) or "simulated" in (row.get("notes") or "").lower(),
        })
    return out


def agreement(pairs, tol, kind):
    """Agreement stats for one measure's scored pairs (belt minus truth)."""
    d = np.array([p["diff"] for p in pairs], float)
    truth = np.array([p["truth"] for p in pairs], float)
    n = len(d)
    if n == 0:
        return {"n": 0}
    bias = float(d.mean())
    sd = float(d.std(ddof=1)) if n > 1 else 0.0
    out = {
        "n": n, "bias": round(bias, 3), "sd": round(sd, 3),
        "loa": [round(bias - 1.96 * sd, 3), round(bias + 1.96 * sd, 3)],
        "mae": round(float(np.abs(d).mean()), 3), "tol": tol,
        "within": int((np.abs(d) <= tol + 1e-9).sum()),
        "truth_mean": round(float(truth.mean()), 3),
    }
    if kind == "count":
        out["exact"] = int((d == 0).sum())
    else:
        pos = truth > 0
        out["mae_pct"] = round(float((np.abs(d[pos]) / truth[pos]).mean() * 100), 1) if pos.any() else None
    same = [p for p in pairs if cutoff_of(p["step"])]
    if same:
        agree = 0
        for p in same:
            cut, high = cutoff_of(p["step"])
            agree += (p["belt"] >= cut) == (p["truth"] >= cut) if high else (p["belt"] < cut) == (p["truth"] < cut)
        out["cutoff"] = {"n": len(same), "agree": int(agree),
                         "what": "12 s TUG cutoff" if same[0]["step"] == "tug" else "10 s tandem cutoff"}
    return out


def summarize(pairs, tol_time=TOL["time"], tol_count=TOL["count"]):
    """Per-measure stats, in MEASURES order, for the measures that have any ground truth."""
    out = {}
    for m, (label, _, unit, kind) in MEASURES.items():
        rows = [p for p in pairs if p["measure"] == m]
        if not rows:
            continue
        scored = [p for p in rows if p["belt"] is not None]
        stats = agreement(scored, tol_time if kind == "time" else tol_count, kind)
        stats.update(label=label, unit=unit, kind=kind, not_scored=len(rows) - len(scored),
                     people=len({p["person"] for p in rows if p["person"]}))
        out[m] = stats
    return out


# ---- a simulated set, to prove the report end to end before real recordings exist ------------------------

SIM_PEOPLE = [  # walk speed m/s, stand cycle s, semi-tandem and tandem hold s (60 = held the full 10 s)
    ("sim-a", 1.30, 2.3, 60, 60), ("sim-b", 1.05, 2.8, 60, 7.5), ("sim-c", 0.85, 3.4, 8.0, 3.5),
    ("sim-d", 1.20, 2.5, 60, 60), ("sim-e", 0.70, 3.9, 6.5, 2.0), ("sim-f", 0.95, 3.0, 60, 5.0),
]


def _session(steps, seed):
    """Concatenate simulated steps into one recording: (data, tags, truths)."""
    rows, tags, truths, offset = [], [], {}, 0.0
    for i, (sid, kind, p, kw, window) in enumerate(steps):
        t, acc, gyro, truth = sim.simulate(kind, p, seed=seed + i, **kw)
        t = t + offset
        go = offset
        end = go + window if window else t[-1]
        rows.append(np.column_stack([t, acc, gyro]))
        tags.append((sid, go, float(end)))
        truths[sid] = truth
        offset = float(t[-1]) + 3.0
    return np.vstack(rows), tags, truths


def make_simulated(out_dir, seed=0):
    """Simulated recordings plus made-up hand ground truth (stopwatch lag, the odd miscount), all labelled.

    Writes out_dir/recordings/*.csv and out_dir/ground_truth.csv; returns the ground-truth path.
    """
    out_dir = Path(out_dir)
    (out_dir / "recordings").mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    rows = []

    def stopwatch(v, cap=None):
        v = v + rng.normal(0.12, 0.18)  # reaction time on start and stop
        return round(min(v, cap) if cap else v, 2)

    def hand_count(v):
        return int(v + (rng.choice([-1, 1]) if rng.random() < 0.08 else 0))

    for k, (pid, speed, cycle, semi, tandem) in enumerate(SIM_PEOPLE):
        holds = {"feet_together": 60.0, "semi_tandem": semi, "tandem": tandem}
        for trial in range(2):
            p = sim.SimParams(walk_speed=speed * (1 + rng.normal(0, 0.04)), stand_cycle_s=cycle,
                              hold_s={s: (h if h >= 60 else h + rng.normal(0, 0.8)) for s, h in holds.items()},
                              mount_deg=tuple(rng.normal(0, 6, 3)))
            steps = [("tug", "tug", p, {}, None), ("dual_tug", "dual_tug", p, {}, None),
                     ("chair_stand", "chair_stand", p, {}, 30.0)]
            steps += [(f"balance_{s}", f"balance_{s}", p, {}, 10.0) for s in sim.STANCES]
            steps += [(f"sit_to_stand#{j + 1}", "sit_to_stand", p, {"reps": int(rng.integers(5, 11))}, None)
                      for j in range(2)]
            data, tags, truths = _session(steps, seed=seed + 100 * k + 10 * trial)
            name = f"2026092{7 + trial}-10{k}000-simulated.csv"
            write_recording(out_dir / "recordings" / name, data, tags, "sim", True)
            for sid, truth in truths.items():
                if "tug_s" in truth:
                    v = stopwatch(truth["tug_s"])
                elif "hold_s" in truth:
                    v = stopwatch(truth["hold_s"], cap=10.0)
                else:
                    v = hand_count(truth.get("stands", truth.get("reps")))
                rows.append({"recording": name, "step": sid, "truth": v, "person": pid, "who": "made up",
                             "notes": "simulated"})
    path = out_dir / "ground_truth.csv"
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)
    return path
