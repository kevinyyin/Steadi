# Hardware validation: belt vs stopwatch and hand count

This is how we check the belt against a person with a stopwatch, and turn that into numbers and charts for the
pitch. What it measures: **agreement between the belt and hand timing or counting**, on our own team and volunteers.
It is not a clinical validation (no patients, no clinic, no fall outcomes), and the stopwatch has its own error, so
don't call the result "accuracy". Say "agreed with a stopwatch within 1 second in 14 of 15 trials".

## What you need

- The belt, base station and laptop, set up as for a normal check-in (README, sections 2 and 3).
- A **timer**: a second person with a phone stopwatch (lap mode off). They watch the walker, not the screen.
- A **counter** for chair stands and exercise reps. The timer can do both, one job per trial.
- The STEADI test station: arm chair, armless ~17-inch chair, 3 m tape line, a counter for balance.
- A sheet of paper (template at the bottom of this doc) to write the numbers on as you go.

## Rules that keep it honest

1. **Blind:** the timer and counter don't look at the dashboard until they've written their number down.
2. **Let the belt decide:** during validation, don't press the button to end the Timed Up and Go or to mark a balance
   break. A TUG the belt couldn't end by itself is listed as "not scored", not counted as agreement.
3. **Keep every trial.** If something went wrong (belt slipped, timer missed "Go"), write it in `notes`. Leave `truth`
   blank only if the hand number itself is unusable, and decide that before seeing the belt's number.
4. **Time the same thing STEADI does:** start on the buzzer's "Go", not when they start moving.

## What to record

Aim for at least **12 trials of each test**, from **3 or more people**. More people beats more repeats of one person.

| Test | Belt reports | Hand ground truth | How to take it by hand | Trials |
|---|---|---|---|---|
| Timed Up and Go (`tug`) | seconds | stopwatch | Start on "Go". Stop when their back is against the chair again. | 12+ |
| Dual-task TUG (`dual_tug`) | seconds | stopwatch | Same as TUG. | 12+ |
| 30-second chair stand (`chair_stand`) | stands | hand count | Count full stands from "Go" to the stop beep. A stand more than halfway up at the beep counts. | 12+ |
| Balance stances (`balance_*`) | seconds held | stopwatch | Start on "Go". Stop when a foot moves or a hand touches the counter. Held to the end beep = `10`. | 3 per check-in |
| Sit-to-stand sets (`sit_to_stand#N`) | reps | hand count | Count full stands you see, not the beeps. | 12+ sets |
| Supported holds (`hold_*#N`) | seconds held | stopwatch | Same as balance. | optional |

**Make the data varied**, or every point lands in one spot and the chart says nothing:

- TUG: some at normal pace, some slow ("walk like you're 85"), one or two with a pause at the line.
- Chair stand: some fast, some slow, one where they stop early.
- Balance: in about half the stances, **step out on purpose** at a time the timer doesn't know in advance (anywhere
  from 2 to 9 s). Put `deliberate` in `notes`. A stance held to 10 s on both sides is real agreement but not much of a
  test.
- Exercise mode: plan sets of 5 to 10 reps.

A check-in is about 3 minutes, plus a minute to write the numbers down, so 15 check-ins fit in about an hour.

## Workflow

1. Run the dashboard with the belt: `uv run checkin serve --source udp --base serial --serial-port <port>`.
2. For each person: pick or add them on the dashboard, run a check-in (and an exercise session if you're testing
   reps). The timer writes each number on the sheet next to the time of day.
3. After a batch, make the ground-truth file. This adds a blank row for every recorded step it hasn't seen yet and
   never touches rows you've already filled in:

   ```bash
   uv run checkin validate --template
   ```

   It writes `data/validation/ground_truth.csv`. Recordings are named by start time
   (`data/recordings/20260927-101500-checkin.csv`), which is how you match them to the sheet.
4. Fill in `truth` (and `person`, `who`, `notes`) from the sheet. Any spreadsheet app works; keep it as CSV.
5. Make the report:

   ```bash
   uv run checkin validate data/validation/ground_truth.csv
   ```

   It prints one line per test and writes `data/validation/report/`: `report.html` (open it in a browser, works
   offline), a PNG and an SVG of each chart, and `results.json` with every number.

The belt's number always comes from re-scoring the raw recording with the same code the dashboard uses
(`checkin replay`), so it can't be mistyped. If you tune `src/checkin/signals.py` afterwards, re-run step 5 and say
which version the numbers came from. Tuning on the same trials you report inflates agreement; if you tune, record a
fresh batch for the numbers you present.

### Ground-truth CSV

```csv
recording,step,truth,person,who,notes
20260927-101500-checkin.csv,tug,11.84,allen,kevin stopwatch,
20260927-101500-checkin.csv,dual_tug,14.10,allen,kevin stopwatch,
20260927-101500-checkin.csv,chair_stand,13,allen,kevin count,
20260927-101500-checkin.csv,balance_feet_together,10,allen,kevin stopwatch,
20260927-101500-checkin.csv,balance_semi_tandem,10,allen,kevin stopwatch,
20260927-101500-checkin.csv,balance_tandem,6.2,allen,kevin stopwatch,deliberate
20260927-103000-exercise.csv,sit_to_stand#1,8,allen,kevin count,
```

- `recording`: file name in `data/recordings/` (or a path). `step`: the step id from the template.
- `truth`: seconds or a count. Rows with it blank are skipped.
- `person`: who did the test (counted for "N people"). `who`: who timed or counted. `notes`: anything.
- A row whose `notes` says `simulated`, or whose recording came from the simulator, makes the whole report
  "Simulated".

### Options

- `--tol-time 1.0` and `--tol-count 1`: what counts as "within tolerance" (defaults: 1 s, 1 rep). Pick these before
  you look at the results and say them next to the number.
- `--out DIR`: report folder. `--no-png`: SVG and HTML only.
- `--simulated`: generates simulated sessions with made-up ground truth in `data/validation/simulated/` and reports on
  them. Everything it makes says "Simulated". Use it to preview the charts, never as a result.

## Reading the report

- **Within tolerance:** trials where the belt and the stopwatch were at most 1 s (or 1 rep) apart.
- **Mean difference:** belt minus hand, averaged. Negative means the belt reads shorter. A steady offset (for example
  the timer reacting 0.2 s late on both start and stop) shows up here.
- **Typical error:** the mean absolute difference, also as a percentage of the average time.
- **95% limits of agreement (Bland-Altman):** mean difference ± 1.96 standard deviations of the differences. About
  95% of trials should fall inside.
- **Same side of the STEADI cutoff:** trials where both methods agree on whether TUG was 12 s or more, or the tandem
  stance under 10 s. This is the one that matters for screening.
- **Not scored:** trials the belt couldn't score (data dropped out, or it didn't detect the sit-down). They're listed
  and counted, never dropped.

For comparison, a 2024 study of a lower-back sensor running STEADI matched human raters within about 4% on TUG and
8% on chair stands (docs/COMPETITION.md). You can say our numbers are "in the same range as" that if they are; don't
say we reproduced or validated it.

## Wording for the pitch and Devpost

Say: "On 15 Timed Up and Go trials from 4 people, the belt was within 1 second of a stopwatch in 14, and agreed on
which side of the 12-second cutoff in 15." "Agreement with hand timing and counting, not a clinical validation."

Don't say: "accurate to 0.3 s", "clinically validated", "detects fall risk with 95% accuracy", or any number
without its trial count. Anything from `--simulated` is labelled Simulated and isn't a result.

## Paper sheet

| Time | Person | Test | Hand number | Timer | Notes |
|---|---|---|---|---|---|
| 10:15 | allen | TUG | 11.84 | kevin | |
| 10:15 | allen | Dual-task TUG | 14.10 | kevin | |
| 10:15 | allen | Chair stand | 13 | kevin | |
| 10:15 | allen | Feet together | 10 | kevin | |
| 10:15 | allen | Semi-tandem | 10 | kevin | |
| 10:15 | allen | Tandem | 6.2 | kevin | stepped out on purpose |
