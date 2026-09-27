# Devpost draft: Steadi (HackGT 13)

Checked against `main` at `2994190` (27 Sep 2026): firmware, scoring, the exercise plan, the dashboard, Grok in the product, and the judge README. The pitch deck (`internal/pitch-deck.pdf`) was not in the clone, so deck lines below are the ones in the earlier draft.

Paste everything under **Submit this**. The notes after that are for the team.

Claims follow `CLAUDE.md`: "fall-risk screening", "flags increased fall risk", "change from baseline". The copy does not say the device diagnoses, predicts when someone will fall, or prevents falls.

---

## Submit this

### Project name

Steadi

### Tagline

The CDC's fall-risk tests, scored by a belt at home. Check. Coach. Share.

73 characters. Devpost's tagline field allows 120.

### Elevator pitch

Put this directly under the tagline. **What it does** opens with the same paragraph, so the project page reads tagline, then pitch.

Steadi brings the CDC's fall-risk screening home. A belt worn at the lower back and a one-button base station run the tests in about three minutes, with a family member standing by. The belt times the walk, counts chair stands, and times each balance hold. It flags increased fall risk, tracks change from baseline, and coaches strength and balance moves, counting every rep so the family can see the exercise happened. Home is the trend in plain words. For the doctor is one page to take to the next visit.

90 words.

### Inspiration

Every second, an older adult falls (CDC). Falls are the leading cause of injury death after 65: about 41,000 deaths a year, and about $80 billion in medical costs for non-fatal falls in 2020.

Today's devices notice a fall after it happens. In one study, 80% of the oldest adults with a personal alarm did not use it when they fell alone and could not get up (Fleming and Brayne, BMJ 2008). Exercise reduces the rate of falls by 23% (Cochrane, 108 trials), but only 21% of participants in home programs were fully adherent to the prescribed dose (Simek, McPhate, and Haines, Preventive Medicine 2012).

The CDC's STEADI playbook already screens, assesses, and then recommends exercise. That happens in a clinic, maybe once a year. We run the same screening at home every week, confirm the exercises happen, and show the family the trend.

### What it does

A belt at the lower back and a one-button base station. In about three minutes, with a family member standing by, Steadi runs the CDC's fall-risk tests, flags increased fall risk, tracks change from baseline, and coaches strength and balance moves while counting every rep.

**Check.** The base station beeps each step. The screen shows one large instruction and a picture. The belt times Timed Up and Go from the "Go" beep until the person sits (a button is the stopwatch fallback), reports the slowdown when they name animals on a second walk (with the family's opt-in, Grok speech to text counts the animals named; the count never changes a score), counts a 30-second chair stand (arms used records 0), and times three balance holds beside a counter. A break has to last 0.3 seconds, so a flinch does not end the hold. Sway plays a warning beep; a real loss of balance ends the stance with an alarm. The dashboard also asks STEADI's three key questions.

Each result is compared with STEADI's cutoffs and the person's own baseline. Green, amber, or red is our summary, not STEADI's, and the lights show it. A check-in missing a core test is never green.

**Coach.** Everyone gets a plan. If chair stands or balance slip across two check-ins, it adds sit-to-stands or balance holds. Reps step up as sessions are completed, and progression pauses when exercise days drop off.

**Share.** Home is plain words, trends, and exercise days against a target of 5 a week. Check-in is full screen, meant to be read from 3 m. For the doctor is a one-page summary after any check-in, with a nudge to bring it when something flags.

Every simulated value is labelled "Simulated", including the eight-week "Simulated: Dad" history. The public demo at https://dhsquad.onrender.com runs on the simulator.

### How we built it

**Hardware.** An ESP32 and an MPU-6050, on a USB power bank at the lower back, stream 100 Hz motion over UDP. The laptop sends colours and cues back. The belt's light and buzzer play them without stopping the sensor stream, including a sway warning and a loss-of-balance alarm. An Arduino base station (one button, an RGB LED, a buzzer) talks over USB serial. A phone running phyphox is the backup. Both sketches are built with arduino-cli. Wi-Fi, the UDP port, and the serial port are settings.

**Scoring.** Orientation does not matter, so there is no calibration. Timing starts on "Go". A walk ends at stillness in a near-seated posture. Chair stands are upward-velocity peaks. A balance break is smoothed acceleration or trunk rotation that lasts 0.3 seconds. Thresholds are named constants, and `checkin replay` re-scores a saved session.

**Software.** FastAPI cues the devices, tags the stream, scores each step, and pushes live state over a WebSocket. The page is plain HTML and JavaScript, with Chart.js and the font stored locally, so the check-in works offline. The simulator, the belt, the phone, and a CSV replay share one interface, and so do the on-screen and Arduino base stations. Data is JSON, plus a CSV of every raw stream.

**Grok in the product.** Grok Imagine drew the instruction pictures, which ship as local files. Grok chat writes a 3- to 5-sentence family update from the recorded numbers. No name is sent. A reply is rejected if it invents a number, makes a forbidden claim, or uses clinical jargon, and the page labels accepted text "AI-written". Otherwise the family gets fixed wording. Ask Steadi answers a short question from those same numbers, through the same checks. Grok Voice speaks the check-in cues in a soft, soothing voice, generated ahead of time so they play offline, and a Listen button reads the summary. With the family's opt-in, Grok speech to text counts the animals named on the dual-task walk; only the names and counts are kept. A switch, or `CHECKIN_AI=off`, turns every Grok call off. The check-in still works.

**Cursor.** We ran many agents in parallel and sent each task to the model better at it: Grok for rapid idea checks, Claude and Grok for the backend, Codex and Grok for the UI and visual design. Cursor can guide an agent while it is still running. We often confirmed a new idea while agents were already spinning, which is how the sway warning and the foot pictures made it in.

**Testing.** pytest, including a full simulated check-in scored against the simulator's true values, and ruff. Agreement with a stopwatch and hand counts on real people is still to be measured.

### Challenges we ran into

The venue had no soldering tools, so we soldered headers at a makerspace and built on a simulator until the belt was ready. Telling "sat down" from "paused while standing" took a posture check against the seat before "Go", with the button kept as a stopwatch. Balance used to end on any flinch. A break now lasts 0.3 seconds, sway warns first, and a missing sensor tail scores as not measured. Late packets, Wi-Fi gaps, and double-taps had to be ignored, and the belt had to beep without dropping its 100 Hz stream. A fluent family summary is easy to generate. One that never invents a number, or says it predicts a fall, has to be checked. Families need one big action. Doctors need the rule for each number. Those are separate views.

### Accomplishments that we're proud of

- The STEADI loop runs end to end, on the belt, a phone, a recording, or the simulator: the questions, three tests plus a dual-task walk, coached exercise, and tracking.
- Every rep is counted and every hold is timed. A helper stands by for the check-in. Solo exercise is limited to supported moves.
- The family summary is checked before it is shown, labelled AI-written, and replaced with fixed wording on any doubt.
- The check-in works offline, with body text of at least 18 px, AA contrast, and 44 px targets. Simulated data is labelled. A missing test is never shown as all-clear.

### What we learned

Following the clinical timing, from "Go", and recording 0 when arms are used, removed sensing problems such as detecting when a walk starts. Swappable devices let several agents work at once. Sending each task to the model better at it, and guiding agents while they were still running, beat one long chat. In a health product, the checks on the model's output matter more than the prompt. Balance is the hardest score, which matches published lower-back IMU work: within about 4% on Timed Up and Go, about 8% on chair stands, and less well on balance.

### What's next

Validate on real people and publish the stopwatch and hand-count agreement. `checkin validate` is already built. Commit the generated Grok Voice files so the cues play offline. Then check the animal count against a hand tally, optional gait quality, and a pilot with a per-unit cost.

### Built with

python, fastapi, uvicorn, websockets, numpy, pyserial, javascript, html5, css, chart.js, esp32, arduino, arduino-cli, mpu-6050, c++, udp, phyphox, xai, grok, grok-imagine, grok-voice, speech-to-text, cursor, claude, codex, pytest, ruff, uv, render

### Track fit

**The Shipyard (Hardware).** Steadi is a wearable with a job. An IMU belt streams 100 Hz motion over Wi-Fi, and its light shows the check-in state. A one-button base station cues each step, so the check-in is not an app on the older adult's phone. The belt sits at a standard placement at the lower back, and there is one button to press. Both firmware sketches, the belt-to-laptop UDP protocol, and the serial protocol are ours. Judges can clip on the belt and do a 30-second chair stand while the dashboard scores it live.

**Aramco, A Marina's Mission (social good: health).** Falls are the leading cause of injury death for adults 65 and older. Steadi brings the CDC's own STEADI fall-risk screening from a yearly clinic visit to a weekly routine at home, and pairs it with strength and balance exercise of the type shown to reduce the rate of falls. The belt confirms the exercise was done. It is built for the people it serves: plain language for families, a one-page summary for the doctor, large text and AA contrast, and a check-in that works offline. It flags increased fall risk and tracks change from baseline. It does not diagnose, and we have not run a clinical trial.

**SpaceXAI, Make it Legendary (Cursor + Grok).** We used Cursor to run many agents in parallel, and we sent each kind of task to the model that was better at it. Grok did rapid idea verification. Claude and Grok built the backend. Codex and Grok did a lot of the frontend and the UI and visual design. Cursor can guide an agent while it is still running, so when we had a new idea we wanted confirmed we steered the agents that were already spinning instead of starting over. Grok is also in the product, aimed at public health. Grok Imagine drew every instruction picture. A Grok model writes the family's update, and answers Ask Steadi, from the recorded numbers inside a strict check: no invented numbers, no diagnosis or prediction claims, no jargon, and fixed wording as the fallback. Grok Voice speaks the check-in cues and reads the family summary aloud, and Grok speech to text counts the animals named on the dual-task walk. A switch turns every Grok call off, and the check-in still works.

### Video demo script (about 2 minutes)

Three teammates narrate, and Allen does the physical demo.

| Time | On screen | Voice-over |
|---|---|---|
| 0:00–0:15 | "Every second, an older adult falls." Then about 41,000 deaths a year, and about $80 billion in medical costs for non-fatal falls (2020). | Speaker 1: "Falls are the leading cause of injury death after 65." |
| 0:15–0:30 | The alarm finding (80% did not use it) and "21% fully adhered to a prescribed home program." | Speaker 1: "Today's devices notice a fall after it happens. Exercise cuts the rate of falls by 23%, and almost nobody completes the home program." |
| 0:30–0:40 | The belt, the base station, and the tablet. Title card: Check. Coach. Share. | Speaker 2: "Steadi turns the CDC's fall-risk tests into a 3-minute routine at home." |
| 0:40–1:10 | Allen, with a teammate standing by, does the check-in: Timed Up and Go on the "Go" beep, a clip of the walk while naming animals, chair stands counting up, and a balance hold with the foot picture and a sway warning beep. | Speaker 2: "Check: the belt scores the CDC's own tests. It times the walk, counts stands, and times each balance hold, with a warning beep if he sways." |
| 1:10–1:20 | The result screen, then the light turning green, amber, or red. | Speaker 2: "Results in plain words, and the light shows the level." |
| 1:20–1:35 | Exercise mode: a short set of sit-to-stands with a beep and a count per rep, then the week's exercise days. | Speaker 3: "Coach: strength and balance moves, and every rep counted." |
| 1:35–1:50 | "Simulated: Dad", with the Simulated label visible: a flag, the trend, the For the doctor view and printout, the family summary with its AI-written tag, and the Listen button. | Speaker 3: "Share: the family sees the trend, and the doctor gets a one-page summary. Grok writes the family update inside strict checks." |
| 1:50–2:00 | A short capture of Cursor with parallel agents, then the closing card with the website URL. | Speaker 3: "Built in Cursor. Grok checked the ideas, Claude and Grok built the backend, Codex and Grok built the screen. Steadi: Check. Coach. Share." |

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
| Steadi turns the CDC's fall-prevention playbook into a 3-minute routine. | 72 | A spoken opener, if you want the deck's sentence. "Playbook" means STEADI, the CDC program. Say it in the video, not as the only line on the card. |
| A 3-minute home check-in that flags increased fall risk and counts every rep. | 77 | The most literal description. Use it if the form has a second short-description field. |
| The CDC's fall-risk tests, scored by a belt at home. Every rep counted. | 71 | Same shape as the recommended line, with the exercise proof instead of the three-beat closer. |
| Today's answers come too late. Steadi starts before a fall. | 59 | Leave this off the card. "Before a fall" is easy to hear as "predicts" or "prevents". The inspiration section already says today's devices notice a fall after it happens. |

## Elevator pitch

The 90-word paragraph above is the one to paste. Read aloud it is about 35 seconds, which is one breath longer than a strict 30-second booth intro and short enough to sit under a title.

If a judge is already holding the belt, start one sentence later: "A belt at the lower back and a one-button base station. Three minutes, someone standing by. It times the walk, counts the stands, times the holds, flags increased fall risk, and counts every exercise rep."

## Deck lines, resolved from the code

- The belt has a motion sensor, an RGB LED, and a buzzer. The laptop sends LED colours and cues over UDP, and the belt plays them without stopping the sensor stream, including a sway warning and a loss-of-balance alarm. The button is on the Arduino base station, or on the screen. The base station also has a light and a buzzer. The demo slide should say: a motion sensor, a light, and a buzzer on the belt; a button, a light, and a buzzer on the base station.
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
- Stopwatch and hand-count agreement. The tool is in the repo (`checkin validate`, `docs/VALIDATION.md`); no real trials are recorded yet. The testing paragraph says it is still to be measured.
- Spoken cue mp3s. The Grok Voice code, the Listen button, and `scripts/make_voice.py` are on main. `src/checkin/static/audio/` has the index and no mp3s yet, so a check-in with no generated files uses the browser's voice. What's next says to generate and commit those files (they will be in the carina voice).
- The animal count has only been tested with mocked speech to text and the bundled sample. Try it once with the key and a close mic before filming.
- A balance break lasts 0.3 seconds (`BREAK_MIN_S` in `src/checkin/signals.py`). Sustained sway plays `CUE warn` before a loss of balance plays `CUE alarm`.
- Per-unit cost. `docs/COMPETITION.md` still says to fill this in before judging.
- Image files for the gallery. The shot list is above. Photos of the belt, the base station, and a person wearing the belt still have to be taken. There is no CAD file in the repo to render.
