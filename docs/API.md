# Check-in API

Everything the dashboard shows comes from here, so the UI can be rebuilt without touching the backend.
Served by `uv run checkin serve` at `http://<laptop>:8000`. JSON everywhere; no auth (it's on the home network). The only outside call is the optional AI family summary (below), which sends the doctor summary text, with no name, to xAI Grok.

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
| `live` | `elapsed_s` since "Go"; `reps` counted so far (chair stand, sit-to-stands); `target` reps (exercise); `limit_s` (chair stand, 30) and `target_s` (balance and exercise holds), so the page can show time left |
| `led` | `off`, `blue` (session in progress), `green`, `amber`, `red` (level of the check-in just saved) |
| `base` | `virtual` (the page plays the tones) or `serial` (the Arduino does) |
| `source.kind` | `sim`, `csv`, `udp`, `phyphox` |
| `demo` | `true` when started with `checkin serve --demo` (the public demo): hide Add a person and Edit profile; `POST`/`PUT /api/people` return `403` |

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
| `POST /api/button` | none | The on-screen button: starts the waiting step; during a TUG it stops the clock (stopwatch fallback); during a balance stance it marks the stance as broken; during a sit-to-stand round it ends the round. A press within 1 s of the last one taken is ignored (double-tap), and so is one within 3 s of "Go" (a nervous "did it start?" press must not save a 2 s walk or a broken stance) |
| `POST /api/stop` | `{"reason": "arms_used"}` | While the chair stand is running: stop and record 0 stands (STEADI). Ignored at any other time |
| `POST /api/stop` | `{"reason": "cancel"}` | End the session; nothing is saved (the `stop` cue plays, not `error`: it's a safety stop, not a failure) |

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
    "simulated": [true, "..."],
    "series": {"tug_s": [10.8, "..."], "dual_task_cost_pct": [16.7, "..."], "chair_stands": [13, "..."],
               "tandem_s": [10.0, "..."]},
    "cutoffs": {"tug_s": 12.0, "chair_stands": 11, "tandem_s": 10.0}
  },
  "plan": {"sit_to_stand": {"sets": 3, "reps": 8}, "balance": {"stance": "tandem", "holds": 2, "target_s": 20.0},
           "why": "more sit-to-stands: chair stands are at or near the STEADI line"},
  "adherence": {"target_days_per_week": 5, "last_7_days": 5,
                "weeks": [{"week_start": "2026-09-21", "days": 4, "sessions": 4, "reps": 96, "hold_s": 96.0,
                           "simulated": true}]},
  "exercise": [ "... the last 10 exercise logs, below" ]
}
```

`plan` is rebuilt from the latest check-in and the exercise logs every time it's read:
- A weak area changes the plan only when it shows up in two check-ins in a row, so one bad day doesn't. A check-in that didn't measure it (belt dropout) is skipped, not counted as fine. After a single low result, `why` says the plan adds more if the next check-in shows the same.
- `sit_to_stand.sets`: 3 when chair stands are at or near the STEADI line (under it + 2), or have slipped below their baseline, two check-ins in a row; otherwise 2.
- `balance.holds`: 4 with a balance flag, or a tandem stance slipping below its baseline, two check-ins in a row; otherwise 2.
- `sit_to_stand.reps` (8 to start, 10 at most) and `balance.stance` move up one step once every set or hold in the latest session hit its target, but only after 3 or more exercise days in the last 7. Otherwise they stay the same, and `why` says so when they would have moved up. Sessions shorter than 8 reps (the quick demo) don't count.

`trends.cutoffs` are STEADI lines for charts: TUG flags at 12 s or more; chair stands flag below the number (`chair_label` names the age/sex group); tandem flags below 10 s. Per check-in: `trends.levels`, `trends.flags` (flag ids), `trends.declines` (metric ids), `trends.partial` (a core test wasn't measured, so the check-in isn't "clear" even when green), `trends.baseline` (the rolling baseline each metric was compared with: mean of up to 4 earlier check-ins; `null` until there are 2), and `trends.stances_held` (0–3 balance stances held for 10 s in order, `null` if not measured). A TUG not finished within 60 s while the belt kept sending is `metrics.tug_timed_out: true` and flagged; a belt that went quiet is a dropout (`error`), never flagged. `adherence.weeks` covers the last 8 weeks (Monday start), oldest first. `trends.simulated` (per check-in) and `adherence.weeks[].simulated` (any simulated session that week) say which chart points to label "Simulated".

### `GET /api/people/{id}/summary`

Two text summaries of the dashboard, for a "summary" panel and for printing before a doctor's visit.

```json
{"doctor": "Fall-risk screening summary: ...\n- Timed Up and Go: 10.8 s (flags at 12 s or more; ...)\n...",
 "family": "Simulated data. The check-in on Saturday, September 26 raised no flags. ...",
 "family_by": "ai",
 "simulated": true}
```

- `doctor`: built only from the recorded numbers, never by AI: profile, key questions, latest results against the STEADI cutoffs, change from baseline, first/worst/latest per metric, exercise adherence and plan. Plain text with line breaks (show it in `<pre>` or with `white-space: pre-wrap`). It has no name in it.
- `family`: 3–5 plain sentences. `family_by` is `"ai"` when a Grok model wrote it from the `doctor` text, or `"template"` (fixed wording) when there's no `XAI_API_KEY`, no internet, or the AI reply failed a check: a number that isn't in the data, a forbidden claim (diagnosis, predicting a fall, guaranteed prevention, medication), or clinical words the family never sees (STEADI, Timed Up and Go, TUG, tandem, sway, baseline, dual-task). The fixed wording names flags the way the Home cards do ("Leg strength: 10 stand-ups from a chair in 30 seconds, fewer than average for men 75–79."); a check-in raised only by a sustained decline "showed a change from usual" rather than "flags increased fall risk", since the decline rule is ours, not STEADI's. Label the AI text as AI-written.
- With an AI key set, the call can take a few seconds: fetch it when the user asks, not with every dashboard load.
- `simulated`: the text already starts with "Simulated data." / "SIMULATED DATA"; still show the usual Simulated tag.

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

A set or hold whose sensor data dropped out is saved without its count: a set as `{"error": ..., "target": 5}` (no `reps`), a hold as `{"error": ..., "stance", "method", "target_s"}` (no `hold_s`): it counts as "not measured" and adds nothing to adherence or stance progression.

Balance holds move up a stance (feet together → semi-tandem → tandem) once every hold in the latest session reaches its target.

## Files

- `data/people/<id>.json`: `{"id", "name", "simulated", "profile", "checkins": [...], "exercise": [...]}`
- `data/recordings/<session id>.csv`: first line `# source=<kind> simulated=<0|1>`, then `t,ax,ay,az,gx,gy,gz,step` (s, g, °/s; `step` is the step id for samples from its "Go" to its end, blank otherwise)
