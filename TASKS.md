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
- [ ] Dashboard files sent with Cache-Control: no-cache (stale app.js breaks the new page)
- [ ] Later: design finish review and DESIGN.md; test on the Dell tablet with the real belt and base station
