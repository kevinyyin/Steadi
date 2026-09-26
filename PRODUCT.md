# Product

<!-- impeccable:product-schema 1 -->

Written from the redesign brief (2026-09-26), CLAUDE.md and docs/COMPETITION.md; no separate interview round.

## Platform

web

## Users

- A family member (adult child) who sets up the profile, starts check-ins and reads flags, trends and exercise adherence.
- The older adult being screened, who watches the prompt and presses the one button; the base station cues every step.
- Hackathon judges (software engineers) watching a live demo.

Used on a 10-inch tablet (Dell Venue 10 Pro, portrait or landscape) and a laptop, sometimes on an offline access point.

## Product Purpose

Fall prevention at home following the CDC's STEADI algorithm: screen (three key questions), assess (a ~3-minute guided check-in: Timed Up and Go, dual-task TUG, 30-second chair stand, balance stances, scored by a lower-back sensor), intervene (coached sit-to-stands and balance holds with counted reps and timed holds), and track (flags, trends, adherence for the family). Success: a working live demo that a judge can take on their own body.

## Positioning

The whole STEADI screen at home, guided by a belt and one button, with sensor-verified exercise so the family sees whether it happened.

## Capabilities and Constraints

- One static page plus a WebSocket from FastAPI; vanilla HTML/JS; vendored Chart.js; every value comes from docs/API.md.
- Must work with no internet: no CDN, no web fonts from a network, no cloud calls.
- Runs on the simulator and the on-screen base station; real hardware plugs in behind the same interfaces.
- Status colours carry meaning: LED blue = session in progress; green / amber / red = the check-in's fall-risk level.

## Brand Commitments

- Claims: say "fall-risk screening", "flags increased fall risk", "change from baseline". Never say it diagnoses, predicts when someone will fall, or guarantees prevention.
- Every simulated value is labelled "Simulated" wherever it appears, including chart points.

## Evidence on Hand

- "Simulated: Dad": eight weeks of simulated check-ins and exercise (labelled Simulated).
- STEADI cutoffs and the Cochrane exercise evidence in docs/COMPETITION.md. No trial of this device exists; do not imply one.

## Product Principles

- The live check-in is the moment: the prompt and the one button lead while a session runs.
- Flags are plain and calm: what was found, the cutoff, the change from baseline, and when to see a doctor.
- Honest labels over polish: simulated, not measured, and our own (non-STEADI) summaries are always named.

## Accessibility & Inclusion

Older adults read this: body text at least 18px, very large key numbers, WCAG AA contrast, touch targets at least 44px, portrait and landscape tablet, laptop and phone widths with no horizontal scroll, prefers-reduced-motion respected.
