# Tasks

Plan: docs/superpowers/plans/2026-09-26-fall-checkin-mvp.md

- [x] 1. Project scaffold and simulator
- [x] 2. Step scoring (signals)
- [x] 3. STEADI logic
- [x] 4. People store and recordings
- [x] 5. Clock and motion sources
- [x] 6. Base stations and protocol
- [x] 7. Session controller
- [x] 8. Simulated: Dad history
- [x] 9. API server and docs/API.md
- [x] 10. CLI
- [x] 11. Dashboard page
- [x] 12. Base station firmware
- [x] 13. ESP32 belt firmware
- [x] 14. README and final verification

## Frontend redesign

- [x] Read brief, API, current page; vendor Archivo (OFL) woff2; PRODUCT.md
- [x] Rewrite index.html: tokens, fixed top bar, blocks, rows, roll hover, heading reveal
- [x] Update app.js renderers to the new markup (IDs + API calls unchanged)
- [x] Restyle Chart.js (font, colours, gridlines, cutoff lines, Simulated labels)
- [x] Browser check: tablet landscape/portrait, phone; idle, running, results, Simulated: Dad, exercise
- [x] Console clean; `uv run pytest`; `uv run ruff check .`
- [x] Summary panel: Make summary (on request only), For the family (+ AI-written), For the doctor (pre-wrap, print only it), Simulated tag
- [x] Views by audience: Home / Check-in / For the doctor tabs (hash, no reload, socket kept)
- [x] Home: plain answer + level word, 3 cards (verdict + better/same/worse), exercise in words, family summary, 2 big buttons, no jargon
- [x] Check-in: auto-switch, full screen, Step N of M, huge instruction, Button, one live line, arms-used only in chair stand, small cancel, warnings only when wrong, plain result then Home
- [x] For the doctor: results table, flags, trends, exercise log, doctor summary + print
- [x] Edit profile link (auto-open when age/sex missing before check-in); quick exercise inside Start exercise
- [x] Test 3 views x tablet/phone x Guest empty, live check-in, Simulated: Dad; pytest, ruff; screenshots
- [x] Detector clean
- [x] Dashboard files sent with Cache-Control: no-cache (stale app.js breaks the new page)
- [ ] Later: design finish review and DESIGN.md; test on the Dell tablet with the real belt and base station

## Home critique fixes (2026-09-26, calmer direction)

Critique: .impeccable/critique/2026-09-26T20-10-18Z__src-checkin-static-index-html.md (25/40)

- [x] 1. Family summary: plain flag lines (card wording), banned-word check on AI text; tests
- [x] 2. Hero: name flagged areas, no "Also", level-coloured card marks, decline on its card, never Green when unmeasured
- [x] 3. Errors: plain API errors, retry dashboard on reconnect instead of "Loading…" forever
- [x] 4. Type: numbers below the answer, section h2 > card h3, values wrap, darker green (AA)
- [x] 5. Actions: Start exercise starts the plan, Guest asked for age/sex first, "Add a person…" in picker, Copy summary, summary disabled with no check-in
- [x] 6. Calmer: sentence case, no brackets or roll, meaning words for levels, calm line under a flag
- [x] 7a. pytest (164), ruff, detector (regex fallback: 0), answerFor cases in node
- [ ] 7b. Browser check at tablet/phone widths: needs the server running (starting it here was blocked)

## Home critique fixes, round 2 (2026-09-26)

Critique: .impeccable/critique/2026-09-26T20-29-42Z__src-checkin-static-index-html.md (25/40)

- [x] 1. Flagged moment: every reason listed under the headline; declines say what changed (not "flags increased fall risk"), Home and family summary
- [x] 2. Cards: flagged = amber/red chip, decline = "Getting worse" chip + "Two check-ins in a row." (fixes overflow)
- [x] 3. Exercise section quiet (no blue band); no big "0"
- [x] 4. People: visible Add a person button, menu only switches, open on last person, focus back on Close, Sex help text out of the label, close panel after save
- [x] 5. Simulated: Dad read-only note instead of the form; plain 403
- [x] 6. Tags at body size; offline startup (tile, Start check-in, disabled summary, first-connect warning, retry); label consistency
- [x] 7a. pytest (165), ruff, detector (regex fallback: 0), answerFor/reasons cases in node
- [ ] 7b. Browser pass at tablet/phone widths + /impeccable polish: needs the server running

## Check-in critique fixes (2026-09-26)

Critique: .impeccable/critique/2026-09-26T20-51-33Z__src-checkin-static-index-html-checkin.md (20/40)
Decisions: person starts, helper stops; thanks first, result below; P0 first; all five issues.

- [x] 1. Server: ignore stray presses for 3 s after Go (walk, holds, rounds); live target for time-left; prompt wording (counter on every stance, normal pace, take your time sitting down, no "instep"/"rep"); neutral cancel cue; tests
- [x] 2. Button by phase: "I'm ready" while waiting; full-screen Go ~1.5 s; small helper control while moving (inactive 3 s), hidden in chair stand; rest beat between steps
- [x] 3. Readable from 3 m: one big cue word while moving, draining bar / time left, foot pictures, no walk stopwatch
- [x] 4. Setup screen before a check-in (belt, chairs, 3 m line, counter, someone beside you); name shown while running
- [x] 5. Screen reader/keyboard: write warnings/prompt only on change, focus on start and result, Stop after the button with confirm, polite Go/step/done announcements, no empty heading
- [x] 6. Ending: "You finished. Thank you." then the result for the family, flagged rows marked, honest rows (arms used, not tried, 1 decimal), no auto-return, Start again after a stop
- [x] 7a. pytest (167), ruff, detector (regex fallback: 0), app.js stage-by-stage run in a Node harness
- [ ] 7b. Browser pass (tablet portrait/landscape, laptop, 150% scaling) + /impeccable polish: needs the server running

## Doctor view critique fixes (2026-09-26)

Critique: .impeccable/critique/2026-09-26T21-09-45Z__src-checkin-static-index-html-doctor.md (22/40)
Decisions: walk timeout is flagged; name + date on print/download only; wrong values first; all five issues.

- [x] 1. Scoring: TUG timeout flagged ("did not finish in 60 s"); balance flag text names the stance that broke; a check-in with core tests missing is never shown green (doctor view, printout, family text, base LED); reasons per row (timeout, not tried, arms needed, dropout, how timed); tests
- [x] 2. Trends: level history strip, baseline line + definition, stance ladder instead of the tandem chart, fixed axes, flagged side shaded, gaps as gaps, 1 decimal
- [x] 3. Layout: patient header, results as one aligned table (result, STEADI rule, change, notes, sparkline), exercise log off the blue band, charts two-up on tablets
- [x] 4. Charts for AT: role=img + summary label, one data table, adherence heading, legend not clickable, 16px chart text, fewer headings, doctor text focused when made
- [x] 5. Copy: clinician-facing alert head/advice, decline-only = change from baseline, flags coloured by level, one formatter for screen and print, dual-task baseline in %, name + date on print/download
- [x] 6. Minor: duplicate Simulated tag, "semi-tandem" wording, hold targets in sessions, partial week "(so far)", target line above bars, Blob charset, AI disclosure, summary.py chair cutoff .get
- [x] 7a. pytest (171), ruff, detector (regex fallback: 0), doctor view rendered in the Node harness (Dad + a flagged case)
- [ ] 7b. Browser pass (laptop, tablet portrait/landscape, phone, print preview) + /impeccable polish: needs the server running

## Instruction pictures

- [x] scripts/make_images.py: Grok Imagine via urllib, shared style prompt, optional names, extension from the image bytes
- [x] Balance stances use a feet-from-above prompt; sit-to-stand is halfway up, arms crossed
- [x] Check-in: each step's local picture beside the instruction, plus the exercise pictures
- [x] Family summary calls xAI Grok (`XAI_API_KEY`, `CHECKIN_GROK_MODEL`); same checks and template fallback

## Devpost draft

Paste-ready copy: `docs/devpost-draft.md`.

- [x] Tagline (73 characters) and a 90-word elevator pitch under it
- [x] Inspiration, what it does, how we built it, challenges, accomplishments, learned, what's next, built with, track fit, video script
- [x] Simek 2012 wording checked: 21% fully adherent (95% CI 15–29%), not "stick with a home program"
- [x] $80 billion kept as non-fatal falls, 2020; CDC "every second, an older adult falls"; about 41,000 deaths
- [x] Try it out: https://dhsquad.onrender.com returns the dashboard (`demo: true`, simulator). GitHub stays in the repository field.
- [x] Gallery plan: 3:2, 5 MB, up to 15; nine slots, CAD only as an optional later frame. No CAD file in the repo.
- [x] Cursor and Grok usage, in the README and the Devpost draft, matching how the team actually ran the agents
- [ ] Team names, stopwatch agreement numbers, per-unit cost
- [ ] Gallery photos: belt on a person, belt close-up, base station, result light, exercise reps

## Hardware validation report

- [x] Read diagram-design skill; map it onto the dashboard's tokens (Archivo, ink/blue, white paper)
- [x] Static Archivo 400/700 TTFs for PNG export (resvg can't read woff2)
- [x] `src/checkin/validate.py`: ground-truth CSV, template, pairing, agreement stats, simulated set
- [x] `src/checkin/report.py`: SVG charts, PNG export, offline HTML page
- [x] CLI `checkin validate`; tests; ruff
- [x] docs/VALIDATION.md protocol + README pointer
- [x] End-to-end on simulated data; copy sample images to the project store media/validation/

## Grok Voice cues (2026-09-27)

- [x] `voice.py`: phrase list from the controller's own prompts, hashed filenames, xAI TTS call, cache
- [x] `scripts/make_voice.py` (skip existing, prune unused, `--dry-run` cost) and `static/audio/index.json`
- [x] Check-in screen speaks waiting prompts, rest, and the closing line; hushes at Go; browser voice fallback
- [x] Listen on the family summary (`/api/people/{id}/summary/audio`, only the served text, cached)
- [x] Tests, ruff, README, API.md
- [ ] Generate the audio with a real XAI_API_KEY and commit `src/checkin/static/audio/*.mp3` (no key on the agent VM)
