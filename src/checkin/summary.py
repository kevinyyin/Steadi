"""Summaries of one person's dashboard: an exact one for the doctor, a plain-language one for the family.

The doctor summary is built only from the recorded numbers. The family summary is written by an OpenAI
model from that same text (no name sent), and is used only if it passes the checks below; otherwise, or
with no key or no internet, the family gets a fixed-template summary. Settings: OPENAI_API_KEY,
CHECKIN_OPENAI_MODEL.
"""

import json
import logging
import os
import re
import urllib.request
from datetime import datetime

from . import steadi

log = logging.getLogger(__name__)
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"
TIMEOUT_S = 20
NUMBER = re.compile(r"\d+(?:\.\d+)?")
# Claims we never make (CLAUDE.md): diagnosis, predicting a fall, guaranteed prevention, medical advice.
FORBIDDEN = re.compile(
    r"diagnos|predict|will (?:likely |probably )?fall|going to fall|guarantee|prevents? (?:all |any )?falls"
    r"|medicat|prescri|dosage",
    re.IGNORECASE,
)
FAMILY_NOTE = "This is fall-risk screening, not a diagnosis. A doctor can do a full fall-risk assessment."
SYSTEM = (
    "You write a short update for the family of an older adult who does a weekly fall-risk screening at home "
    "with the CDC's STEADI tests. Write 3 to 5 plain sentences a non-expert can follow: how the latest "
    "check-in went, any change from their usual results, and how the exercises are going. Use everyday words "
    "(the walk test, the chair test, the balance test) and never write STEADI, TUG, tandem, sway, baseline, or "
    "dual-task. Write dates as month and day, like September 26. Use only facts and numbers from the summary "
    "you are given, and no other numbers. Say 'flags increased fall risk' for a flag. Never diagnose, predict "
    "whether or when someone will fall, promise that falls will be prevented, or give medical or medication "
    "advice. If anything is flagged, suggest mentioning it at the next doctor's visit."
)


def _num(v, unit=""):
    return "not measured" if v is None else f"{round(v, 1):g}{unit}"


def _change(changes, key, unit=""):
    c = (changes or {}).get(key)
    if not c:
        return ""
    sign = "+" if c["change"] > 0 else ""
    return f"; baseline {_num(c['baseline'], unit)}, change {sign}{_num(c['change'], unit)}"


def doctor(dash):
    """Plain-text STEADI summary from the recorded numbers only. No name, so it can be shared as is."""
    person, latest = dash["person"], dash["latest"]
    p = person["profile"]
    lines = ["Fall-risk screening summary: CDC STEADI tests done at home, scored by a lower-back motion sensor."]
    if person["simulated"]:
        lines.append("SIMULATED DATA: not a real person.")
    elif any(dash["trends"]["simulated"]):
        lines.append("SIMULATED DATA: some check-ins are simulated, not measured by a sensor.")
    lines.append(f"Age {p.get('age') or 'not given'}, {p.get('sex') or 'sex not given'}.")
    if not latest:
        return "\n".join(lines + ["No check-ins yet."])

    dates = dash["trends"]["dates"]
    lines.append(f"{len(dates)} check-in{'s' if len(dates) != 1 else ''}, {dates[0]} to {dates[-1]}.")
    kq = latest.get("key_questions") or {k: p.get(k) for k in steadi.KEY_QUESTIONS}
    yes = [text for k, text in steadi.KEY_QUESTIONS.items() if kq.get(k)]
    lines.append("Key questions: " + ("yes to: " + "; ".join(yes) + "." if yes else "no to all three."))

    m, cut, ch = latest["metrics"], latest["cutoffs"], latest.get("changes")
    flags = [f["text"] for f in latest["flags"]]
    lines += [
        "",
        f"Latest check-in, {latest['date'][:10]}: "
        + ("flags increased fall risk: " + "; ".join(flags) + "." if flags else "no STEADI flags."),
        f"- Timed Up and Go: {_num(m['tug_s'], ' s')} (flags at {_num(cut['tug_s'], ' s')} or more"
        f"{_change(ch, 'tug_s', ' s')})",
        f"- Timed Up and Go while naming animals: {_num(m['dual_tug_s'], ' s')}; dual-task cost "
        f"{_num(m['dual_task_cost_pct'], '%')}{_change(ch, 'dual_task_cost_pct', ' points')}",
        f"- 30-second chair stand: {_num(m['chair_stands'])} stands (below {cut['chair_stands']} is below average "
        f"for {cut['chair_label']}{_change(ch, 'chair_stands')})",
        f"- Balance stances held (target 10 s): feet together {_num(m['feet_together_s'], ' s')}, "
        f"semi-tandem {_num(m['semi_tandem_s'], ' s')}, tandem {_num(m['tandem_s'], ' s')} "
        f"(tandem under {_num(cut['tandem_s'], ' s')} flags{_change(ch, 'tandem_s', ' s')})",
    ]
    declines = [d["text"] for d in latest.get("declines", [])]
    lines.append("Sustained declines from baseline: " + ("; ".join(declines) + "." if declines else "none."))

    over = []
    for key, (label, unit, worse, *_) in steadi.TRACKED.items():
        pts = [(v, d) for v, d in zip(dash["trends"]["series"][key], dates, strict=True) if v is not None]
        if len(pts) >= 2:
            u = unit if unit in ("", "%") else " " + unit
            (first, _), (low, when), (last, _) = pts[0], max(pts, key=lambda p: p[0] * worse), pts[-1]
            over.append(f"{label} first {_num(first, u)}, worst {_num(low, u)} ({when}), latest {_num(last, u)}")
    if over:
        lines.append("Over time: " + "; ".join(over) + ".")

    a, plan = dash["adherence"], dash["plan"]
    sts, bal = plan["sit_to_stand"], plan["balance"]
    lines += [
        "",
        f"Exercise: {a['last_7_days']} of the target {a['target_days_per_week']} days in the last 7 days. Plan: "
        f"{sts['sets']} sets of {sts['reps']} sit-to-stands, {bal['holds']} supported "
        f"{steadi.STANCE_LABEL[bal['stance']]} holds of {_num(bal['target_s'], ' s')}.",
        "",
        "This is fall-risk screening: it flags increased fall risk and tracks change from baseline. "
        "It does not diagnose. A doctor can do a full fall-risk assessment.",
    ]
    return "\n".join(lines)


def template(dash):
    """Family summary with no AI: the saved alert text, or an all-clear, plus exercise."""
    latest, a = dash["latest"], dash["adherence"]
    if not latest:
        return "No check-in yet."
    d = datetime.fromisoformat(latest["date"])
    when = f"{d:%A}, {d:%B} {d.day}"  # "Saturday, September 26"
    if latest["alert"]:
        al = latest["alert"]
        parts = [f"The check-in on {when} flags increased fall risk: " + "; ".join(al["items"]) + ".", al["advice"]]
    else:
        parts = [f"The check-in on {when} raised no flags."]
    parts.append(f"Exercises done on {a['last_7_days']} of the target {a['target_days_per_week']} days this week.")
    parts.append(FAMILY_NOTE)
    return " ".join(parts)


def check(text, facts):
    """Why an AI summary can't be shown, or None: a forbidden claim, or a number not in the facts."""
    if FORBIDDEN.search(text):
        return "forbidden claim"
    allowed = {float(n) for n in NUMBER.findall(facts)}
    invented = [n for n in NUMBER.findall(text) if float(n) not in allowed]
    return f"numbers not in the data: {', '.join(invented)}" if invented else None


def openai_ask(system, user):
    """The model's reply, or None with no API key. Raises on network or API errors."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return None
    body = {
        "model": os.environ.get("CHECKIN_OPENAI_MODEL", DEFAULT_MODEL),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        OPENAI_URL, json.dumps(body).encode(), {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()


def summaries(dash, ask=openai_ask):
    """{"doctor", "family", "family_by": "ai" | "template", "simulated"}."""
    facts = doctor(dash)
    family, by = template(dash), "template"
    if dash["latest"]:
        try:
            text = ask(SYSTEM, facts)
        except Exception as e:  # offline, bad key, rate limit, odd reply: the template still works
            log.warning("AI summary unavailable: %s", e)
            text = None
        problem = text and check(text, facts)
        if problem:
            log.warning("AI summary rejected (%s): %s", problem, text)
        elif text:
            family, by = text, "ai"
    simulated = dash["person"]["simulated"] or any(dash["trends"]["simulated"])
    if simulated:
        family = "Simulated data. " + family
    return {"doctor": facts, "family": family, "family_by": by, "simulated": simulated}
