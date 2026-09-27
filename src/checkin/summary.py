"""Summaries of one person's dashboard: an exact one for the doctor, a plain-language one for the family.

The doctor summary is built only from the recorded numbers. The family summary is written by a Grok
model from that same text (no name sent), and is used only if it passes the checks below; otherwise, or
with no key or no internet, the family gets a fixed-template summary. Ask Steady answers the family's
questions from the same text under the same checks. Settings: XAI_API_KEY, CHECKIN_GROK_MODEL, CHECKIN_AI
(see ai.py).
"""

import json
import logging
import os
import re
import urllib.request
from datetime import datetime

from . import ai, steadi

log = logging.getLogger(__name__)
GROK_URL = "https://api.x.ai/v1/chat/completions"
DEFAULT_MODEL = "grok-4.3"
TIMEOUT_S = 20
NUMBER = re.compile(r"\d+(?:\.\d+)?")
# Claims we never make (CLAUDE.md): diagnosis, predicting a fall, guaranteed prevention, medical advice.
FORBIDDEN = re.compile(
    r"diagnos|predict|will (?:likely |probably )?fall|going to fall|guarantee|prevents? (?:all |any )?falls"
    r"|(?:un)?likely to fall|won.t fall|will not fall|never fall|safe from fall"
    r"|medicat|prescri|dosage"
    r"|\bhealthy\b|low risk|risk (?:of falling )?is low|stop using|(?:no|doesn.t|does not) need (?:to see )?a doctor",
    re.IGNORECASE,
)
# Words the family never sees (CLAUDE.md): an AI summary using them falls back to the template.
JARGON = re.compile(r"STEADI|\bTUG\b|timed up|tandem|sway|baseline|dual.task", re.IGNORECASE)
FAMILY_NOTE = "This is fall-risk screening, not a diagnosis. A doctor can do a full fall-risk assessment."
# The Home cards' plain words, so the family summary matches the page.
AREA = {"tug_s": "standing up and walking", "chair_stands": "leg strength", "tandem_s": "balance",
        "dual_task_cost_pct": "walking while naming animals"}
YES = {"fallen": "has had a fall in the past year", "unsteady": "feels unsteady when standing or walking",
       "worried": "worries about falling"}
SYSTEM = (
    "You write a short update for the family of an older adult who does a weekly fall-risk screening at home "
    "with the CDC's STEADI tests. Write 3 to 5 plain sentences a non-expert can follow: how the latest "
    "check-in went, any change from their usual results, and how the exercises are going. Use the family's "
    "words (standing up and walking, leg strength, balance) and never write STEADI, Timed Up and Go, TUG, tandem, "
    "sway, baseline, or dual-task. Write dates as month and day, like September 26. Use only facts and numbers "
    "from the summary you are given, and no other numbers. Say 'flags increased fall risk' for a flag. Never "
    "diagnose, predict whether or when someone will fall, promise that falls will be prevented, or give medical "
    "or medication advice. If anything is flagged, suggest mentioning it at the next doctor's visit."
)
ASK_SYSTEM = (
    "You answer a family member's question about an older adult's weekly fall-risk screening at home. Answer "
    "in 1 to 3 plain sentences, using only facts and numbers from the check-in results you are given, and no "
    "other numbers. If the results don't answer the question, say so. Use the family's words (standing up and "
    "walking, leg strength, balance) and never write STEADI, Timed Up and Go, TUG, tandem, sway, baseline, or "
    "dual-task. Write dates as month and day. Say 'flags increased fall risk' for a flag. Never diagnose, "
    "predict whether or when someone will fall, promise that falls will be prevented, or give medical or "
    "medication advice."
)
CANT_ANSWER = "I can only answer from the check-in results."
# Questions only a prediction, diagnosis or medical advice could answer: not sent to Grok at all.
ASK_FORBIDDEN = re.compile(
    r"\bwill\b.*\bfall|going to fall|chances? of (?:him |her |them )?falling|odds|predict|diagnos|guarantee"
    r"|medicat|prescri|dosage|\bpills?\b|\bdrugs?\b|how likely|stop using",
    re.IGNORECASE,
)


def _num(v, unit=""):
    return "not measured" if v is None else f"{round(v, 1):g}{unit}"


def _change(changes, key):
    c = (changes or {}).get(key)
    if not c:
        return ""
    unit = steadi.TRACKED[key][1]
    return f"; baseline {steadi.fmt(c['baseline'], unit)}, change {steadi.fmt(c['change'], unit, change=True)}"


CORE_NAMES = {"tug_s": "Timed Up and Go", "chair_stands": "chair stand", "tandem_s": "balance"}


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
    steps = latest.get("steps") or {}  # which steps ran, and how they ended
    flags = [f["text"] for f in latest["flags"]]
    missing = [CORE_NAMES[k] for k in steadi.unmeasured(m)]
    if flags:
        status = "flags increased fall risk: " + "; ".join(flags) + "."
    elif latest.get("declines"):
        status = "no STEADI flags; a sustained change from baseline (below)."
    else:
        status = "no STEADI flags" + (" among the tests measured." if missing else ".")
    if missing:
        status += " Not measured: " + ", ".join(missing) + "."
    tug = (f"did not finish within {steadi.TUG_TIMEOUT_S:g} s" if m.get("tug_timed_out") else _num(m["tug_s"], " s"))
    chair = ("0 stands (stopped: needed arms)" if (steps.get("chair_stand") or {}).get("arms_used")
             else "not measured" if m["chair_stands"] is None else f"{_num(m['chair_stands'])} stands")
    chair_rule = (f"below {cut['chair_stands']} is below average for {cut['chair_label']}" if cut.get("chair_stands")
                  else "no STEADI line without age and sex")

    def stance(s):  # stances after the first one not held for 10 s aren't tried (STEADI)
        return "not tried" if steps and f"balance_{s}" not in steps else _num(m[f"{s}_s"], " s")

    lines += [
        "",
        f"Latest check-in, {latest['date'][:10]}: {status}",
        f"- Timed Up and Go: {tug} (flags at {_num(cut['tug_s'], ' s')} or more{_change(ch, 'tug_s')})",
        f"- Timed Up and Go while naming animals: {_num(m['dual_tug_s'], ' s')}; dual-task cost "
        f"{_num(m['dual_task_cost_pct'], '%')}{_change(ch, 'dual_task_cost_pct')}",
        f"- 30-second chair stand: {chair} ({chair_rule}{_change(ch, 'chair_stands')})",
        f"- Balance stances held (target 10 s): feet together {stance('feet_together')}, "
        f"semi-tandem {stance('semi_tandem')}, tandem {stance('tandem')} "
        f"(tandem under {_num(cut['tandem_s'], ' s')} flags{_change(ch, 'tandem_s')})",
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


def family_items(latest):
    """The check-in's flags and sustained declines in the Home cards' plain words."""
    m, c = latest["metrics"], latest["cutoffs"]
    items = []
    for f in latest["flags"]:
        if f["id"] == "key_questions":
            yes = [t for k, t in YES.items() if latest["key_questions"].get(k)]
            items.append("Answered yes: " + "; ".join(yes) + ".")
        elif f["id"] == "tug":
            took = (f"wasn't finished within {steadi.TUG_TIMEOUT_S:g} seconds" if m.get("tug_timed_out")
                    else f"took {_num(m['tug_s'])} seconds")
            items.append(f"Standing up and walking {took}; {_num(c['tug_s'])} seconds or longer is flagged.")
        elif f["id"] == "chair_stand":
            group = re.sub(r"\s*\(.*\)$", "", c["chair_label"])  # drop "(the oldest STEADI group)"
            items.append(f"Leg strength: {m['chair_stands']} stand-ups from a chair in 30 seconds, "
                         f"fewer than average for {group}.")
        elif f["id"] == "balance":
            # The stance that broke; after it the check-in stops, so a later 0 s means "not tried".
            broke = next((s for s in steadi.STANCES if m.get(f"{s}_s") is not None and m[f"{s}_s"] < 10), "tandem")
            held = f"Balance: held {steadi.STANCE_WORDS[broke]} for {_num(m[f'{broke}_s'])} seconds"
            items.append(f"{held}; under {_num(c['tandem_s'])} seconds is flagged." if broke == "tandem"
                         else f"{held} (the goal is 10), so the hardest position wasn't tried.")
        else:
            items.append(f["text"])
    return items + [f"{AREA[d['id']].capitalize()} has been worse than usual two check-ins in a row."
                    for d in latest.get("declines", [])]


def template(dash):
    """Family summary with no AI: the flags in plain words, or an all-clear, plus exercise."""
    latest, a = dash["latest"], dash["adherence"]
    if not latest:
        return "No check-in yet."
    d = datetime.fromisoformat(latest["date"])
    when = f"{d:%A}, {d:%B} {d.day}"  # "Saturday, September 26"
    if latest["alert"]:
        # A decline is our change-from-usual rule, not a screening flag: say what changed, not "flags".
        found = "flags increased fall risk" if latest["flags"] else "showed a change from usual"
        parts = [f"The check-in on {when} {found}.", *family_items(latest), latest["alert"]["advice"]]
    else:
        missing = steadi.unmeasured(latest["metrics"])
        parts = [f"The check-in on {when} raised no flags" + (", but some tests weren't measured." if missing else ".")]
    parts.append(f"Exercises done on {a['last_7_days']} of the target {a['target_days_per_week']} days "
                 "in the past week.")
    parts.append(FAMILY_NOTE)
    return " ".join(parts)


def check(text, facts):
    """Why an AI summary can't be shown, or None: a forbidden claim, or a number not in the facts."""
    if FORBIDDEN.search(text):
        return "forbidden claim"
    if JARGON.search(text):
        return "clinical words"
    allowed = {float(n) for n in NUMBER.findall(facts)}
    invented = [n for n in NUMBER.findall(text) if float(n) not in allowed]
    return f"numbers not in the data: {', '.join(invented)}" if invented else None


def grok_ask(system, user):
    """The model's reply, or None with no API key or Grok switched off. Raises on network or API errors."""
    key = os.environ.get("XAI_API_KEY")
    if not key or not ai.ai_enabled():
        return None
    body = {
        "model": os.environ.get("CHECKIN_GROK_MODEL", DEFAULT_MODEL),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "temperature": 0.2,
    }
    req = urllib.request.Request(
        GROK_URL, json.dumps(body).encode(), {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
        return json.loads(r.read())["choices"][0]["message"]["content"].strip()


def summaries(dash, ask=None):
    """{"doctor", "family", "family_by": "ai" | "template", "simulated"}."""
    facts = doctor(dash)
    family, by = template(dash), "template"
    if dash["latest"]:
        try:
            text = (ask or grok_ask)(SYSTEM, facts)
        except Exception as e:  # offline, bad key, rate limit, odd reply: the template still works
            log.warning("AI summary unavailable: %s", e)
            text = None
        problem = text and check(text, facts)
        if problem:
            log.warning("AI summary rejected (%s): %s", problem, text)
        elif text:
            family, by = text, "ai"
    simulated = _simulated(dash)
    if simulated:
        family = "Simulated data. " + family
    return {"doctor": facts, "family": family, "family_by": by, "simulated": simulated}


def _simulated(dash):
    return dash["person"]["simulated"] or any(dash["trends"]["simulated"])


def answer(dash, question, ask=None):
    """Ask Steady: {"by": "ai" | "blocked" | "template", "answer", "summary", "reason", "simulated"}.

    "ai": Grok's reply passed check(). "blocked": the question asks for a prediction or diagnosis, or the
    reply failed check(); the family sees CANT_ANSWER and the template summary. "template": Grok is off,
    offline or has no check-in to go on, so only the template summary is shown.
    """
    simulated = _simulated(dash)
    sim = "Simulated data. " if simulated else ""
    out = {"by": "template", "answer": None, "summary": sim + template(dash), "reason": None, "simulated": simulated}
    if not dash["latest"]:
        return out
    if ASK_FORBIDDEN.search(question):
        return {**out, "by": "blocked", "answer": CANT_ANSWER, "reason": "asks for a prediction or medical advice"}
    facts = doctor(dash)
    try:
        text = (ask or grok_ask)(ASK_SYSTEM, f"Check-in results:\n{facts}\n\nQuestion: {question}")
    except Exception as e:
        log.warning("Ask Steady unavailable: %s", e)
        return out
    if not text:
        return out
    problem = check(text, facts)
    if problem:
        log.warning("Ask Steady reply rejected (%s): %s", problem, text)
        return {**out, "by": "blocked", "answer": CANT_ANSWER, "reason": problem}
    return {**out, "by": "ai", "answer": sim + text, "summary": None}
