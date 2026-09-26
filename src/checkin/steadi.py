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
