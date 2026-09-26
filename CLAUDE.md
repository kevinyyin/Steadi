<!--
HUMAN NOTES. Claude Code strips HTML comments before loading this file, so
nothing in them costs context. Only the text outside comments reaches Claude.

SETUP
- Fill in the [brackets]. Delete sections you don't need.
- Run `claude update` (Opus 5.5 needs v2.1.280+). Run /context to confirm this
  file loaded, and /doctor later to get suggested trims.
- This file is guidance, not enforcement. For hard blocks on destructive
  commands, keep permission prompts on or add permissions.deny / a PreToolUse hook.

LEFT OUT ON PURPOSE (don't add these back)
- "Think carefully / step by step": Opus 5.5 always thinks. Use /effort instead.
- "Double-check / verify your work": causes over-verification on Claude 5 models.
- "Show your reasoning in the reply": can be refused (reasoning_extraction).
- Code-style and subagent-delegation rules: Claude Code's system prompt covers them.
- Anything Claude can read from the repo: layouts, dependencies, architecture.
Add a gotcha only when Claude makes the same mistake twice.

EFFORT (/effort, can change mid-session)
low = sketches and quick in-the-loop edits | medium = default feature work |
high = bug fixes in existing code, edge cases, security | max = long autonomous builds.
A loop that works: have Claude interview you on the spec, build at low,
review it yourself, then verify and test at high.

PROMPTS WORTH PASTING
- Task: "[Task]. Done means: [finish line]. Stop only if [condition]."
- Review: "Review this branch's diff against main. Report every real problem
  with file:line, why it's wrong, and how to show it fails. Merge-blockers first."
- Big audit: "Give each [module] its own subagent. Check each one's evidence
  before accepting it. Finish with one table."

OTHER
- Type follow-ups mid-run instead of restarting. /fast for rapid back-and-forth
  (costs more per token). Pick the model at session start; switching breaks the
  cache. Attach screenshots; an HTML mockup beats a screenshot or prose.
- Flagged and moved to an older model? /model to switch back, /config to be asked
  first next time, /feedback if the flag was wrong.

SOURCES (Sep 2026): claude.dev/blog/getting-the-most-out-of-opus-5-5,
claude.dev/blog/spending-your-effort, claude.com/blog/the-new-rules-of-context-
engineering-for-claude-5-generation-models, platform.claude.com prompting guides
for Opus 5.5 and Opus 5, code.claude.com/docs/en/memory
-->

# Project

A 36-hour hackathon build (hardware track, judges are software engineers): fall prevention for older adults at home, following the CDC's STEADI algorithm (screen → assess → intervene) plus tracking. A lower-back sensor scores a ~3-minute guided check-in of the STEADI fall-risk tests (Timed Up and Go, 30-second chair stand, balance stances) plus a dual-task Timed Up and Go; an exercise mode counts reps and times holds; a family dashboard shows fall-risk flags, trends, and exercise adherence. A working live demo beats polish.

Spec: `docs/COMPETITION.md`. Pins, wiring, cues: `docs/PARTS_LIST.md`.

Stack: Python 3.11 with uv; FastAPI serving one static page plus a WebSocket; vanilla HTML/JS with a vendored chart library; JSON files in `data/`; pytest; ruff. Firmware: Arduino sketches built with `arduino-cli`.

## Commands

- Setup: `uv sync`
- Run (no hardware): `uv run checkin serve --source sim --base virtual` → http://localhost:8000
- Test: `uv run pytest`
- Lint: `uv run ruff check .`

## Gotchas

- Hardware isn't final. Everything must run on the simulator and on-screen base station; real devices are adapters behind the same interfaces.
- No core score depends on SKDH. It's an optional extra (gait quality on the optional walk) and doesn't install reliably on Windows.
- The dashboard must work with no internet (the tablet may be on an offline access point): no cloud calls or CDN assets.
- Serial port, UDP port, and Wi-Fi credentials are settings, never hard-coded. The ESP32 broadcasts UDP instead of targeting one IP.
- Claims: say "fall-risk screening", "flags increased fall risk", and "change from baseline". Never say it diagnoses, predicts when someone will fall, or guarantees prevention. Label simulated data "Simulated" wherever it appears.

# Working style

- Keep going when a step doesn't need me. Put status notes in the same message as your next action. Don't end a turn to announce the next step, offer to continue, or list decisions that don't block the work; give your recommendation and carry on with whatever doesn't depend on it.
- Stop and ask only when nothing can move without me, or before anything destructive or hard to undo: deleting data or files you didn't create for this task, force-pushing, rewriting git history, or touching anything outside this repo.
- Do what was asked, at the scope intended. If a request looks mistaken or a clearly better approach exists, say so in one sentence, then do it as asked.
- On multi-step work, keep a checklist in `TASKS.md` and update it as you go, so progress survives context compaction.
- End each substantial run with three short headings: **Blocked on me** (or "nothing"), **Changed**, **Found** (surprises, risks, and anything you couldn't verify).

## Frontend

Unless I give a design direction or reference, avoid: cream or off-white backgrounds, italic accent words in headings, numbered "01 / 02 / 03" section labels, monospace labels, and pill-shaped buttons.
