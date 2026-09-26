# Competition Context & Strategy

Single source of truth for the hackathon plan. Hardware: `PARTS_LIST.md` (final build) and `BOM.md` (everything available). **Section 0.1: no soldering at the hackathon; solder at Hive.**

---

## 0. Final Decision (TL;DR)
**Fall prevention for older adults living at home: the CDC's STEADI fall-prevention algorithm (screen → assess → intervene), turned into a belt and a button, plus tracking over time.**
- **Screen:** STEADI's three key questions (fallen in the past year? unsteady? worried about falling?), answered in the family dashboard.
- **Assess (fall-risk prediction):** a ~3-minute guided check-in running STEADI's three tests (Timed Up and Go, 30-second chair stand, balance stances), plus Timed Up and Go while naming animals (dual-task). The belt scores everything against STEADI cutoffs and a personal baseline.
- **Intervene (prevention):** the device coaches balance and strength exercises, the kind shown to cut falls, and the belt counts reps and times holds, so we know they were done.
- **Track:** the family dashboard shows flags, trends, and exercise adherence, and says when to see a doctor.
- **Hardware:** ESP32 + MPU-6050 belt unit (phone as backup), an Arduino base station (button, RGB LED, buzzer), my laptop. Software runs on a simulator until hardware is ready.

**Pitch:** "Dad won't press a pendant, and he won't do exercises from a pamphlet. Our belt checks his fall risk in three minutes with the CDC's own tests, coaches the kind of exercise shown to cut falls by about a quarter, and shows the family both."

---

## 0.1 Hardware Constraint & Resolution
**Constraint:** the hackathon hardware desk has **no soldering irons, alligator clips, or wire strippers.**

**Resolution:** one trip to the makerspace (Hive), where we can solder. Parts and checklist: `PARTS_LIST.md`.
1. **Belt unit:** ESP32 + MPU-6050, headers soldered at Hive, female-female jumpers, USB power bank, UDP broadcast over Wi-Fi. Test at Hive before leaving.
2. **Base station (solderless, on the table):** Arduino + breadboard with start button, RGB LED, passive buzzer, USB to the laptop.
3. **Backup sensor:** a phone in a belt pouch running phyphox remote access.
4. **Software is hardware-agnostic:** simulator and on-screen base station by default.
5. **Never demo press-fit (unsoldered) connections.**

Checkout items (ESP32, MPU-6050): confirm the checkout covers the hackathon, and whether soldered headers can stay on when returned.

---

## 1. Competition Details
- **Length:** 36 hours · **Size:** ~1,200 participants; ~30 teams on the hardware track
- **Judges:** appear to be software engineers
- **TBD:** dates, rubric, demo format/length, submission requirements, prizes, track rules

## 2. What This Means for Us
- A working demo is the baseline. What wins: a clear angle, a demo on the judge's own body, a "why hardware" answer, and evidence it works.
- Expect: "How do you know it works?", "Why not a phone app?", "What's new?", "Does it actually prevent falls?"

---

## 3. Idea Selection
**Chosen:** fall prevention (screen → assess → intervene → track). Strongest stats, fits the hardware, personal story (a teammate's dad), validated clinical tests, and high-certainty evidence for the intervention.
**Backup:** recycling contamination sorter (Pi + camera + stepper). Common hackathon project; moving parts add demo risk.
**Dropped:** ocean sensors, wildfire/air/ethylene sensing (no suitable sensors), intracranial pressure (not feasible).

---

## 4. The Angle

### What already exists
| Existing solution | What it does | Gap |
|---|---|---|
| Alert pendants / Apple Watch fall detection | Detects a fall after it happens | Nothing before the fall; low use (~6% of older adults with mobility difficulties), many false alarms |
| Apple Walking Steadiness | Passive walking analysis from an iPhone in a pocket; points to exercises | Walking only; needs an iPhone; can't confirm exercises happen |
| Zibrio SmartScale (~$499 reported) | 60-second home standing-balance test; app suggests exercises | Standing balance only; can't confirm exercises happen |
| Kinesis QTUG | Validated sensor-based Timed Up and Go | Clinician-administered |
| Lower-back IMU STEADI study (2024) | Automates TUG, chair stand, balance; within 4–8% of human raters | Research, clinician-run |

### Our angle
1. **The whole STEADI algorithm at home, guided by a device**: the three key questions, all three tests (not just walking or just balance), plus a dual-task Timed Up and Go.
2. **Sensor-verified prevention:** others suggest exercises; we count the reps and time the holds, so the family sees whether they happened.
3. **Screen-free for the senior:** one button; the base station cues every step.
4. **Built on validated tests and open-source clinical algorithms**, not a homemade score.

### Evidence (verified)
- **STEADI (CDC):** screen with three key questions ("yes" to any = at risk), assess gait, strength, and balance with TUG, 30-second chair stand, and the 4-stage balance test, then intervene (including referral to exercise). Cutoffs: TUG ≥12 s; chair stand below the age/sex average (table in Section 5); full tandem stance held <10 s.
- **Exercise prevents falls:** Cochrane review, 108 trials, 23,407 people (average age 76): exercise reduces the rate of falls by **23%** (high-certainty). Balance and functional exercise: **24%**. Multiple exercise types (balance + functional + resistance): about **34%** (moderate certainty). These effects come from structured programs; our coached subset (sit-to-stands, supported balance) is the same *type* of exercise but untested.
- **Sensors can run STEADI:** a lower-back IMU matched human raters within ~4% on TUG and ~8% on chair stands (2024). Balance timing agreed less well (a single-leg stance equivalence zone of ~23%), so balance is our least certain score.
- **Dual-task:** a meta-analysis found dual-task changes while walking predict falls. Caveat: reviews find dual-task walking speed about equal to normal walking speed for fall prediction; it's one test among several, not the headline. (In people with mild cognitive impairment, dual-task walking is also linked to dementia progression; mention only if asked.)

### Claims
**We say:** fall-risk screening with the CDC's STEADI tests; flags increased fall risk; tracks change from baseline; coaches exercises of the type shown to reduce falls, and verifies they were done.
**We never say:** it diagnoses anything, predicts *when* someone will fall, or guarantees prevention. We haven't run a trial.

---

## 5. The Check-In (~3 Minutes, Safe by Design)
| Step | Task | Measures | STEADI flag |
|---|---|---|---|
| 0 | (Profile, family dashboard) STEADI three key questions | Screening | "Yes" to any |
| 1 | **Timed Up and Go:** on the buzzer's "Go," stand up, walk to a line 3 m (10 ft) away, turn, walk back, sit | TUG time | ≥12 s |
| 2 | **TUG while naming animals out loud** | Dual-task TUG time → dual-task cost | (ours; tracked vs. baseline) |
| 3 | **30-second chair stand**, arms crossed; on "Go," stand fully and sit, repeatedly for 30 s | Stands in 30 s (a stand over halfway at 30 s counts) | Below average for age/sex |
| 4 | **Balance beside a counter:** feet together → semi-tandem → full tandem, 10 s each (stop at first failure) | Hold time + sway per stance | Tandem <10 s |
| 5 | (Upgrade) 30 s walk along a wall | Gait quality (SKDH), walking speed | (ours) |

**Chair stand, below-average scores (STEADI):**
| Age | 60–64 | 65–69 | 70–74 | 75–79 | 80–84 | 85–89 | 90–94 |
|---|---|---|---|---|---|---|---|
| Men | <14 | <12 | <12 | <11 | <10 | <8 | <7 |
| Women | <12 | <11 | <10 | <10 | <9 | <8 | <4 |

**Setup (per STEADI):** TUG uses a standard **arm chair**; the chair stand uses a **straight-back chair without arms, ~17-inch seat**. If only one chair is available, use the armless one for both and note the deviation. Regular footwear; walking aids allowed in TUG. A taped 3 m line; a counter or wall for balance.
**Timing (per STEADI):** TUG and chair-stand timing start on the "Go" cue (the buzzer), not on detected movement. TUG ends when the person is seated again. This matches the clinical protocol and means the sensor only has to detect sit-down and count stands.
**Dual-task cost** = (dual-task TUG time − normal TUG time) ÷ normal TUG time × 100.
**Fall-risk level (our summary, not STEADI's):** a flag is a "yes" to any key question or any test past its cutoff. Green = no flags; amber = 1 flag or a sustained decline vs. baseline; red = 2+ flags. Always show which items flagged. Per STEADI, everyone (flagged or not) gets exercise-based prevention.
**Safety rules:** STEADI's instructions say to stay by the person during the tests, so **the weekly check-in is done with a family member standing by**. Balance next to a counter with a hand hovering; no single-leg (stage 4) or eyes-closed tests; auto-stop if sway spikes; stop the chair stand if arms are needed (STEADI records a 0). **Solo exercise mode** is limited to supported moves: sit-to-stands from a sturdy chair and counter-supported balance holds.
**Cadence:** check-in weekly with family present; exercises most days.

### Exercise mode (prevention)
- **Sit-to-stands** (sets of 5–10), counted by the belt, buzzer beep per rep.
- **Supported balance holds** (feet together → semi-tandem → tandem), timed by the belt, progressing as holds succeed.
- The plan leans on the weakest area: low chair-stand score → more sit-to-stands; balance flag → more holds.
- Every session is logged; the dashboard shows adherence and whether scores improve.

---

## 6. Hardware Map
| Role | Item | Source | Notes |
|---|---|---|---|
| Motion sensor | **ESP32 + MPU-6050** belt unit + USB power bank | Hive + personal | ±8 g, ±500 °/s, 100 Hz via FIFO; UDP broadcast; lower back. The gyroscope helps detect the TUG turn and sit-down. |
| Backup sensor | **Phone** in a belt pouch | Pixel / personal | phyphox remote access |
| Base station | **Arduino** + breadboard + button + RGB LED + passive buzzer | Team / Hive | USB serial; buzzer cues steps and reps; LED shows green/amber/red |
| Dev + demo machine | **My laptop** | Personal | Claude Code, firmware uploads, session controller, dashboard |
| Dashboard | **Dell Venue 10 Pro tablet** | BOM | Browser |
| Network | **Phone hotspot** (or the Access Point) | Personal / BOM | Never venue Wi-Fi for devices |
| Test station | Arm chair (TUG) + armless ~17-inch chair (chair stand), 3 m tape line, counter | Venue / Hive | Per STEADI setup |
| Audio upgrade | Second phone + wired earbuds with inline mic; keyboard tally fallback | Pixel / personal / BOM | Confirms talking during the dual-task TUG |

**Not used:** LilyPad, haptic breakout, vibration motor, stepper, relays, RFID/NFC, Gear VR, Edisons. WYZE: stretch only.

---

## 7. Software Architecture
**The laptop is the session controller.** For each step it cues the base station (USB serial), tags the incoming motion stream (ESP32 UDP or phone) with the step ID, scores the step, and pushes results to the dashboard.

**Scoring (core, no SKDH needed):**
- **TUG time:** from the "Go" cue to the final sit-down, detected from acceleration + gyroscope (trunk pitch settles; motion stops).
- **Chair stands:** count of full stands in the 30 s after "Go," from trunk-pitch/vertical-acceleration cycles; a stand past halfway at 30 s counts.
- **Balance:** hold time until the stance breaks (sway threshold or step), plus RMS sway.
- **Exercise mode:** rep counting and hold timing reuse the chair-stand and balance code.
- **Flags and trends:** STEADI key questions + test cutoffs (needs age and sex in the profile), rolling baseline, decline alert.

**Why step-level sync:** every score is a whole-step total, so sub-second alignment across streams doesn't matter.

**Upgrades:** talk detection during the dual-task TUG (close mic, voice activity detection); animal counting (Vosk restricted vocabulary or faster-whisper); SKDH gait quality on the optional walk; Claude plain-language weekly summary; fall safety net (never the headline).

**Everything stays local:** "data never leaves the house" is our privacy answer.

---

## 8. SKDH (Optional)
Pfizer's open-source (MIT) gait library: https://github.com/pfizer-opensource/scikit-digital-health. Only used for the optional walk (step 5): cadence, stride regularity, symmetry. Defaults: 8 s minimum walking bout; turns need gyroscope data. Compiled extensions; unreliable on Windows. **No core score depends on it.**

---

## 9. Data & Literature
- **CDC STEADI** materials: TUG, 30-second chair stand, 4-stage balance, cutoffs above.
- **Cochrane exercise review** (CD012424, 2019; 108 RCTs): numbers in Section 4.
- **2024, Archives of Gerontology and Geriatrics Plus:** lower-back IMU STEADI agreement with human raters.
- **Kinesis QTUG** (Greene et al.): large-scale sensor-based TUG.
- **Chu et al. 2013:** meta-analysis of dual-task walking for fall prediction. **Wollesen et al. 2019:** dual-task vs. normal speed.
- **PhysioNet LTMM** (optional gait-model upgrade): 71 older adults, fallers (2+ falls in the past year) vs. non-fallers, 1-minute lab walks. Labels are past falls. Use LabWalks only.

---

## 10. Risk Register (Ranked by Impact)

### Tier 1: Could lose us the track
0. **No soldering at the hackathon.** *Fix:* solder and test at Hive; spare MPU-6050; tape/glue jumpers; phone backup.
1. **"What's new? Zibrio/Apple/QTUG exist."** *Fix:* all three STEADI tests at home + sensor-verified exercise; name competitors first.
2. **"Why hardware, not a phone app?"** *Fix:* dedicated belt at a standardized placement; one button, no screen for the senior; the people most at risk are least able to run an app.
3. **The core measurement fails live.** *Fix:* core scores are simple timings and counts; a teammate with the base-station button can act as a stopwatch fallback.
4. **Safety** (TUG, tandem stance, dual-task, exercise at home). *Fix:* family member stands by for the check-in, as STEADI's instructions require; solo exercise limited to supported moves (Section 5); say it proactively.
5. **Overclaiming prediction or prevention.** *Fix:* claim language in Section 4.

### Tier 2: Hurts credibility or the demo
6. **Healthy young judges pass every test, and STEADI chair-stand norms start at age 60.** *Fix:* show the judge's raw numbers vs. the 60–64 norm, labeled as such; the "Simulated: Dad" dashboard shows what a flag looks like; the dual-task cost shows a real effect on the judge.
7. **Sit-down detection (end of TUG) and balance timing are the least certain scores.** Published IMU agreement was weakest for balance. *Fix:* timing starts on the "Go" cue (no onset detection needed); gyroscope + stillness for sit-down; stopwatch agreement checks for TUG and each balance stance.
8. **Participant stops talking during dual-task.** *Fix:* talk-detection upgrade or a teammate watching.
9. **Validation is limited.** *Fix:* agreement checks: TUG vs. stopwatch, chair stands and reps vs. hand count, balance holds vs. stopwatch.
10. **Day-to-day noise vs. real decline.** *Fix:* alerts on rolling averages.
11. **One laptop does everything.** *Fix:* push to GitHub often; keep the charger at hand.

### Tier 3: Nitpicks
Sensor tilt calibration; Wi-Fi drops (own network); animal word list edge cases; LLM summary is garnish; WYZE cut first.

---

## 11. Verification Log
**Confirmed by the team:** no soldering tools at the hardware desk; the Hive "Accelerometer" is an MPU-6050 (GY-521) with unsoldered headers; passive buzzer on hand.
**Verified by research:** STEADI algorithm (three key questions → TUG, chair stand, 4-stage balance → intervene); STEADI setup (TUG in a standard arm chair, 3 m/10 ft line, timing from "Go" to seated; chair stand in an armless ~17-inch chair; stay by the person); cutoffs (TUG ≥12 s, chair-stand table, tandem <10 s); Cochrane exercise effect sizes; 2024 IMU STEADI agreement (weakest for balance); competitor features; SKDH defaults; LTMM contents; Uno R4 GPIO limit (8 mA per pin).
**Not yet tested (hours 0–4):** ESP32 streams at 100 Hz without drops; power bank doesn't auto-shut off; TUG onset/turn/sit detection works on real data; chair-stand counting matches hand counts.

---

## 12. Before the Hackathon (In Order)
Step-by-step: `KICKOFF_PROMPT.md` (outside the repo).
1. **Tools:** setup prompt (uv, Python 3.11, arduino-cli, ESP32 core, MPU-6050 libraries).
2. **Hive trip:** `PARTS_LIST.md` Section 7; test the belt unit before leaving.
3. **Network:** laptop, ESP32, tablet all on a phone hotspot.
4. **Backup phone:** phyphox remote access tested.
5. **Base station parts** on hand; **USB power bank** tested 20+ minutes.
6. **Test station:** an arm chair (TUG) and an armless ~17-inch chair (chair stand), tape for a 3 m line, counter or wall.
7. (Upgrades) wired earbuds with mic; LTMM LabWalks downloaded.

---

## 13. 36-Hour Plan (Parallel Tracks)
| Hours | Motion (firmware + scoring) | Product (controller + dashboard) | Prevention + validation |
|---|---|---|---|
| 0–4 | Simulator; ESP32 UDP streaming; base station wired | Controller skeleton; step tagging | Record real TUG/chair/balance samples with the belt |
| 4–12 | TUG time, chair-stand count | Dashboard: live steps, results card | Balance hold/sway |
| 12–20 | Dual-task TUG; STEADI flags | Baseline, trends, alerts | Exercise mode (reps, holds, adherence) |
| 20–24 | **Full screen → assess → intervene → track loop working. Core freeze at hour 24.** | | |
| 24–30 | Belt mounting; phone backup | Simulated "Dad" story; LLM summary | Agreement checks (stopwatch, hand counts) |
| 30–36 | Rehearse, backup video, submit | | |

**Kill criteria:**
- **Hour 4:** ESP32 streaming unreliable → phone backup.
- **Hour 12:** TUG detection unreliable → base-station button as start/stop timer (still device-timed).
- **Hour 12:** audio not working → drop audio; teammate confirms talking.
- **Hour 24:** feature freeze.

**Cut order if behind:** WYZE → LLM summary → fall safety net → SKDH walk → animal counting → talk detection → simulated trend view → LED result on base station. **Never cut the three STEADI tests or exercise mode.**

---

## 14. Demo Script (~3 Minutes)
1. **Hook (20 s):** the dad story. "1 in 4 older adults falls every year. Pendants only help after, and in one study of the oldest adults, 80% who fell alone never pressed theirs."
2. **Judge check-in (80 s):** a teammate stands by (as STEADI requires); the judge puts on the belt and presses the button. The base station cues TUG, dual-task TUG, chair stand, balance. Dashboard shows each score against the STEADI cutoffs, plus the judge's dual-task cost.
3. **Prevention (30 s):** exercise mode: judge does 5 sit-to-stands; each rep beeps and counts on screen.
4. **Product view (30 s):** "Simulated: Dad": chair stands slipping → amber flag → exercise plan → adherence → scores recovering.
5. **Evidence (15 s):** CDC STEADI tests; exercise cuts falls ~23% (Cochrane, 108 trials); our stopwatch/hand-count agreement.
6. **Close (5 s):** "Catch the risk. Coach the fix. Show the family."

---

## 15. Judge Q&A Prep
- **"Can it predict falls?"** → It flags increased fall risk with the CDC's own screening tests and tracks it over time. It doesn't predict when someone will fall.
- **"Does it actually prevent falls?"** → It coaches the kind of exercise that cut falls ~23% across 108 trials, and verifies it's done. We haven't run our own trial.
- **"What's new?"** → Others test one thing (walking or balance) and suggest exercises. We run the CDC's whole STEADI screen-assess-intervene loop at home and verify the exercises happen.
- **"Why hardware, not a phone app?"** → Dedicated belt at a standardized placement, one button, no screen. Phones can measure this; the people most at risk can't reliably run an app.
- **"How do you know it works?"** → Agreement with stopwatch and hand counts; a published lower-back IMU study matched human raters within 4–8% using the same approach.
- **"Why the talking walk?"** → Real-life walking involves doing other things; dual-task changes predict falls in meta-analysis. (In people with mild cognitive impairment, it's also linked to dementia progression.)
- **"Is it safe to do alone?"** → The weekly check-in isn't done alone: like the clinical version, someone stands by. Solo exercises are supported moves only (sturdy chair, counter). No single-leg or eyes-closed tests; auto-stop on large sway.
- **"Privacy?"** → Data stays local, shared only with chosen family.
- **"Cost?"** → Fill in a per-unit estimate before judging.

---

## 16. Pitch Stats
- **Falls:** 14M+ U.S. adults 65+ (about 1 in 4) report falling each year; falls are the leading cause of injury death for 65+; the age-adjusted fall death rate rose 21% from 2018 to 2024. (CDC)
- **Alarm non-use:** 80% of the oldest adults with a personal alarm didn't use it when they fell alone and couldn't get up.
- **Low adoption:** only ~6% of older adults with mobility difficulties used a personal call alarm. (English Longitudinal Study of Ageing)
- **False alarms:** 58% of alarm-triggered ambulance calls were false alarms in one Australian audit.
- **Long lies:** two-thirds of people who fell couldn't get up unassisted.
- **Prevention works:** exercise reduces the rate of falls by 23% (Cochrane, 108 trials, 23,407 people; high-certainty evidence).
