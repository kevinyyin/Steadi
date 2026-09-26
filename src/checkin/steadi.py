"""STEADI screening logic: cutoffs, flags, fall-risk level, change from baseline, exercise plan, adherence.

Wording rule (docs/COMPETITION.md Section 4): "flags increased fall risk", "change from baseline".
Never "diagnose", "predict", or "prevent" in anything shown to people.
"""

from datetime import date, timedelta
from statistics import mean

TUG_CUTOFF_S = 12.0  # STEADI: 12 s or more flags
TUG_TIMEOUT_S = 60.0  # a walk not finished by then is flagged, not "not measured"
CORE = ("tug_s", "chair_stands", "tandem_s")  # a check-in missing any of these can't be called clear
TANDEM_CUTOFF_S = 10.0  # STEADI: tandem stance held under 10 s flags
STANCES = ("feet_together", "semi_tandem", "tandem")
STANCE_LABEL = {"feet_together": "feet together", "semi_tandem": "semi-tandem", "tandem": "tandem"}
STANCE_WORDS = {  # what the family and the person see: no stance names
    "feet_together": "feet together",
    "semi_tandem": "one foot a little ahead of the other",
    "tandem": "one foot right in front of the other",
}

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
NOTE = "Fall-risk screening with the CDC's STEADI tests. A doctor can do a full fall-risk assessment."
KEY_QUESTIONS = {
    "fallen": "fallen in the past year",
    "unsteady": "feels unsteady when standing or walking",
    "worried": "worries about falling",
}
EXERCISE_REPS = 8  # starting reps per sit-to-stand set
MAX_REPS = 10  # Section 5: sets of 5–10
CHAIR_LOW_MARGIN = 2  # chair stands under the STEADI line + this count as "low" for the plan
EXERCISE_HOLD_S = 20.0
TARGET_DAYS_PER_WEEK = 5  # "exercises most days"
PROGRESS_MIN_DAYS = 3  # reps and stance move up only after this many exercise days in the last 7


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


def fmt(v, unit, change=False):
    """One number format for screen text and print: 12.4 s, 18.4%, 13; a change in a percentage is in points."""
    if change and unit == "%":
        unit = " points"
    elif unit and unit != "%":
        unit = " " + unit
    return f"{'+' if change and v > 0 else ''}{round(v, 1):g}{unit}"


def unmeasured(m):
    """The core tests with no value. A walk that timed out is flagged instead, so it isn't listed."""
    return [k for k in CORE if m.get(k) is None and not (k == "tug_s" and m.get("tug_timed_out"))]


def metrics_from_steps(steps):
    """Flatten step results (keyed by step id) into the tracked metrics."""
    tug = (steps.get("tug") or {}).get("tug_s")
    dual = (steps.get("dual_tug") or {}).get("tug_s")
    m = {
        "tug_s": tug,
        "dual_tug_s": dual,
        "dual_task_cost_pct": round((dual - tug) / tug * 100, 1) if tug and dual else None,
        "chair_stands": (steps.get("chair_stand") or {}).get("stands"),
        "tug_timed_out": (steps.get("tug") or {}).get("method") == "timeout" and "error" not in steps["tug"],
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
    if m.get("tug_timed_out"):
        flags.append({"id": "tug", "text": f"Timed Up and Go not finished within {TUG_TIMEOUT_S:g} s "
                                           "(STEADI flags 12 s or more)"})
    elif m.get("tug_s") is not None and m["tug_s"] >= TUG_CUTOFF_S:
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
        # Name the stance that broke: after it the check-in stops, and later stances count as 0 s.
        broke = next(s for s in STANCES if m.get(f"{s}_s") is not None and m[f"{s}_s"] < TANDEM_CUTOFF_S)
        held = f"Held the {STANCE_LABEL[broke]} stance {m[f'{broke}_s']:.1f} s"
        flags.append({"id": "balance", "text": (held if broke == "tandem" else f"{held}, so tandem wasn't tried")
                      + " (STEADI flags tandem under 10 s)"})
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
                    f"(baseline {fmt(ch['baseline'], unit)}, change {fmt(ch['change'], unit, change=True)})",
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
        "note": NOTE,
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


def _days_in_last_week(logs, today):
    return len({lg["date"][:10] for lg in logs if (today - date.fromisoformat(lg["date"][:10])).days < 7})


def next_stance(logs, progress=True):
    """Supported-balance progression: move up a stance once every hold at the current one hits its target."""
    for log in reversed(logs):
        holds = [h for h in log.get("holds") or [] if h.get("hold_s") is not None]  # skip holds not measured
        if holds:
            stance = holds[0]["stance"]
            if progress and all(h["hold_s"] >= h["target_s"] for h in holds):
                return STANCES[min(STANCES.index(stance) + 1, len(STANCES) - 1)]
            return stance
    return STANCES[0]


def next_reps(logs, progress=True):
    """Sit-to-stand progression: one more rep per set (up to MAX_REPS) once every set of the latest session hit
    its target. Sessions shorter than the starting reps (the 5-rep demo) and unmeasured sets are ignored."""
    for log in reversed(logs):
        sets = [s for s in log.get("sets") or [] if s.get("reps") is not None and s.get("target", 0) >= EXERCISE_REPS]
        if sets:
            target = sets[0]["target"]
            if progress and all(s["reps"] >= s["target"] for s in sets):
                target += 1
            return min(target, MAX_REPS)  # a longer session sent through the API still plans at most 10
    return EXERCISE_REPS


def _near_line(checkin):
    m, cut = checkin["metrics"], checkin["cutoffs"].get("chair_stands")
    return cut is not None and m["chair_stands"] < cut + CHAIR_LOW_MARGIN


def _balance_flag(checkin):
    return "balance" in {f["id"] for f in checkin["flags"]}


def _low_twice(checkins, key, low):
    """(low in the latest result, low in the two latest results) for one metric. Check-ins that didn't
    measure it (belt dropout) are skipped: "not measured" is neither low nor fine."""
    measured = [c for c in reversed(checkins) if c["metrics"].get(key) is not None][:2]
    now = bool(measured) and low(measured[0])
    return now, now and len(measured) == 2 and low(measured[1])


def make_plan(person, today=None):
    """Exercise plan leaning on the weakest area (Section 5).

    Weak areas count only when they show up two check-ins in a row, so one bad day doesn't change the plan:
    - Chair stands at or near the STEADI line, or slipping below their baseline: 3 sets.
    - A balance flag, or the tandem stance slipping below its baseline: 4 holds.
    - Reps and stance move up once every set or hold hit its target, but only with regular practice
      (PROGRESS_MIN_DAYS exercise days in the last 7); otherwise the plan stays at the same level.
    """
    today = today or date.today()
    logs = person["exercise"]
    checkins = person["checkins"]
    latest = checkins[-1] if checkins else None
    chair_low = balance_low = False
    why = "no check-in yet: the standard sets and holds"
    if latest:
        declining = {d["id"] for d in latest.get("declines", [])}  # already two check-ins in a row
        now_chair, near_line = _low_twice(checkins, "chair_stands", _near_line)
        now_balance, balance_flag = _low_twice(checkins, "tandem_s", _balance_flag)
        chair_low = near_line or "chair_stands" in declining
        balance_low = balance_flag or "tandem_s" in declining
        watching = [text for on, text in [
            (now_chair and not chair_low, "chair stands at or near the STEADI line"),
            (now_balance and not balance_low, "the tandem stance under 10 s"),
        ] if on]
        reasons = [
            (near_line, "more sit-to-stands: chair stands at or near the STEADI line two check-ins in a row"),
            (chair_low and not near_line, "more sit-to-stands: chair stands have slipped below their baseline"),
            (balance_flag, "more balance holds: the tandem stance under 10 s two check-ins in a row"),
            (balance_low and not balance_flag, "more balance holds: the tandem stance has slipped below its baseline"),
            (watching, f"{' and '.join(watching)} in the latest result: "
                       "the plan adds more if the next check-in shows the same"),
        ]
        why = ("; ".join(text for on, text in reasons if on)
               or "no weak area in the latest check-in: the standard sets and holds")
    days = _days_in_last_week(logs, today)
    progress = days >= PROGRESS_MIN_DAYS
    reps, stance = next_reps(logs, progress), next_stance(logs, progress)
    if (reps, stance) != (next_reps(logs), next_stance(logs)):  # it would move up, but practice has been patchy
        why += (f"; holding at this level until there are {PROGRESS_MIN_DAYS} exercise days in a week "
                f"({days} in the last 7)")
    return {
        "sit_to_stand": {"sets": 3 if chair_low else 2, "reps": reps},
        "balance": {"stance": stance, "holds": 4 if balance_low else 2, "target_s": EXERCISE_HOLD_S},
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
                # a set or hold whose sensor data dropped out has no count: it adds nothing
                "reps": sum(s.get("reps") or 0 for lg in week for s in lg["sets"]),
                "hold_s": round(sum(h.get("hold_s") or 0.0 for lg in week for h in lg["holds"]), 1),
                "simulated": any(lg.get("simulated") for lg in week),
            }
        )
    return {"target_days_per_week": TARGET_DAYS_PER_WEEK, "weeks": out, "last_7_days": _days_in_last_week(logs, today)}


def trends(person):
    """Per-metric series for charts, with the STEADI cutoff where one exists."""
    cs = person["checkins"]
    series = {k: [c["metrics"].get(k) for c in cs] for k in TRACKED}
    latest_cut = cs[-1]["cutoffs"] if cs else {}
    return {
        "dates": [c["date"][:10] for c in cs],
        "levels": [c["level"] for c in cs],
        "flags": [[f["id"] for f in c["flags"]] for c in cs],
        "declines": [[d["id"] for d in c.get("declines", [])] for c in cs],
        "partial": [bool(unmeasured(c["metrics"])) for c in cs],  # a core test missing: not "clear"
        "simulated": [bool(c.get("simulated")) for c in cs],
        "series": series,
        "baseline": {k: [((c.get("changes") or {}).get(k) or {}).get("baseline") for c in cs] for k in TRACKED},
        "stances_held": [stances_held(c["metrics"]) for c in cs],
        "cutoffs": {k: latest_cut.get(k) for k in ("tug_s", "chair_stands", "chair_label", "tandem_s")},
    }


def stances_held(m):
    """How far up the balance ladder a check-in got: 0–3 stances held for 10 s in order, or None if not measured.
    The tandem stance is capped at its own cutoff, so this carries more than a chart of tandem seconds."""
    held = 0
    for s in STANCES:
        v = m.get(f"{s}_s")
        if v is None:
            return None if held == 0 else held
        if v < TANDEM_CUTOFF_S:
            break
        held += 1
    return held


def dashboard(person, today):
    """Everything the family dashboard shows for one person."""
    latest = person["checkins"][-1] if person["checkins"] else None
    return {
        "person": {k: person[k] for k in ("id", "name", "simulated", "profile")},
        "latest": latest,
        "level": latest["level"] if latest else None,
        "alert": latest["alert"] if latest else None,
        "trends": trends(person),
        "plan": make_plan(person, today),
        "adherence": adherence(person["exercise"], today),
        "exercise": person["exercise"][-10:],
    }
