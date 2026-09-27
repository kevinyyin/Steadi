# Devpost draft: Steady (HackGT 13)

Checked against `main` at `e474ab3` (27 Sep 2026): firmware, scoring, the exercise plan, the dashboard, and the docs in this repo. The pitch deck (`internal/pitch-deck.pdf`) was not in the clone, so deck lines below are the ones in the draft you pasted.

Paste everything under **Submit this**. The notes after that are for the team.

Claims follow `CLAUDE.md`: "fall-risk screening", "flags increased fall risk", "change from baseline". The copy does not say the device diagnoses, predicts when someone will fall, or prevents falls.

---

## Submit this

### Project name

Steady

### Tagline

The CDC's fall-risk tests, scored by a belt at home. Check. Coach. Share.

73 characters. Devpost's tagline field allows 120.

### Elevator pitch

Put this directly under the tagline. **What it does** opens with the same paragraph, so the project page reads tagline, then pitch.

Steady brings the CDC's fall-risk screening home. A belt worn at the lower back and a one-button base station run the tests in about three minutes, with a family member standing by. The belt times the walk, counts chair stands, and times each balance hold. It flags increased fall risk, tracks change from baseline, and coaches strength and balance moves, counting every rep so the family can see the exercise happened. Home is the trend in plain words. For the doctor is one page to take to the next visit.

90 words.

### Inspiration

Every second, an older adult falls (CDC). Falls are the leading cause of injury death for adults 65 and older, about 41,000 deaths a year (CDC). Medical costs for non-fatal falls were about $80 billion in 2020 (Haddad et al., Injury Prevention 2024).

Today's devices notice a fall after it happens. In one study, 80% of the oldest adults who had a personal alarm did not use it when they fell alone and could not get up (Fleming and Brayne, BMJ 2008). Exercise reduces the rate of falls by 23% (Cochrane review, 108 trials, 23,407 people). A review of home exercise programs for preventing falls found that 21% of participants were fully adherent to the prescribed dose (Simek, McPhate, and Haines, Preventive Medicine 2012; 23 trials; 95% CI 15% to 29%).

Clinicians already have the playbook. The CDC's STEADI algorithm screens with three key questions, assesses with three short tests (Timed Up and Go, the 30-second chair stand, and a balance test), and then intervenes with exercise. That happens in a clinic, maybe once a year. We wanted to run the same screening at home every week, confirm the exercises actually happen, and let the family see the trend.

### What it does

Steady brings the CDC's fall-risk screening home. A belt worn at the lower back and a one-button base station run the tests in about three minutes, with a family member standing by. The belt times the walk, counts chair stands, and times each balance hold. It flags increased fall risk, tracks change from baseline, and coaches strength and balance moves, counting every rep so the family can see the exercise happened. Home is the trend in plain words. For the doctor is one page to take to the next visit.

**Check.** About three minutes, with a family member standing by, as STEADI's instructions require. The base station beeps a cue for each step. The screen shows a large instruction and a picture. The belt scores each test.

- Timed Up and Go: timed from the "Go" beep until the person is seated again, detected from the belt's motion. A button press works as a stopwatch fallback.
- Timed Up and Go while naming animals out loud: we report the dual-task cost, the percentage slowdown from the normal walk.
- 30-second chair stand: counts full stands. An Arms used button stops the test and records 0, as STEADI specifies.
- Balance stances: feet together, then semi-tandem, then tandem, 10 seconds each, beside a counter. The belt times each hold until the stance breaks, and the sequence stops at the first failure. A button press can mark the break. A gap in the sensor data is scored as not measured.
- Screening questions: the dashboard asks STEADI's three key questions: fallen in the past year, feel unsteady, worried about falling.

Each result is compared with STEADI's cutoffs (Timed Up and Go of 12 seconds or more, chair stands below the age and sex norm, tandem stance under 10 seconds) and with the person's own rolling baseline. Steady flags increased fall risk and shows any sustained change from baseline. It gives a fall-risk level of green, amber, or red. That level is our own summary, not part of STEADI, and the belt's light and the base station's light show it. A check-in with a core test missing is never shown as green.

**Coach.** Exercise mode coaches sit-to-stands (the belt counts every rep and the base station beeps) and counter-supported balance holds (the belt times them). Everyone gets a plan, as STEADI recommends. If chair stands or balance slip across two check-ins, the plan adds sit-to-stands or balance holds. Reps and the stance move up as sessions are completed, and that progression pauses when exercise days drop off.

**Share.** Three views:

- Home tells the family in plain words how the check-in went, with trends and exercise days against a target of 5 a week.
- Check-in is a full-screen view meant to be read from 3 m away.
- For the doctor has a results table with the STEADI rule for each test, change from baseline, trends, the exercise log, and a one-page printable summary. The summary can be made after any check-in. When something flags, the family is prompted to bring it to the next doctor's visit.

Every simulated value is labelled "Simulated". A built-in "Simulated: Dad" profile shows eight weeks of history: a flag, the exercise plan responding, and scores over time.

The public demo at https://dhsquad.onrender.com runs on the simulator. Every value there is labelled "Simulated".

### How we built it

**Hardware**

- Belt: an ESP32 with an MPU-6050 IMU (±8 g, ±500 °/s). It reads the sensor's FIFO at 100 Hz and broadcasts UDP over Wi-Fi. A USB power bank powers it, and it is worn at the lower back. The laptop sends LED colours back to the belt, and the belt's RGB LED shows them without interrupting the sensor stream: blue while a session is running, then green, amber, or red for the level. A buzzer pin is on the board and held quiet. The beeps come from the base station.
- Base station: an Arduino Uno R4 on a breadboard with a start button, an RGB LED, and a buzzer for cues and rep beeps. It talks to the laptop over USB serial with a small text protocol (`CUE start`, `LED amber`, `BTN`).
- Backup sensor: a phone in a belt pouch running a custom phyphox experiment.

Both firmware sketches are built with arduino-cli. Wi-Fi credentials, the UDP port, and the serial port are settings, not hard-coded. The ESP32 broadcasts UDP instead of targeting one IP.

**Scoring (Python, NumPy).** Scoring does not depend on how the belt is oriented, so there is no calibration step. Timing starts on the "Go" cue, as in the clinical protocol. The end of a Timed Up and Go is stillness after movement, in a posture closer to the seated posture before "Go" than to walking. Chair stands are counted from upward-velocity peaks. A stand still rising at 30 seconds counts if it is more than halfway up. A balance stance breaks when smoothed acceleration leaves the starting posture, or the trunk rotates past a set rate. The signal is averaged over a tenth of a second, and the reference is the posture at the start of the hold. Every threshold is a named constant, and `checkin replay` re-scores a recorded session after tuning.

**Swappable hardware.** Every sensor (simulator, ESP32 over UDP, phyphox, CSV replay) and both base stations (on-screen or Arduino serial) sit behind the same interfaces. We built and tested the software on the simulator, and the public demo runs there.

**Server and dashboard.** A FastAPI session controller cues the devices, tags the motion stream by step, scores each step, and pushes live state to the page over a WebSocket. The page is plain HTML and JavaScript with a local copy of Chart.js and a local font. It makes no CDN calls, and the check-in works on an offline access point. The optional family summary is the one feature that calls out, and only when an API key is set. Data is stored as JSON files, and every session also saves its raw motion stream as a CSV file.

**xAI Grok in the product**

- Grok Imagine (`grok-imagine-image-2.0`) drew the instruction picture for each step: Timed Up and Go, chair stand, sit-to-stand, supported hold, and the three foot positions, shown from above because a side view hides foot placement. `scripts/make_images.py` holds the style prompts. The pictures ship as local files.
- Grok chat (`grok-4.3`, configurable) turns the doctor summary into a 3- to 5-sentence family update. No name is sent. The reply is rejected if it uses a forbidden claim (diagnose, predict, guarantee, medication advice) or clinical jargon, or if it includes any number that is not in the source data. The page tags accepted text as "AI-written". With no key, no internet, or a rejected reply, the family gets a fixed-wording summary.

**How we built it with Cursor.** We ran Cursor as a team of parallel agents and sent each task to the model best at it.

- Grok for quick idea checks: whether a feature idea, a threshold, or a claim held up before we committed to it.
- Claude and Grok on the backend: signal scoring, the STEADI logic, the session controller, and the API.
- Codex and Grok on the frontend: the UI and visual design of the three dashboard views.

Many agents worked at once on firmware, scoring, the dashboard, and documentation, and the swappable interfaces kept them from getting in each other's way. The most useful feature was Cursor's mid-run guidance. When we had a new idea, we could steer an agent while it was still running instead of stopping it and starting over. That is how late ideas, such as the foot-position pictures, made it into the build.

**Testing.** pytest, including a full simulated check-in scored against the simulator's true values. Linting uses ruff. Agreement with a stopwatch and hand counts on real people is still to be measured.

### Challenges we ran into

**No soldering at the venue.** The hardware desk had no soldering irons, clips, or wire strippers. We soldered the MPU-6050 headers at a campus makerspace and built against a simulator, so progress never waited on the belt.

**Detecting the end of a Timed Up and Go.** The STEADI protocol times from "Go" to seated, so we had to find the sit-down and tell it apart from a pause while standing. We compare the posture with the seated posture before "Go", and a button press remains a stopwatch fallback.

**Balance scoring.** A single noisy sample should not end a hold, and a missing tail of sensor data should not look like a short hold. We smooth the signal, compare it with the posture at the start of the stance, and score a dropout as not measured. A button press can still mark a break.

**Messy input.** Late packets at the end of a step, short gaps in the Wi-Fi stream, a double-tap on the button, and a stray press right after "Go" each had to be ignored or scored as not measured. The belt keeps streaming at 100 Hz while it reads LED messages. Cues play on the base station.

**Keeping an LLM honest in a health product.** A fluent family summary is easy to generate. One that never invents a number or says it predicts falls is harder, so we check the output rather than trusting the prompt.

**Designing for two audiences.** Older adults need big text and one action at a time. Doctors need exact numbers and the rule for each test. We ended up with separate views for the family, the check-in, and the doctor.

### Accomplishments that we're proud of

- The CDC's STEADI loop runs end to end: screening questions, all three tests plus a dual-task walk, coached exercise, and tracking. The same software runs on the belt, a phone, a replayed recording, or the simulator.
- Every rep is counted and every hold is timed, so the family can see whether the exercise happened.
- A helper stands by for the check-in, as STEADI's instructions require. Solo exercise is limited to supported moves: sit-to-stands from a sturdy chair and counter-supported balance holds.
- A guarded AI summary that falls back to fixed wording on any doubt, and that the page labels as AI-written.
- A dashboard that works offline for the check-in, with body text of at least 18 px, AA contrast, 44 px touch targets, and screen-reader labels on the charts.
- Honesty is in the product: simulated data is labelled, a stance the sequence never reached shows as "not tried", and a check-in missing a test is never shown as all-clear.

### What we learned

Clinical protocols make good specs. Following STEADI on timing (from "Go", record 0 when arms are used, stop at the first failed stance) removed sensing problems such as detecting when movement starts.

Parallel agents need clean interfaces. With swappable devices and a written API, several agents could work at once.

Sending tasks to models by their strengths, and steering agents while they ran, got more done than one long chat.

With an LLM in a health product, the checks on the output matter more than the prompt.

Balance is the hardest thing to score. That matches published lower-back IMU work, which agreed with human raters within about 4% on the Timed Up and Go and about 8% on chair stands, and less well on balance.

### What's next

- Finish validation on real people, publish the agreement with a stopwatch and with hand counts, and tune thresholds with the replay tool.
- Add spoken check-in cues and a Listen button on the family summary, with the audio generated ahead of time so it plays offline.
- Detect talking during the dual-task walk with a close microphone and voice activity detection, and possibly count the animals named.
- Measure gait quality on an optional 30-second walk using Pfizer's open-source SKDH library. No core score depends on it.
- Run a pilot with physical therapists or a senior center, and work out a per-unit cost.

### Built with

python, fastapi, uvicorn, websockets, numpy, pyserial, javascript, html5, css, chart.js, esp32, arduino, arduino-cli, mpu-6050, c++, udp, phyphox, xai, grok, grok-imagine, cursor, claude, codex, pytest, ruff, uv, render

### Track fit

**The Shipyard (Hardware).** Steady is a wearable with a job. An IMU belt streams 100 Hz motion over Wi-Fi, and its light shows the check-in state. A one-button base station cues each step, so the check-in is not an app on the older adult's phone. The belt sits at a standard placement at the lower back, and there is one button to press. Both firmware sketches, the belt-to-laptop UDP protocol, and the serial protocol are ours. Judges can clip on the belt and do a 30-second chair stand while the dashboard scores it live.

**Aramco, A Marina's Mission (social good: health).** Falls are the leading cause of injury death for adults 65 and older. Steady brings the CDC's own STEADI fall-risk screening from a yearly clinic visit to a weekly routine at home, and pairs it with strength and balance exercise of the type shown to reduce the rate of falls. The belt confirms the exercise was done. It is built for the people it serves: plain language for families, a one-page summary for the doctor, large text and AA contrast, and a check-in that works offline. It flags increased fall risk and tracks change from baseline. It does not diagnose, and we have not run a clinical trial.

**SpaceXAI, Make it Legendary (Cursor + Grok).** We built Steady in Cursor as a team of parallel agents. Grok handled quick idea checks, Claude and Grok built the backend, and Codex and Grok built the frontend. Cursor's mid-run guidance let us steer agents with new ideas while they were running. Grok is also in the product. Grok Imagine drew every instruction picture, and a Grok model writes the family's update from the recorded numbers inside a strict check: no invented numbers, no diagnosis or prediction claims, no jargon, and fixed wording as the fallback.

### Video demo script (about 2 minutes)

Three teammates narrate, and Allen does the physical demo.

| Time | On screen | Voice-over |
|---|---|---|
| 0:00–0:15 | "Every second, an older adult falls." Then about 41,000 deaths a year, and about $80 billion in medical costs for non-fatal falls (2020). | Speaker 1: "Falls are the leading cause of injury death after 65." |
| 0:15–0:30 | The alarm finding (80% did not use it) and "21% fully adhered to a prescribed home program." | Speaker 1: "Today's devices notice a fall after it happens. Exercise cuts the rate of falls by 23%, and almost nobody completes the home program." |
| 0:30–0:40 | The belt, the base station, and the tablet. Title card: Check. Coach. Share. | Speaker 2: "Steady turns the CDC's fall-risk tests into a 3-minute routine at home." |
| 0:40–1:10 | Allen, with a teammate standing by, does the check-in: Timed Up and Go on the "Go" beep, a clip of the walk while naming animals, chair stands counting up, and a balance hold with the foot picture. | Speaker 2: "Check: the belt scores the CDC's own tests. It times the walk, counts stands, and times each balance hold." |
| 1:10–1:20 | The result screen, then the light turning green, amber, or red. | Speaker 2: "Results in plain words, and the light shows the level." |
| 1:20–1:35 | Exercise mode: a short set of sit-to-stands with a beep and a count per rep, then the week's exercise days. | Speaker 3: "Coach: strength and balance moves, and every rep counted." |
| 1:35–1:50 | "Simulated: Dad", with the Simulated label visible: a flag, the trend, the For the doctor view and printout, and the family summary with its AI-written tag. | Speaker 3: "Share: the family sees the trend, and the doctor gets a one-page summary. Grok writes the family update inside strict checks." |
| 1:50–2:00 | A short capture of Cursor with parallel agents, then the closing card with the website URL. | Speaker 3: "Built in Cursor with Grok, Claude, and Codex. Steady: Check. Coach. Share." |

Film the check-in on the real belt. Label any simulator footage "Simulated". After an amber or red result, say "flags increased fall risk".

### Try it out

Devpost form field. Do not paste this note into the story.

https://dhsquad.onrender.com

That is the only try-it-out link. The site is up: it serves the dashboard in demo mode, Guest can start a check-in, and the sensor is the simulator. Put https://github.com/kevinyyin/dhsquad in the repository field.

---

## Tagline

**Use:** The CDC's fall-risk tests, scored by a belt at home. Check. Coach. Share.

It does three jobs the gallery needs. The first sentence says what the project is, so a judge who never opens the page still knows it is CDC fall-risk screening on a belt. "Check. Coach. Share." is the deck's closing line, so the booth, the video, and Devpost end on the same three words. It stays inside the claim rules: screening and a routine, not a promise that falls are prevented.

| Line | Chars | Use it when |
|---|---|---|
| The CDC's fall-risk tests, scored by a belt at home. Check. Coach. Share. | 73 | The Devpost tagline. Recommended. |
| Check. Coach. Share. | 20 | The video closer and the last slide. Too thin alone on a gallery of hardware projects. |
| Steady turns the CDC's fall-prevention playbook into a 3-minute routine. | 72 | A spoken opener, if you want the deck's sentence. "Playbook" means STEADI, the CDC program. Say it in the video, not as the only line on the card. |
| A 3-minute home check-in that flags increased fall risk and counts every rep. | 77 | The most literal description. Use it if the form has a second short-description field. |
| The CDC's fall-risk tests, scored by a belt at home. Every rep counted. | 71 | Same shape as the recommended line, with the exercise proof instead of the three-beat closer. |
| Today's answers come too late. Steady starts before a fall. | 59 | Leave this off the card. "Before a fall" is easy to hear as "predicts" or "prevents". The inspiration section already says today's devices notice a fall after it happens. |

## Elevator pitch

The 90-word paragraph above is the one to paste. Read aloud it is about 35 seconds, which is one breath longer than a strict 30-second booth intro and short enough to sit under a title.

If a judge is already holding the belt, start one sentence later: "A belt at the lower back and a one-button base station. Three minutes, someone standing by. It times the walk, counts the stands, times the holds, flags increased fall risk, and counts every exercise rep."

## Deck lines, resolved from the code

- The belt in this tree has a motion sensor and an RGB LED. The laptop sends the LED colour over UDP. The buzzer pin is defined and held low; cues and rep beeps play on the base station (or in the browser when the base is on-screen). The button is on the Arduino, or on the screen. The demo slide should say: a motion sensor and a light on the belt; a button, a light, and a buzzer on the base station.
- Everyone gets an exercise plan, including before any check-in (the standard sets and holds). The plan adds a sit-to-stand set when chair stands are low two check-ins in a row or have slipped below baseline, and adds balance holds when the tandem stance flags two check-ins in a row or has slipped below baseline. Reps start at 8 and move up to 10, and the stance moves up, only after completed work and at least 3 exercise days in the last 7. Otherwise progression stays put. There is no slower-pace mode.
- The one-page doctor summary can be made after any check-in. A flag prompts the family to take it to the next visit.

## Statistics, with the wording to keep

- **Every second.** CDC's line is "Every second, an older adult falls" (Still Going Strong; also the 2016 MMWR synopsis, "Every second of every day in the U.S., an older adult falls"). Use that, not "every second an older American falls", which is the same fact in looser words.
- **41,000 deaths.** CDC Still Going Strong lists 41,000 fall deaths a year next to that "every second" line. The figure moves as new vital-statistics years publish. "About 41,000" is the safe wording.
- **$80 billion.** Haddad et al., Injury Prevention 2024: healthcare spending for **non-fatal** older-adult falls was $80.0 billion in **2020**. A CDC at-a-glance sheet rounds this to "about $80 billion in medical costs every year" and does not say non-fatal. The draft says non-fatal and 2020 so the number matches the paper.
- **80% alarms.** Matches `docs/COMPETITION.md`: 80% of the oldest adults with a personal alarm did not use it when they fell alone and could not get up. Fleming and Brayne, BMJ 2008, is the study that sentence refers to.
- **23%.** Matches `docs/COMPETITION.md`: exercise reduces the **rate** of falls by 23% (Cochrane, 108 trials, high-certainty). Say "reduces the rate of falls". The coached moves are that type of exercise. This device has not been tested for that effect.
- **21%.** Simek, McPhate, and Haines, Preventive Medicine 2012. The paper's result is: the pooled estimate of participants who were **fully adherent** was 21% (95% CI 15%–29%, range 0%–68%) across 23 randomized trials of home exercise for preventing falls. "Only 21% stick with a home program" is looser than "fully adherent to the prescribed dose." The same paper found that full adherence was not associated with how well the program reduced falls, so the pitch should not say that tracking adherence is what produces the 23% effect.

The 4% and 8% figures in What we learned are the published lower-back IMU study in `docs/COMPETITION.md` ("within ~4% on TUG and ~8% on chair stands"), not our own agreement numbers. "Agreement was about 4%" reads as 4% agreement. The draft says "within about 4%".

## Image gallery

Devpost: JPG, PNG, or GIF, 5 MB each, up to 15 images, 3:2. Export at 2400×1600 (or 1800×1200). Keep the subject in the middle third, because a 4:3 shot will be cropped. A 2400×1600 JPG is far under 5 MB.

There is no CAD in the repo. The only images on hand are seven instruction drawings in `src/checkin/static/img/`, each 1152×864 (4:3, about 100 KB). Use them as one combined frame (slot 9), not as seven gallery slots.

Upload in this order. Slot 1 is the thumbnail judges see in the project gallery, so it has to be the hardware. Eight or nine strong frames beat fifteen thin ones.

| # | What | How |
|---|---|---|
| 1 | Cover. Belt on the lower back, base station and tablet in the same frame. Person from the side or back. | Photo. This is the thumbnail. |
| 2 | Belt close-up: ESP32, MPU-6050, power bank, RGB lit. | Photo. |
| 3 | Base station: the one button, the RGB LED, the buzzer, on the breadboard. | Photo. |
| 4 | Check-in on the tablet: one large instruction and the foot picture. | Screenshot or a straight-on photo of the tablet. If it is the simulator, the word Simulated has to be in the frame. |
| 5 | Result in plain words, and the light green, amber, or red. Belt or base station light in the same shot if you can. | Photo. |
| 6 | Exercise: sit-to-stands with the rep count on screen and the base station in frame. | Photo. |
| 7 | Home, "Simulated: Dad": a flag, the trend, and the Simulated label. | Screenshot from https://dhsquad.onrender.com. |
| 8 | For the doctor: the results table, or a photo of the one-page printout on paper. | Screenshot, or a photo of the paper. The paper is the better of the two. |
| 9 | The three foot-position drawings on one 3:2 board. | Compose from the JPGs already in the repo. Pad them onto a 3:2 canvas. A center crop of the 4:3 files cuts the feet. |

Optional, and only if you still have room:

| # | What | How |
|---|---|---|
| 10 | CAD, one image. The belt's placement on the body, or a mount you actually use. | Render at 3:2. If the part is not built, put the word Design in the corner. An unlabelled render of a case that is not on the table will be read as the prototype. Skip the CAD if it does not show placement better than slot 1. |
| 11 | The test station: arm chair, the 3 m tape line, the armless chair, the counter. | Photo. |
| 12 | One GIF under 5 MB: the chair-stand count ticking, or the LED changing colour. A few seconds, looped. | GIF. One only. |

Leave out stat slides, a Cursor window, a wiring diagram, the phone-in-a-pouch backup, and the seven instruction drawings as separate images. The phone backup makes the "why not a phone app?" answer harder. The Cursor story belongs in the video.

## Left open

- Team names. The deck you described lists Kevin Yin and James Wang, and Allen runs the physical demo. Confirm the Devpost team before submitting. Nothing here invents a third name.
- Stopwatch and hand-count agreement. Not in the repo. The testing paragraph says it is still to be measured.
- Spoken cues and a Listen button. Not in this tree. Grok Voice is not in Built with. It is under What's next.
- A live sway-warning beep, separate from ending the stance, is not in this tree. A detected break ends the hold; the base station then plays its stop cue. The video script does not mention a warning beep.
- A balance break is not "outside the posture for 0.3 seconds." In `src/checkin/signals.py` the hold ends on the first smoothed sample past the threshold (0.1 second average; acceleration departs by 0.2 g, or rotation passes 30 °/s).
- Per-unit cost. `docs/COMPETITION.md` still says to fill this in before judging.
- Image files for the gallery. The shot list is above. Photos of the belt, the base station, and a person wearing the belt still have to be taken. There is no CAD file in the repo to render.
