"use strict";
// Dashboard: renders GET /api/people/{id}/dashboard and the /ws state stream (docs/API.md) in three views:
// Home (family and the person), Check-in (one step at a time), For the doctor (every clinical number).

const $ = (id) => document.getElementById(id);
const QUICK_PLAN = { sit_to_stand: { sets: 1, reps: 5 }, balance: { stance: "feet_together", holds: 0, target_s: 20 } };
// Buzzer cues from firmware/PROTOCOL.md: [frequency Hz (0 = silence), milliseconds]
const CUES = {
  start: [[2000, 150], [0, 80], [3000, 150]],
  stop: [[1500, 600]],
  done: [[2093, 150], [2637, 150], [3136, 250]],
  error: [[800, 100], [0, 80], [800, 100], [0, 80], [800, 100]],
  rep: [[2500, 80]],
  warn: [[2500, 70], [0, 70], [2500, 70], [0, 70], [2500, 70]], // swaying: helper, step closer
  alarm: [[1000, 250], [0, 100], [1000, 250], [0, 100], [1000, 250], [0, 100], [1000, 250]], // lost balance
};
const VIEWS = ["home", "checkin", "doctor"];
// Home names a level by what to do; the doctor view names the colour.
const LEVEL_MEANING = { green: "No flags", amber: "Mention to the doctor", red: "Talk to a doctor soon" };
const LEVEL_NAME = { green: "Green", amber: "Amber", red: "Red" };
const CORE = ["tug_s", "chair_stands", "tandem_s"]; // a check-in missing these can't be "No flags"
const CHANGE_UNITS = { tug_s: " s", dual_task_cost_pct: " points", chair_stands: " stands", tandem_s: " s" };
// Plain words for the Home and Check-in views.
const STEP_TITLE = {
  tug: "Stand up and walk",
  dual_tug: "Walk again, naming animals",
  chair_stand: "Stand up from the chair, again and again",
  balance_feet_together: "Stand still: feet together",
  balance_semi_tandem: "Stand still: one foot a little ahead",
  balance_tandem: "Stand still: one foot in front of the other",
};
const STANCE_WORDS = {
  feet_together: "feet together", semi_tandem: "one foot a little ahead of the other",
  tandem: "one foot right in front of the other",
};
const ANSWERED_YES = {
  fallen: "has had a fall in the past year", unsteady: "feels unsteady when standing or walking",
  worried: "worries about falling",
};
const TRACKED_WORDS = {
  tug_s: "standing up and walking", chair_stands: "leg strength", tandem_s: "balance",
  dual_task_cost_pct: "walking while naming animals",
};
// The API only marks a change as `worse` (docs/API.md: TUG +10%, chair stands −2, tandem −3 s).
// "Better than usual" is the same distance the other way.
const USUAL = {
  tug_s: { dir: +1, limit: (base) => 0.1 * base },
  chair_stands: { dir: -1, limit: () => 2 },
  tandem_s: { dir: -1, limit: () => 3 },
};
// Chart colours follow the page tokens in index.html.
const COLOR = { ink: "#080912", blue: "#2a4093", muted: "#464b5d", line: "#d5d9e2", red: "#b42318" };
const GO_S = 1.5; // the whole-screen "Go"
const REST_S = 2; // "Done. Rest a moment." between steps
const GO_GUARD_S = 3; // controller.GO_GUARD_S: presses this soon after "Go" are ignored

let personId = null;
let state = null;
let audio = null;
let online = null; // null while the first WebSocket connects
let view = null;
let ended = false; // a session ended while this page watched: show its result on the Check-in view
let setup = false; // the setup checklist shows before a check-in starts
let lastRunning = null; // the step that was running at the last state message
let goFor = null;
let goUntil = 0;
let restUntil = 0;
let stageKey = null; // step and stage last announced
let warningsText = "";
let revealed = false;
let profileReady = false; // age and sex given: the check-in can compare leg strength
let newPerson = false; // the profile form is adding a person, not editing this one
let lastPerson = null;
let hasCheckin = false;
let making = false;
let aiStatus = null; // GET /api/ai; null until loaded, then Ask Steady stays hidden unless it's on
let asking = false;
let everOnline = false; // the first failed connection says "can't connect", later ones "lost the connection"
const LAST_PERSON = "checkin.person"; // this browser reopens on the person it showed last
const charts = {};

function h(tag, text, attrs = {}) {
  const el = document.createElement(tag);
  if (text !== undefined && text !== null) el.textContent = text;
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

function simTag() {
  return h("span", "Simulated", { class: "tag" });
}

// Chart x labels: a simulated point gets a second line reading "Simulated".
function simLabels(labels, simulated) {
  return labels.map((label, i) => (simulated[i] ? [label, "Simulated"] : label));
}

// A big number with its unit; null or undefined is drawn as "Not measured", never as zero.
function big(v, unit) {
  const absent = v === null || v === undefined;
  const el = h("span", null, { class: absent ? "value absent" : "value" });
  el.append(h("span", absent ? "—" : String(v), absent ? { class: "num", "aria-hidden": "true" } : { class: "num" }));
  if (absent || unit) el.append(h("span", absent ? "Not measured" : unit, { class: "unit" }));
  return el;
}

// "2026-08-29T10:00:00" (local time, no zone) -> "Sat, Aug 29, 10:00 AM"; "2026-08-08" -> "Aug 8";
// long: "Saturday, August 29" (the same as the summary text).
function when(iso, long = false) {
  const [y, mo, d, hh = 0, mm = 0] = iso.split(/[-T:]/).map(Number);
  const date = new Date(y, mo - 1, d, hh, mm);
  if (long) return date.toLocaleDateString("en-US", { weekday: "long", day: "numeric", month: "long" });
  const opts = iso.includes("T")
    ? { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }
    : { day: "numeric", month: "short" };
  return date.toLocaleString("en-US", opts);
}

const seconds = (v) => `${v} ${v === 1 ? "second" : "seconds"}`;
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const chairGroup = (c) => (c.chair_label || "").replace(/\s*\(.*\)$/, ""); // drop "(the youngest STEADI group)"

// Per-browser convenience only; private windows and blocked storage just fall back to the first person.
function recallPerson() {
  try {
    return localStorage.getItem(LAST_PERSON);
  } catch {
    return null;
  }
}
function rememberPerson(id) {
  try {
    localStorage.setItem(LAST_PERSON, id);
  } catch {
    // not remembered; nothing else depends on it
  }
}

// Errors come back as plain sentences, never a status code or raw JSON.
async function api(method, path, body) {
  let r;
  try {
    r = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Can't reach the laptop. Check that the check-in app is running, then try again.");
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    if (r.status === 403) { // the only 403: the simulated person is read-only
      const err = new Error("This person is example data and can't be changed.");
      err.status = 403;
      throw err;
    }
    const field = Array.isArray(data.detail) ? data.detail[0]?.loc?.at(-1) : null; // 422: which field
    const text = typeof data.detail === "string" ? data.detail.charAt(0).toUpperCase() + data.detail.slice(1)
      : field ? `Please check the ${field}.` : "Something went wrong. Please try again.";
    const err = new Error(/[.!?]$/.test(text) ? text : `${text}.`);
    err.status = r.status;
    throw err;
  }
  return data;
}

function say(text) {
  $("msg").textContent = text;
}

function play(name) {
  if (!state || state.base !== "virtual" || state.source.beeps || !audio) return; // a base station or the belt beeps itself
  let t = audio.currentTime;
  for (const [freq, ms] of CUES[name] || []) {
    if (freq) {
      const osc = audio.createOscillator();
      const gain = audio.createGain();
      osc.type = "square";
      osc.frequency.value = freq;
      gain.gain.value = 0.05;
      osc.connect(gain).connect(audio.destination);
      osc.start(t);
      osc.stop(t + ms / 1000);
    }
    t += ms / 1000;
  }
}

// ---- voice: Grok-voiced files from scripts/make_voice.py, else the browser's own voice -------------
// Speech only explains. The clock starts on the button and "Go" is the buzzer, so nothing waits for it.
let voiceFiles = {}; // exact text → file in /static/audio
let voiceNow = null; // the <audio> playing
let voiceDone = null;
fetch("/static/audio/index.json", { cache: "no-cache" })
  .then((r) => (r.ok ? r.json() : {}))
  .then((m) => (voiceFiles = m))
  .catch(() => {});

function hush() {
  const done = voiceDone;
  voiceDone = null;
  if (voiceNow) voiceNow.pause();
  voiceNow = null;
  if (window.speechSynthesis) speechSynthesis.cancel();
  if (done) done();
}

// The system default (often a compact male voice) sounds mechanical. Prefer a local natural English voice.
const HUMAN_VOICE = /natural|neural|premium|enhanced|aria|jenny|sonia|libby|sara|samantha|karen|moira|serena|fiona|zira|google .+ english/i;
const HARSH_VOICE = /david|espeak|compact|robot|zarvox|trinoids|boing|whisper|fred|\bmark\b/i;

function pickSpokenVoice(voices) {
  const en = voices.filter((v) => /^en([-_]|$)/i.test(v.lang));
  const pool = en.length ? en : voices;
  const label = (v) => `${v.name} ${v.voiceURI || ""}`;
  const rank = (v) => (v.localService ? 3 : 0) + (HUMAN_VOICE.test(label(v)) ? 5 : 0) - (HARSH_VOICE.test(label(v)) ? 8 : 0);
  return pool.slice().sort((a, b) => rank(b) - rank(a) || label(a).localeCompare(label(b)))[0] || null;
}

function browserVoice(text, finish) {
  if (!window.speechSynthesis) {
    finish();
    return null;
  }
  let started = false;
  const start = (force) => {
    const voices = speechSynthesis.getVoices();
    if (!voices.length && !force) return;
    if (started || voiceDone !== finish) return; // hushed, or the voice list arrived twice
    started = true;
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-US";
    u.rate = 0.9;
    const picked = pickSpokenVoice(voices);
    if (picked) u.voice = picked;
    u.onend = u.onerror = finish;
    speechSynthesis.speak(u);
  };
  speechSynthesis.addEventListener("voiceschanged", () => start(false), { once: true });
  speechSynthesis.getVoices();
  if (speechSynthesis.getVoices().length) start(false);
  else setTimeout(() => start(true), 300);
  return "browser";
}

// Says `text`: its pre-made file, else `url` (a server-made one), else the browser's voice. Resolves once
// it starts to "ai", "browser", or null (no voice); `done` runs once when it ends or is hushed.
function speak(text, url = null, done = () => {}) {
  hush();
  let over = false;
  const finish = () => {
    if (over) return;
    over = true;
    if (voiceDone === finish) voiceDone = null;
    done();
  };
  voiceDone = finish;
  const src = voiceFiles[text] ? `/static/audio/${voiceFiles[text]}` : url;
  if (!src) return Promise.resolve(browserVoice(text, finish));
  const el = new Audio(src);
  voiceNow = el;
  el.onended = () => {
    if (voiceNow === el) voiceNow = null;
    finish();
  };
  return el.play().then(() => "ai", () => { // no file, no network, or not allowed before a click
    if (voiceNow !== el) return null; // hushed meanwhile
    voiceNow = null;
    return browserVoice(text, finish);
  });
}

function cueVoice(text) {
  if (document.visibilityState === "visible") speak(text);
}

function listenSummary() {
  const b = $("listen-summary");
  if (b.dataset.on) {
    hush();
    return;
  }
  b.dataset.on = "1";
  b.textContent = "Getting the voice…";
  b.setAttribute("aria-busy", "true");
  const end = () => {
    delete b.dataset.on;
    b.removeAttribute("aria-busy");
    b.textContent = "Listen";
    $("family-voice").replaceChildren();
  };
  speak($("family-text").textContent, `/api/people/${encodeURIComponent(personId)}/summary/audio`, end).then((how) => {
    if (!b.dataset.on) return;
    b.removeAttribute("aria-busy");
    b.textContent = "Stop";
    $("family-voice").replaceChildren(how === "ai" ? h("span", "AI voice", { class: "tag tag-ai" }) : "");
  });
}

// ---- views: Home, Check-in, For the doctor (the URL hash; no reloads, the WebSocket stays open) -----
function show() {
  const v = VIEWS.includes(location.hash.slice(1)) ? location.hash.slice(1) : "home";
  if (v !== "checkin") ended = setup = false;
  for (const x of VIEWS) $(`view-${x}`).hidden = x !== v;
  for (const a of document.querySelectorAll(".views a")) {
    if (a.getAttribute("href") === `#${v}`) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  }
  if (v !== view) scrollTo(0, 0);
  view = v;
  renderCheckin(state);
  if (v === "doctor") for (const c of Object.values(charts)) c.resize(); // drawn while hidden
}

function go(v) {
  if (location.hash !== `#${v}`) history.pushState(null, "", `#${v}`);
  show();
}

// ---- live state ---------------------------------------------------------------------------------
// Only write when the text changes: rewriting a live region (or a role="alert") re-announces it.
function setText(el, text) {
  if (el.textContent !== text) el.textContent = text;
}

// Said once per change of stage; cleared first so the same words ("Done. Rest a moment.") are said again.
function announce(text) {
  $("announce").textContent = "";
  requestAnimationFrame(() => ($("announce").textContent = text));
}

function stepTitle(step, steps) {
  const [kind, n] = step.id.split("#");
  const of = steps.filter((x) => x.id.split("#")[0] === kind).length;
  if (kind === "sit_to_stand") return `Stand up and sit down: round ${n} of ${of}`;
  if (kind.startsWith("hold_")) return `Hold still at the counter: ${n} of ${of}`;
  return STEP_TITLE[kind] || step.label;
}

const stanceOf = (kind) => (/^(balance|hold)_/.test(kind) ? kind.replace(/^(balance|hold)_/, "") : null);

// One word (or three) while moving, big enough to read from the line or the counter.
function cueWord(kind) {
  if (kind === "tug") return "Walk";
  if (kind === "dual_tug") return "Walk and name animals";
  if (kind === "chair_stand" || kind === "sit_to_stand") return "Stand up, sit down";
  return "Hold still";
}

// The small control that replaces "I'm ready" once a step is moving: [label, hint], or null (chair stand).
function helperFor(kind, mode) {
  if (kind === "tug" || kind === "dual_tug") return ["Helper: tap when they're seated", "The belt usually stops the clock by itself."];
  if (kind === "chair_stand") return null;
  if (kind === "sit_to_stand") return ["End this round", ""];
  return mode === "checkin" ? ["Helper: tap if they step out of position", "The belt notices this by itself too."]
    : ["End this hold early", ""];
}

const leftOf = (live) => Math.max(0, Math.ceil((live.limit_s ?? live.target_s) - live.elapsed_s));

// No stopwatch while walking: a visible clock invites rushing the sit-down.
function liveLine(kind, live) {
  if (live.reps !== undefined) {
    const stands = live.target ? `${live.reps} of ${live.target} stands` : `${live.reps} ${live.reps === 1 ? "stand" : "stands"} so far`;
    return live.limit_s && live.elapsed_s !== undefined ? `${stands} · ${seconds(leftOf(live))} left` : stands;
  }
  if (live.target_s !== undefined && live.elapsed_s !== undefined) return `${seconds(leftOf(live))} left`;
  return kind === "tug" || kind === "dual_tug" ? "Take your time sitting down." : "";
}

// Instruction pictures in /static/img (local files). [file, alt describing the position].
// dual_tug reuses the walk; a balance hold uses the counter picture, not the stance close-up.
const PICTURES = {
  tug: ["tug.jpg", "Standing up from an arm chair and walking toward a line taped on the floor."],
  chair_stand: ["chair_stand.jpg", "Standing up from an armless chair with arms crossed on the chest."],
  feet_together: ["feet_together.jpg", "Both feet side by side, touching each other."],
  semi_tandem: ["semi_tandem.jpg",
    "One foot half a step ahead, its heel beside the other foot's big toe, both feet touching along the side."],
  tandem: ["tandem.jpg", "One foot directly in front of the other, the front foot's heel touching the back foot's toes."],
  sit_to_stand: ["sit_to_stand.jpg",
    "Halfway through standing up from a sturdy armless chair, hips just lifted off the seat, feet flat on the floor, leaning slightly forward, arms crossed on the chest."],
  hold: ["hold.jpg", "Standing with one hand resting on a kitchen counter for balance."],
};

function pictureFor(kind) {
  if (kind === "dual_tug") return "tug";
  if (kind.startsWith("hold_")) return "hold";
  if (kind.startsWith("balance_")) return kind.slice("balance_".length);
  return PICTURES[kind] ? kind : null;
}

// Foot positions, toes up. Shown while a stance is underway, when the instruction picture is hidden.
const FOOT = "M17 0C29 0 34 12 34 28L32 70C31 84 25 92 17 92C9 92 3 84 2 70L0 28C0 12 5 0 17 0Z";
const feet = (label, box, ...at) => `<svg viewBox="0 0 100 ${box}" role="img" aria-label="${label}">`
  + at.map(([x, y]) => `<path d="${FOOT}" transform="translate(${x} ${y})" fill="#fff"/>`).join("") + "</svg>";
const FEET = {
  feet_together: feet("Feet side by side", 172, [14, 40], [52, 40]),
  semi_tandem: feet("One foot about half a foot ahead, sides touching", 172, [16, 64], [50, 18]),
  tandem: feet("One foot right in front of the other, heel touching toe", 186, [33, 0], [33, 93]),
};

function personName(id) {
  const o = [...$("person").options].find((x) => x.value === id);
  return o ? o.text : "";
}

// Keyboard focus never drops to the page when the control it was on is hidden.
function keepFocus(primary) {
  const a = document.activeElement;
  if (view === "checkin" && (!a || a === document.body || a.offsetParent === null)) primary.focus();
}

function renderWarnings() {
  const w = [];
  if (online === false) {
    w.push(everOnline ? "Lost the connection to the laptop. Trying again…" : "Can't connect to the laptop yet. Trying again…");
  } else if (state) {
    if (!state.base_connected) w.push("The button box isn't connected. Check its cable to the laptop.");
    if (!(state.source.rate_hz > 0)) w.push("The belt isn't sending any movement. Check that it's switched on and charged.");
  }
  const text = w.join("\n");
  if (text === warningsText) return; // role="alert": rebuilding it would repeat the alert 4 times a second
  warningsText = text;
  $("warning").replaceChildren(...w.map((t) => h("p", t)));
  $("warning").hidden = !w.length;
}

// A step goes waiting (read, then "I'm ready") → go (1.5 s, whole screen) → moving (one big word, time
// left, a small helper control) → rest (2 s) → the next step waiting.
function renderCheckin(s) {
  const phase = s ? s.phase : "idle";
  const screen = phase === "running" ? "running" : ended ? "done" : setup ? "setup" : "idle";
  for (const x of ["idle", "setup", "running", "done"]) $(`ci-${x}`).hidden = screen !== x;
  $("station").dataset.phase = phase;
  if (screen !== "running") {
    $("station").classList.remove("go");
    lastRunning = stageKey = null;
    return;
  }
  const steps = s.steps;
  const live = s.live || {};
  const now = Date.now();
  const i = steps.findIndex((x) => x.status === "waiting" || x.status === "running");
  const step = i >= 0 ? steps[i] : null;
  const running = step && step.status === "running" ? step.id : null;
  if (lastRunning && lastRunning !== running) { // a step just finished
    restUntil = now + REST_S * 1000;
    setTimeout(() => renderCheckin(state), REST_S * 1000 + 20);
  }
  if (running && running !== goFor) {
    goFor = running;
    goUntil = (live.elapsed_s ?? 0) < 1 ? now + GO_S * 1000 : 0; // not when the page opens mid-step
    setTimeout(() => renderCheckin(state), GO_S * 1000 + 20);
  }
  lastRunning = running;
  const stage = !step ? (now < restUntil ? "rest" : "ready")
    : running ? (now < goUntil ? "go" : "moving") : now < restUntil ? "rest" : "waiting";
  const kind = step ? step.id.split("#")[0] : null;
  const stance = kind && stanceOf(kind);

  $("station").classList.toggle("go", stage === "go");
  $("led").className = `led ${s.led}`;
  const n = i >= 0 ? i + 1 : Math.min(steps.filter((x) => x.status !== "pending").length + 1, steps.length);
  setText($("step-count"), [personName(s.person_id), steps.length ? `Step ${n} of ${steps.length}` : "Getting ready"]
    .filter(Boolean).join(" · "));
  $("steps-tag").replaceChildren(s.source.simulated ? simTag() : "");
  const title = step && (stage === "waiting" || stage === "moving") ? stepTitle(step, steps) : "";
  setText($("step-title"), title);
  $("step-title").hidden = !title;
  const cue = { go: "Go", moving: kind && cueWord(kind), rest: "Done. Rest a moment.", ready: "Getting ready…" }[stage] || "";
  setText($("cue"), cue);
  $("cue").hidden = !cue;
  const showFeet = !!stance && stage === "moving" && !!FEET[stance];
  if (showFeet && $("feet").dataset.stance !== stance) {
    $("feet").innerHTML = FEET[stance]; // static markup from FEET above
    $("feet").dataset.stance = stance;
  }
  $("feet").hidden = !showFeet;
  const pic = stage === "waiting" ? PICTURES[pictureFor(kind)] : null;
  const img = $("step-img");
  if (pic) {
    const url = `/static/img/${pic[0]}`;
    if (!img.src.endsWith(url)) img.src = url; // assigning src resolves it; don't reload the same file
    if (img.alt !== pic[1]) img.alt = pic[1];
  }
  $("step-fig").hidden = !pic;
  setText($("prompt"), stage === "waiting" ? s.prompt : "");
  $("prompt").hidden = stage !== "waiting";
  setText($("live"), stage === "moving" ? liveLine(kind, live) : "");
  const total = live.limit_s ?? live.target_s;
  const meter = stage === "moving" && !!total && live.elapsed_s !== undefined;
  $("meter").hidden = !meter;
  if (meter) $("meter").firstElementChild.style.width = `${(100 * leftOf(live)) / total}%`;

  $("button").hidden = stage !== "waiting";
  const help = (stage === "go" || stage === "moving") && helperFor(kind, s.mode);
  $("helper").hidden = !help;
  $("helper-hint").hidden = !(help && help[1]);
  if (help) {
    setText($("helper"), help[0]);
    setText($("helper-hint"), help[1]);
    // The server ignores presses for GO_GUARD_S after "Go"; the control says so by looking inactive.
    $("helper").setAttribute("aria-disabled", String(stage === "go" || (live.elapsed_s ?? 0) < GO_GUARD_S));
  }
  const chair = step && step.id === "chair_stand" && step.status === "running";
  $("arms-used").hidden = !chair;
  $("arms-used").disabled = !chair;
  setText($("cancel"), s.mode === "exercise" ? "Stop the exercise" : "Stop the check-in");

  const key = `${step ? step.id : ""}:${stage}`;
  if (key === stageKey) return;
  const wasRest = stageKey?.endsWith(":rest"); // the rest keeps going when the next step starts waiting
  stageKey = key;
  if (stage === "waiting") {
    announce(`${title}. ${s.prompt}`);
    cueVoice(s.prompt);
  } else if (stage === "go" || stage === "moving") {
    if (stage === "go") announce(`Go: ${stepTitle(step, steps)}.`);
    hush(); // pressed mid-sentence: the step has started, so stop talking over it
  } else if (stage === "rest" && !wasRest) {
    announce("Done. Rest a moment.");
    cueVoice("Done. Rest a moment.");
  }
  keepFocus(stage === "waiting" ? $("button") : help ? $("helper") : $("cancel"));
}

function plainRow(list, name, text, tag = "h3", chip = null) {
  const el = h("div", null, { class: "row two" });
  const left = h("div", null, { class: "r-name" });
  left.append(h(tag, name));
  if (chip) left.append(h("span", "Flagged", { class: chip }));
  const right = h("div", null, { class: "r-value" });
  right.append(h("span", text, { class: "text" }));
  el.append(left, right);
  list.append(el);
}

const STANCE_ROWS = [["feet_together", "Feet together"], ["semi_tandem", "One foot a little ahead"],
  ["tandem", "One foot in front of the other"]];

// Thanks first, for the person who just did it; then the result in plain words for the family.
function renderDone(s) {
  const r = s.last_record;
  const list = h("div", null, { class: "rows" });
  $("done-list").replaceChildren();
  $("done-result").hidden = true;
  $("done-again").hidden = true;
  if (s.phase !== "done" || !r) {
    $("done-answer").textContent = s.prompt || "Stopped. Nothing was saved.";
    $("done-sub").textContent = "";
    $("done-again").hidden = false;
    return;
  }
  const secs = (v) => (v === null || v === undefined ? "Not measured" : seconds(Math.round(v * 10) / 10));
  if (s.mode === "checkin") {
    $("done-answer").textContent = "You finished. Thank you.";
    $("done-sub").textContent = "That's the whole check-in.";
    const a = answerFor(r, "this");
    $("done-level").className = `level-tile level-${a.level}`;
    $("done-level").textContent = a.word;
    $("done-result-text").textContent = a.text;
    const items = reasonsBelow(r);
    $("done-reasons").replaceChildren(...items.map((t) => h("li", t)));
    $("done-reasons").hidden = !items.length;
    $("done-advice").textContent = a.sub;
    $("done-result").hidden = false;
    const m = r.metrics;
    const steps = r.steps || {};
    const flagged = new Set(r.flags.map((f) => f.id));
    const chip = (id) => (flagged.has(id) ? (r.level === "red" ? "chip red" : "chip") : null);
    plainRow(list, "Stand up and walk", m.tug_timed_out ? "Didn't finish within 60 seconds" : secs(m.tug_s), "h3", chip("tug"));
    plainRow(list, "Walk again, naming animals", secs(m.dual_tug_s));
    if (steps.dual_tug?.animals) plainRow(list, "Animals named on that walk", animalsText(steps.dual_tug, true));
    plainRow(list, "Stand up from the chair", steps.chair_stand?.arms_used ? "Stopped: arms were needed"
      : m.chair_stands === null ? "Not measured" : `${m.chair_stands} times in 30 seconds`, "h3", chip("chair_stand"));
    // The balance flag belongs to the stance that ended the balance steps.
    const broke = STANCE_ROWS.map(([x]) => x).find((x) => steps[`balance_${x}`] && m[`${x}_s`] !== null && m[`${x}_s`] < 10);
    for (const [x, name] of STANCE_ROWS) {
      const text = !steps[`balance_${x}`] ? "Not tried: the check-in stops after a hard one"
        : m[`${x}_s`] === null ? "Not measured" : `Held ${secs(m[`${x}_s`])}`;
      plainRow(list, name, text, "h3", x === broke ? chip("balance") : null);
    }
  } else {
    $("done-answer").textContent = "Exercise done. Nice work.";
    $("done-sub").textContent = "It's saved, and counts towards this week.";
    const counted = r.sets.filter((x) => x.reps !== undefined);
    if (r.sets.length) {
      const total = counted.reduce((sum, x) => sum + x.reps, 0);
      plainRow(list, "Stood up and sat down",
        `${total} times${counted.length < r.sets.length ? " (some not measured)" : ""}`);
    }
    if (r.holds.length) {
      plainRow(list, "Held still at the counter", r.holds.map((x) => secs(x.hold_s)).join(", "));
    }
  }
  if (r.simulated) $("done-sub").append(" ", simTag());
  $("done-list").append(list);
}

function renderState(s) {
  const was = state && state.phase;
  state = s;
  $("edit-profile").hidden = $("add-person").hidden = !!s.demo; // the public demo has one ready-made Guest
  if (s.demo) $("ai-toggle").hidden = true;
  const running = s.phase === "running";
  document.body.dataset.running = running;
  let justEnded = false;
  if (running) {
    ended = setup = false;
    if (view !== "checkin") go("checkin"); // the Check-in view takes over while a session runs
  } else if (was === "running") {
    ended = justEnded = true; // the result stays until someone leaves the Check-in view
    renderDone(s);
    if (view !== "checkin") go("checkin");
  }
  renderWarnings();
  renderCheckin(s);
  if (justEnded) {
    $("done-answer").focus();
    cueVoice($("done-answer").textContent);
  }
  for (const id of ["start-checkin", "start-exercise", "start-checkin-2", "start-plan", "start-quick", "setup-go"]) {
    $(id).disabled = running;
  }
}

function connect() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onopen = () => {
    const reconnected = online === false;
    online = true;
    everOnline = true;
    renderWarnings();
    if (reconnected) run(loadPeople); // the laptop may have restarted, or the first load failed
    run(loadAi);
  };
  ws.onmessage = (e) => {
    const ev = JSON.parse(e.data);
    if (ev.type === "state") {
      renderState(ev);
      renderAnimals(ev);
    } else if (ev.type === "ai") {
      renderAi(ev);
    } else if (ev.type === "cue") {
      play(ev.name);
      animalsCue(ev.name);
    }
    else if (ev.type === "saved" && ev.person_id === personId) loadDashboard();
  };
  ws.onclose = () => {
    online = false;
    renderWarnings();
    setTimeout(connect, 1000);
  };
}

// ---- animals named on the second walk (animals.py): recorded from "Go" to its stop, then counted once --
// Only the page that started the check-in and opted in records. Browsers allow the microphone only on
// localhost or HTTPS, so the tablet at http://LAPTOP-IP:8000 can't; the simulator can use a sample clip.
const SAMPLE_CLIP = "/static/sample/animals-walk.mp3";
const micOk = () => !!(window.isSecureContext && navigator.mediaDevices && window.MediaRecorder);
let animalsMode = null; // "mic" or "sample" for the check-in this page started; null: not counted
let recording = null; // a promise of stop(), which resolves to the audio Blob or "sample"
let animalsRun = false; // a session was seen running since animalsMode was chosen

function animalsText(step, list = false) {
  const a = step && step.animals;
  if (!a || a.status === "not_counted") return "Animals: not counted";
  if (a.status === "counting") return "Animals: counting…";
  const rep = a.repeats ? ` (${a.repeats} repeat${a.repeats === 1 ? "" : "s"})` : "";
  const names = list && a.list.length ? `: ${a.list.join(", ")}` : "";
  return `Named ${a.named} animal${a.named === 1 ? "" : "s"}${rep}${names}${a.simulated ? " · Simulated sample" : ""}`;
}

function animalsOffered() {
  // aiStatus is the live switch; state.stt is the same fact on the session stream (set at startup and on each toggle).
  if (aiStatus) return !!aiStatus.on;
  return !!(state && state.stt);
}

function renderAnimalsOptin() {
  const on = animalsOffered() && !!state;
  $("animals-optin").hidden = !on;
  if (!on) return;
  const sim = state.source.simulated;
  $("animals-sample-row").hidden = !sim;
  $("animals-nomic").hidden = !$("animals-on").checked || (sim && $("animals-sample").checked) || micOk();
}

// Called from the "We're ready" click, so the permission prompt comes before the walk, not during it.
async function chooseAnimals() {
  animalsMode = null;
  animalsRun = false;
  if (!animalsOffered() || !$("animals-on").checked) return;
  if (state.source.simulated && $("animals-sample").checked) {
    animalsMode = "sample";
  } else if (micOk()) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      for (const t of stream.getTracks()) t.stop(); // recording starts on the walk's "Go"
      animalsMode = "mic";
    } catch {
      // permission denied: the walk still counts, the animals don't
    }
  }
}

async function startRecording() {
  hush(); // never record the page's own voice
  if (animalsMode === "sample") {
    const clip = new Audio(SAMPLE_CLIP); // the room hears what's sent
    clip.play().catch(() => {});
    return async () => (clip.pause(), "sample");
  }
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const type = ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4"].find((t) => MediaRecorder.isTypeSupported(t));
  const rec = new MediaRecorder(stream, type ? { mimeType: type } : {});
  const parts = [];
  rec.ondataavailable = (e) => e.data.size && parts.push(e.data);
  rec.start();
  return () => new Promise((resolve) => {
    rec.onstop = () => {
      for (const t of stream.getTracks()) t.stop();
      resolve(new Blob(parts, { type: rec.mimeType || "audio/webm" }));
    };
    rec.stop();
  });
}

function stopRecording(send) {
  const r = recording;
  recording = null;
  if (!r) return;
  r.then(async (stop) => {
    const body = await stop();
    if (!send) return;
    // The count arrives on the state stream; a failed upload just leaves "Animals: not counted".
    await fetch(body === "sample" ? "/api/audio/dual_tug?sample=true" : "/api/audio/dual_tug",
      body === "sample" ? { method: "POST" } : { method: "POST", headers: { "Content-Type": body.type }, body });
  }).catch(() => {});
}

function animalsCue(name) {
  if (!animalsMode || !state || state.step !== "dual_tug") return;
  if (name === "start") {
    recording = startRecording();
    recording.catch(() => (recording = null));
  } else if (name === "stop" || name === "error") {
    stopRecording(true);
  }
}

function renderAnimals(s) {
  renderAnimalsOptin();
  // Only a session ending clears the choice: an idle state can still arrive between "We're ready" and the start.
  if (s.phase === "running") animalsRun = true;
  else if (animalsRun) {
    animalsRun = false;
    stopRecording(false); // cancelled or failed mid-walk: nothing is sent
    animalsMode = null;
  }
  const walk = (s.steps || []).find((x) => x.id === "dual_tug");
  const waiting = (s.steps || []).some((x) => x.status === "waiting");
  let text = "";
  if (recording && s.step === "dual_tug") text = animalsMode === "sample" ? "Playing the sample recording (Simulated)" : "Recording for the animal count";
  else if (s.phase === "running" && waiting && walk && walk.result && walk.result.animals) text = animalsText(walk.result, true);
  setText($("animals-live"), text);
  $("animals-live").hidden = !text;
}

// ---- dashboard ----------------------------------------------------------------------------------
async function loadPeople() {
  const people = await api("GET", "/api/people");
  const sel = $("person");
  sel.replaceChildren(...people.map((p) => new Option(p.name, p.id)));
  if (!people.some((p) => p.id === personId)) {
    const last = recallPerson();
    personId = people.some((p) => p.id === last) ? last : (people.find((p) => !p.simulated) || people[0] || {}).id;
  }
  sel.value = personId;
  await loadDashboard();
}

async function loadDashboard() {
  if (!personId) return;
  const d = await api("GET", `/api/people/${encodeURIComponent(personId)}/dashboard`);
  renderProfile(d.person);
  renderHome(d);
  renderDoctor(d);
  clearSummary(); // made on request for the data shown then; a reload (new person, new save) makes it stale
  clearAsk();
}

function renderProfile(person) {
  lastPerson = person;
  // "Simulated: Dad" already says it; other simulated people get the tag.
  $("person-tag").replaceChildren(person.simulated && !/^simulated/i.test(person.name) ? simTag() : "");
  profileReady = !!(person.profile.age && person.profile.sex);
  for (const id of ["start-checkin", "start-checkin-2"]) $(id).textContent = profileReady ? "Start check-in" : "Add age and sex to start";
  if (!newPerson) fillProfile(person);
}

function fillProfile(person) {
  const f = $("profile");
  f.name.value = person.name;
  f.age.value = person.profile.age ?? "";
  f.sex.value = person.profile.sex ?? "";
  for (const k of ["fallen", "unsteady", "worried"]) f[k].checked = !!person.profile[k];
}

// ---- Home: plain words only ---------------------------------------------------------------------
// Every reason behind an amber or red level, in the cards' words (summary.family_items says the same).
function reasons(r) {
  const m = r.metrics;
  const c = r.cutoffs;
  const out = [];
  for (const f of r.flags) {
    if (f.id === "key_questions") {
      for (const [k, yes] of Object.entries(r.key_questions)) if (yes) out.push(`${cap(ANSWERED_YES[k])}.`);
    } else if (f.id === "tug") {
      const took = m.tug_timed_out ? "wasn't finished within 60 seconds" : `took ${seconds(m.tug_s)}`;
      out.push(`Standing up and walking ${took}; ${c.tug_s} seconds or longer is flagged.`);
    } else if (f.id === "chair_stand") {
      out.push(`Leg strength: ${m.chair_stands} stand-ups from a chair in 30 seconds, fewer than average for ${chairGroup(c)}.`);
    } else if (f.id === "balance") {
      // The stance that broke; after it the check-in stops, so a later 0 s means "not tried".
      const broke = Object.keys(STANCE_WORDS).find((x) => m[`${x}_s`] !== null && m[`${x}_s`] < 10) || "tandem";
      const held = `Balance: held ${STANCE_WORDS[broke]} for ${seconds(m[`${broke}_s`])}`;
      out.push(broke === "tandem" ? `${held}; under ${c.tandem_s} seconds is flagged.`
        : `${held} (the goal is 10), so the hardest position wasn't tried.`);
    }
  }
  for (const d of r.declines || []) out.push(`${cap(TRACKED_WORDS[d.id] || d.id)} has been worse than usual two check-ins in a row.`);
  return out;
}

// The reasons to list under a headline: none when the headline already names the only one (a single decline).
function reasonsBelow(r) {
  if (!r || !r.alert) return [];
  const items = reasons(r);
  return !r.flags.length && items.length === 1 ? [] : items;
}

// steadi.make_plan gives 3 sets or 4 holds (instead of 2) when an area has been weak.
function planExtras(plan) {
  return [plan.sit_to_stand.sets > 2 && "extra stand-ups for leg strength",
    plan.balance.holds > 2 && "extra balance holds"].filter(Boolean);
}

// which: "the last" on Home, "this" on the Check-in result.
function answerFor(r, which = "the last") {
  const The = cap(which);
  if (!r) {
    return { level: "none", word: "None yet", text: "No check-in yet.",
      sub: profileReady ? "The check-in takes about 3 minutes. Press Start check-in when you're ready."
        : "First add age and sex. Then the check-in takes about 3 minutes." };
  }
  if (r.alert) {
    // The reasons are listed under this line. A decline is our change-from-usual rule, not a screening
    // flag, so a check-in with only declines says what changed instead of "flags increased fall risk".
    const declines = r.declines || [];
    const text = r.flags.length ? `${The} check-in flags increased fall risk.`
      : declines.length === 1 ? `${cap(TRACKED_WORDS[declines[0].id] || declines[0].id)} has been worse than usual two check-ins in a row.`
        : "Some results have been worse than usual two check-ins in a row.";
    return { level: r.level, word: LEVEL_MEANING[r.level], text, sub: r.alert.advice };
  }
  const missing = unmeasured(r.metrics).length;
  if (missing === CORE.length) {
    return { level: "none", word: "Not measured", text: `${The} check-in couldn't be measured.`,
      sub: "Check that the belt is on and switched on, then do the check-in again." };
  }
  if (missing) {
    return { level: "none", word: "Partly measured", text: `Nothing flagged, but some tests in ${which} check-in weren't measured.`,
      sub: "Do the check-in again to measure every test." };
  }
  return { level: "green", word: LEVEL_MEANING.green, text: `Nothing flagged in ${which} check-in.`,
    sub: "Keep up the exercises most days." };
}

function trendLine(latest, key, unit) {
  const p = h("p", null, { class: "trend" });
  const c = latest.changes && latest.changes[key];
  if (!c) {
    p.textContent = "Not enough check-ins yet to compare with usual.";
    return p;
  }
  const u = USUAL[key];
  const better = -c.change * u.dir >= u.limit(c.baseline);
  p.append(h("b", c.worse ? "Worse than usual" : better ? "Better than usual" : "About the same as usual"));
  if (unit) {
    const usual = unit === "times" ? Math.round(c.baseline) : Math.round(c.baseline * 10) / 10;
    p.append(` (usually about ${usual} ${unit})`);
  }
  return p;
}

function card(title, value, unit, what, verdict, trend) {
  const el = h("article", null, { class: "card" });
  const v = h("p", null, { class: `verdict ${verdict.cls}` });
  const words = h("span");
  words.append(h("b", verdict.word), verdict.text ? ` ${verdict.text}` : "");
  v.append(h("span", null, { class: "mark", "aria-hidden": "true" }), words);
  el.append(h("h3", title, { class: "sub" }), big(value, unit), h("p", what, { class: "what" }), v, trend);
  return el;
}

function renderCards(latest) {
  const box = $("cards");
  box.replaceChildren();
  $("cards-tag").replaceChildren(latest && latest.simulated ? simTag() : "");
  if (!latest) {
    box.append(h("p", "Nothing here yet. After the first check-in you'll see how standing up and walking, "
      + "leg strength and balance went.", { class: "empty" }));
    return;
  }
  const m = latest.metrics;
  const c = latest.cutoffs;
  const flagged = new Set(latest.flags.map((f) => f.id));
  const declined = new Set((latest.declines || []).map((d) => d.id));
  const flagCls = latest.level === "red" ? "flag red" : "flag"; // the chip takes the check-in's level colour
  const verdict = (value, flag, key, bad, good) => {
    if (value === null || value === undefined) return { cls: "unknown", word: "Not measured.", text: "" };
    if (flag) return { cls: flagCls, word: "Flagged", text: bad };
    if (declined.has(key)) return { cls: flagCls, word: "Getting worse", text: "Two check-ins in a row." };
    return { cls: "ok", word: "Nothing flagged.", text: good };
  };
  const group = chairGroup(c);
  const tugValue = m.tug_timed_out ? "60+" : m.tug_s; // not finished within 60 s: flagged, not "not measured"
  const chair = !c.chair_stands
    ? { cls: "unknown", word: "Can't compare yet.", text: "Add age and sex in Edit profile to compare with others the same age." }
    : verdict(m.chair_stands, flagged.has("chair_stand"), "chair_stands", `Fewer than average for ${group}.`,
      `Average or better for ${group}.`);
  const stances = [m.feet_together_s, m.semi_tandem_s, m.tandem_s];
  const held = stances.every((v) => v === null) ? null : `${stances.filter((v) => v !== null && v >= 10).length} of 3`;
  box.append(
    card("Standing up and walking", tugValue, "seconds", "Time to stand up, walk to the line and back, and sit down.",
      verdict(tugValue, flagged.has("tug"), "tug_s", `${c.tug_s} seconds or longer is flagged.`, `Under ${c.tug_s} seconds.`),
      trendLine(latest, "tug_s", "seconds")),
    card("Leg strength", m.chair_stands, "times", "Times stood up from a chair in 30 seconds, arms crossed.", chair,
      trendLine(latest, "chair_stands", "times")),
    card("Balance", held, "positions held",
      "Positions held for 10 seconds, standing still, each harder than the last.",
      verdict(m.tandem_s, flagged.has("balance"), "tandem_s",
        `Under ${c.tandem_s} seconds in the hardest position is flagged.`, "Held the hardest position for 10 seconds."),
      trendLine(latest, "tandem_s", "seconds in the hardest position")),
  );
}

function renderHome(d) {
  const latest = d.latest;
  const a = answerFor(latest);
  const tile = $("answer-level");
  tile.className = `level-tile level-${a.level}`;
  tile.textContent = a.word;
  $("answer").textContent = a.text;
  if (!revealed) {
    $("answer-wrap").classList.add("play"); // the one entrance on the page, on first load only
    revealed = true;
  }
  $("answer-sub").textContent = a.sub;
  const flagged = !!(latest && latest.alert);
  const list = $("answer-list");
  list.replaceChildren(...reasonsBelow(latest).map((t) => h("li", t)));
  list.hidden = !list.children.length;
  // After a flag, the calm part: what the plan is doing about it, and what this screening is.
  const extras = flagged ? planExtras(d.plan) : [];
  $("answer-plan").textContent = extras.length ? `The exercise plan now has ${extras.join(" and ")}.` : "";
  $("answer-plan").hidden = !extras.length;
  $("answer-note").hidden = !flagged;
  hasCheckin = !!latest;
  renderAsk();
  for (const id of ["make-summary", "make-summary-doctor"]) $(id).disabled = !latest;
  $("family-make-text").textContent = latest
    ? "A short summary of how things are going, in plain words. It can take a few seconds to write."
    : "A summary can be made after the first check-in.";
  const whenEl = $("answer-when");
  whenEl.replaceChildren();
  if (latest) {
    whenEl.append(h("span", `From the check-in on ${when(latest.date.slice(0, 10), true)}.`));
    if (latest.simulated) whenEl.append(simTag());
  }
  renderCards(latest);
  renderHomeExercise(d.plan, d.adherence);
}

function renderHomeExercise(plan, adherence) {
  const sts = plan.sit_to_stand;
  const bal = plan.balance;
  const days = h("div", null, { class: "ex-days" });
  const n = adherence.last_7_days;
  const goal = adherence.target_days_per_week;
  if (n) {
    days.append(h("span", String(n), { class: "num" }),
      h("p", `${n === 1 ? "day" : "days"} with exercise in the past 7 days. The goal is ${goal}.`));
  } else {
    days.append(h("p", `No exercise in the past 7 days yet. The goal is ${goal} days a week.`)); // no big zero
  }
  const rows = h("div", null, { class: "rows" });
  if (sts.sets) plainRow(rows, "Stand up from a chair and sit back down", `${sts.sets} rounds of ${sts.reps}`, "h4");
  if (bal.holds) {
    plainRow(rows, `Stand still, holding on to the counter, ${STANCE_WORDS[bal.stance]}`,
      `${bal.holds} times, ${bal.target_s} seconds each`, "h4");
  }
  const today = h("div", null, { class: "today" });
  today.append(h("h3", "Today's exercises", { class: "sub" }), rows);
  const extras = planExtras(plan);
  if (extras.length) today.append(h("p", `The plan has ${extras.join(" and ")}, based on the last check-ins.`, { class: "plan-why" }));
  $("home-exercise").replaceChildren(days, today);
  $("home-ex-tag").replaceChildren(adherence.weeks.some((w) => w.simulated) ? simTag() : "");
  $("plan-words").textContent = [
    sts.sets ? `${sts.sets} rounds of ${sts.reps} stand-ups from a chair` : "",
    bal.holds ? `${bal.holds} holds of ${bal.target_s} seconds at the counter, ${STANCE_WORDS[bal.stance]}` : "",
  ].filter(Boolean).join(", then ") + ".";
}

// ---- For the doctor: every clinical number ----------------------------------------------------------
const FLAG_SHORT = { key_questions: "key questions", tug: "TUG", chair_stand: "chair stand", balance: "balance" };
const METRIC_SHORT = { tug_s: "TUG", chair_stands: "chair stands", tandem_s: "tandem", dual_task_cost_pct: "dual-task cost" };
const CORE_NAME = { tug_s: "Timed Up and Go", chair_stands: "chair stand", tandem_s: "balance" };
const UNIT = { tug_s: "s", dual_task_cost_pct: "%", chair_stands: "", tandem_s: "s" }; // steadi.TRACKED
const STANCE_NAME = { feet_together: "feet together", semi_tandem: "semi-tandem", tandem: "tandem" };
const STANCE_TICKS = ["None", "Feet together", "Semi-tandem", "Tandem"]; // trends.stances_held: 0–3
const FLAG_SHADE = "rgba(180, 35, 24, 0.1)"; // the side of a STEADI cutoff that flags

// One number format for screen and print (steadi.fmt): 12.4 s, 18.4%, 13; a change in a percentage is in points.
function fmt(v, unit, change = false) {
  const u = change && unit === "%" ? " points" : unit && unit !== "%" ? ` ${unit}` : unit;
  return `${change && v > 0 ? "+" : ""}${Math.round(v * 10) / 10}${u}`;
}

// steadi.unmeasured: core tests with no value. A walk that timed out is flagged instead, so it isn't listed.
const unmeasured = (m) => CORE.filter((k) => (m[k] === null || m[k] === undefined) && !(k === "tug_s" && m.tug_timed_out));

function renderDoctor(d) {
  const p = d.person;
  const latest = d.latest;
  const dates = d.trends.dates;
  $("doc-name").textContent = p.name;
  const facts = $("doc-facts");
  facts.replaceChildren(h("span", `Age ${p.profile.age ?? "not given"}`), h("span", p.profile.sex ?? "sex not given"));
  if (latest) {
    facts.append(h("span", `Latest check-in ${when(latest.date.slice(0, 10), true)}`),
      h("span", `${dates.length} check-in${dates.length === 1 ? "" : "s"} since ${when(dates[0], true)}`));
  }
  if (p.simulated && !/^simulated/i.test(p.name)) facts.append(simTag()); // "Simulated: Dad" already says it
  renderAlert(latest);
  renderResults(latest, d.trends);
  renderTrends(d.trends);
  renderExercise(d.plan, d.adherence, d.exercise);
}

// Written for the clinician: what flagged, what changed, what wasn't measured. No family advice here.
function renderAlert(latest) {
  const box = $("alert");
  box.replaceChildren();
  if (!latest) return;
  const missing = unmeasured(latest.metrics);
  const declines = latest.declines || [];
  const partly = latest.level === "green" && missing.length > 0;
  const head = h("p", null, { class: "alert-head" });
  head.append(
    h("span", partly ? "Partly measured" : LEVEL_NAME[latest.level], { class: `level-tile level-${partly ? "none" : latest.level}` }),
    h("span", latest.flags.length ? "Flags increased fall risk"
      : declines.length ? "Change from baseline (not a STEADI flag)"
        : partly ? "No STEADI flags among the tests measured" : "No STEADI flags in the latest check-in"),
    h("span", "Level is our summary, not STEADI's.", { class: "meta" }));
  box.append(head);
  const items = [...latest.flags.map((f) => f.text), ...declines.map((x) => x.text)];
  if (missing.length) items.push(`Not measured: ${missing.map((k) => CORE_NAME[k]).join(", ")}.`);
  if (!items.length) return;
  const ul = h("ul", null, { class: "alert-items" });
  for (const t of items) ul.append(h("li", t));
  box.append(ul);
}

// How a step ended: timed by the belt or by the helper, or why there's no value.
function howNote(step, extra = "") {
  const notes = [];
  if (step && step.error) notes.push("Not measured: the sensor data dropped out");
  else if (step && step.method === "timeout") notes.push("Not finished within 60 s");
  else if (step && step.method === "button") notes.push(step.broke ? "Ended by the helper's button" : "Timed by the helper's button");
  else if (step && step.method) notes.push("Timed by the belt");
  if (extra) notes.push(extra);
  return notes.join(". ");
}

function changeCell(latest, key) {
  const c = latest.changes && latest.changes[key];
  if (!c) {
    const v = latest.metrics[key];
    return h("td", v === null || v === undefined ? "" : "Not enough history yet", { class: "soft", "data-label": "Change from baseline" });
  }
  const td = h("td", null, { "data-label": "Change from baseline" });
  td.append(h("b", fmt(c.change, UNIT[key], true)), ` (baseline ${fmt(c.baseline, UNIT[key])})`);
  if (c.worse) td.append(" ", h("span", "Worse", { class: "tag tag-worse" }));
  return td;
}

// A tiny trend line for a table row; decorative (the charts and the data table carry the numbers).
function spark(values) {
  const pts = values.map((v, i) => [i, v]).filter(([, v]) => v !== null && v !== undefined);
  if (pts.length < 2) return "";
  const lo = Math.min(...pts.map(([, v]) => v));
  const span = Math.max(...pts.map(([, v]) => v)) - lo || 1;
  const n = values.length - 1 || 1;
  const xy = pts.map(([i, v]) => `${((i / n) * 92 + 2).toFixed(1)},${(26 - ((v - lo) / span) * 24).toFixed(1)}`).join(" ");
  return `<svg viewBox="0 0 96 28" aria-hidden="true"><polyline points="${xy}" fill="none" stroke="${COLOR.ink}" stroke-width="2"/></svg>`;
}

function renderResults(latest, t) {
  const box = $("results");
  const meta = $("results-meta");
  box.replaceChildren();
  meta.replaceChildren();
  if (!latest) {
    box.append(h("p", "No check-in yet.", { class: "empty" }));
    return;
  }
  const m = latest.metrics;
  const c = latest.cutoffs;
  const steps = latest.steps || {};
  const flagged = new Set(latest.flags.map((f) => f.id));
  meta.append(h("span", when(latest.date)));
  if (latest.simulated) meta.append(simTag());
  const yes = Object.entries(latest.key_questions).filter(([, v]) => v).map(([k]) => ANSWERED_YES[k]);
  // Stances after the first one not held for 10 s aren't tried (STEADI); older records have no steps.
  const tried = (x) => !Object.keys(steps).length || !!steps[`balance_${x}`];
  const stance = (x) => ({
    v: m[`${x}_s`], unit: "s", text: tried(x) ? null : "Not tried",
    note: tried(x) ? howNote(steps[`balance_${x}`], m[`${x}_sway`] == null ? "" : `Sway ${m[`${x}_sway`]} m/s²`)
      : "Not tried: the check-in stops at the first stance not held for 10 s",
  });
  const chairStep = steps.chair_stand || {};
  const rows = [
    { name: "Key questions", flag: "key_questions", text: yes.length ? "Yes" : "No to all three",
      rule: "STEADI flags any yes", note: yes.length ? cap(yes.join("; ")) : "" },
    { name: "Timed Up and Go", flag: "tug", key: "tug_s", v: m.tug_s, unit: "s", text: m.tug_timed_out ? "Did not finish" : null,
      rule: `STEADI flags ${c.tug_s} s or more`, note: howNote(steps.tug), spark: t.series.tug_s },
    { name: "TUG naming animals", v: m.dual_tug_s, unit: "s", rule: "Ours, not STEADI: tracked vs. baseline",
      note: howNote(steps.dual_tug, steps.dual_tug?.animals ? animalsText(steps.dual_tug) : "") },
    { name: "Dual-task cost", key: "dual_task_cost_pct", v: m.dual_task_cost_pct, unit: "%",
      rule: "Ours, not STEADI: tracked vs. baseline", spark: t.series.dual_task_cost_pct },
    { name: "30-second chair stand", flag: "chair_stand", key: "chair_stands", v: m.chair_stands, unit: "stands",
      rule: c.chair_stands ? `STEADI flags under ${c.chair_stands} (${chairGroup(c)})` : "Needs age and sex for the STEADI line",
      note: chairStep.arms_used ? "Stopped: needed their arms (STEADI records 0)" : howNote(chairStep.error ? chairStep : null),
      spark: t.series.chair_stands },
    { name: "Balance: feet together", ...stance("feet_together"), rule: "Held 10 s to go on" },
    { name: "Balance: semi-tandem", ...stance("semi_tandem"), rule: "Held 10 s to go on" },
    { name: "Balance: tandem", flag: "balance", key: "tandem_s", ...stance("tandem"), rule: `STEADI flags under ${c.tandem_s} s`,
      spark: t.stances_held },
  ];
  const tagCls = latest.level === "red" ? "tag tag-flag" : "tag tag-flag amber"; // flags take the level colour
  const table = h("table", null, { class: "results" });
  const thead = h("thead");
  const hr = h("tr");
  for (const [text, cls] of [["Test"], ["Result", "res"], ["STEADI rule"], ["Change from baseline"], ["Notes"], ["Trend"]]) {
    hr.append(h("th", text, cls ? { scope: "col", class: cls } : { scope: "col" }));
  }
  thead.append(hr);
  const tbody = h("tbody");
  for (const r of rows) {
    const tr = h("tr");
    const name = h("th", r.name, { scope: "row", class: "test" });
    if (r.flag && flagged.has(r.flag)) name.append(h("span", "Flag", { class: tagCls }));
    const val = h("td", null, { class: "res", "data-label": "Result" });
    if (r.text) val.append(r.text);
    else if (r.v === null || r.v === undefined) val.append(h("span", "Not measured", { class: "soft" }));
    else val.append(String(Math.round(r.v * 10) / 10), h("span", r.unit, { class: "u" }));
    const sp = h("td", null, { class: "spark" });
    if (r.spark) sp.innerHTML = spark(r.spark); // numbers only
    tr.append(name, val, h("td", r.rule, { "data-label": "STEADI rule" }),
      r.key ? changeCell(latest, r.key) : h("td"),
      h("td", r.note || "", r.note ? { class: "soft", "data-label": "Notes" } : {}), sp);
    tbody.append(tr);
  }
  table.append(thead, tbody);
  box.append(table);
}

// ---- charts -------------------------------------------------------------------------------------
Chart.defaults.font.family = "Archivo, system-ui, sans-serif";
Chart.defaults.font.size = 16;
Chart.defaults.color = COLOR.muted;
Chart.defaults.borderColor = COLOR.line;
Chart.defaults.maintainAspectRatio = false;
Chart.defaults.animation = false;
Object.assign(Chart.defaults.plugins.legend, { align: "start", onClick: () => {} }); // a key, not pointer-only toggles
Object.assign(Chart.defaults.plugins.legend.labels, { usePointStyle: true, pointStyle: "line", pointStyleWidth: 32, padding: 18 });
Object.assign(Chart.defaults.plugins.tooltip, {
  backgroundColor: COLOR.ink, padding: 12, cornerRadius: 2, displayColors: false,
  titleFont: { weight: "700", size: 16 }, bodyFont: { size: 16 },
});

function axes(color, grid) {
  return {
    x: { grid: { display: false }, border: { color: grid }, ticks: { color, maxRotation: 0, autoSkipPadding: 16 } },
    y: { grid: { color: grid }, border: { display: false }, ticks: { color, padding: 8 } },
  };
}

// The chart in one sentence, for screen readers (role="img").
function chartLabel(title, dates, values, unit, rule) {
  const pts = values.map((v, i) => [v, dates[i]]).filter(([v]) => v !== null && v !== undefined);
  if (!pts.length) return `${title}: not measured yet.`;
  const f = (v) => fmt(v, unit);
  const vs = pts.map(([v]) => v);
  return `${title}, ${pts.length} check-ins from ${when(pts[0][1])} to ${when(pts.at(-1)[1])}: first ${f(pts[0][0])}, `
    + `latest ${f(pts.at(-1)[0])}, lowest ${f(Math.min(...vs))}, highest ${f(Math.max(...vs))}. ${rule}`;
}

// A measured series, its rolling baseline, and the STEADI cutoff with the flagged side shaded. Gaps stay gaps.
function lineChart(id, o) {
  charts[id]?.destroy();
  const datasets = [{
    label: o.label, data: o.values, spanGaps: false, borderColor: COLOR.ink, backgroundColor: COLOR.ink, borderWidth: 3,
    pointRadius: 5, pointHoverRadius: 7, pointHitRadius: 12, pointBackgroundColor: "#fff", pointBorderColor: COLOR.ink, pointBorderWidth: 2.5,
  }, {
    label: "Baseline", data: o.baseline, spanGaps: false, borderColor: COLOR.muted, backgroundColor: COLOR.muted,
    borderDash: [3, 5], borderWidth: 2, pointRadius: 0, pointHitRadius: 0,
  }];
  if (o.cutoff !== null && o.cutoff !== undefined) {
    datasets.push({ label: o.cutoffLabel, data: o.labels.map(() => o.cutoff), borderColor: COLOR.blue, backgroundColor: FLAG_SHADE,
      fill: o.flagAbove ? "end" : "start", borderDash: [8, 6], borderWidth: 2, pointRadius: 0, pointHitRadius: 0 });
  }
  const scales = axes(COLOR.muted, COLOR.line);
  Object.assign(scales.y, { beginAtZero: !!o.fromZero, suggestedMax: o.suggestedMax, ticks: { ...scales.y.ticks, precision: 0 } });
  charts[id] = new Chart($(id), { type: "line", data: { labels: o.labels, datasets }, options: { scales } });
  $(id).setAttribute("aria-label", o.aria);
}

// Balance as a ladder: the hardest stance held for 10 s. Tandem seconds stop at the cutoff, so they'd sit on it.
function stanceChart(labels, t, sim) {
  charts.stances?.destroy();
  const v = t.stances_held;
  const scales = axes(COLOR.muted, COLOR.line);
  Object.assign(scales.y, { min: 0, max: 3, ticks: { ...scales.y.ticks, stepSize: 1, callback: (n) => STANCE_TICKS[n] ?? "" } });
  charts.stances = new Chart($("chart-stances"), {
    type: "bar",
    data: { labels, datasets: [{ label: `Hardest stance held 10 s${sim}; red: below tandem, flags`, data: v,
      backgroundColor: v.map((n) => (n === 3 ? COLOR.ink : COLOR.red)), borderRadius: 2, maxBarThickness: 40, minBarLength: 6 }] },
    options: { scales, plugins: { legend: { labels: { usePointStyle: false } } } },
  });
  $("chart-stances").setAttribute("aria-label", "Balance, hardest stance held for 10 seconds at each check-in: "
    + t.dates.map((d, i) => `${when(d)} ${v[i] === null ? "not measured" : STANCE_TICKS[v[i]].toLowerCase()}`).join(", ")
    + ". STEADI flags when the tandem stance isn't held for 10 seconds.");
}

// One cell per check-in, by level: answers "since when".
function renderLevels(t, allSim) {
  $("levels").replaceChildren(...t.dates.map((d, i) => {
    const partial = t.levels[i] === "green" && t.partial[i];
    const li = h("li", null, { class: `lv lv-${partial ? "none" : t.levels[i]}` });
    const why = [...t.flags[i].map((id) => FLAG_SHORT[id] || id), ...t.declines[i].map((id) => `${METRIC_SHORT[id] || id} declining`)];
    li.append(h("span", null, { class: "lv-sw", "aria-hidden": "true" }), h("span", when(d), { class: "lv-date" }),
      h("span", partial ? "Partly measured" : LEVEL_NAME[t.levels[i]], { class: "lv-word" }));
    if (why.length) li.append(h("span", why.join(", "), { class: "lv-why" }));
    if (t.simulated[i] && !allSim) li.append(simTag());
    return li;
  }));
}

function renderTrendTable(t) {
  const num = (v) => (v === null || v === undefined ? "not measured" : String(Math.round(v * 10) / 10));
  const table = h("table");
  const thead = h("thead");
  const hr = h("tr");
  for (const c of ["Date", "Level", "TUG (s)", "Chair stands", "Hardest stance held 10 s", "Dual-task cost (%)"]) {
    hr.append(h("th", c, { scope: "col" }));
  }
  thead.append(hr);
  const tbody = h("tbody");
  t.dates.forEach((d, i) => {
    const tr = h("tr");
    tr.append(h("th", `${when(d)}${t.simulated[i] ? " (simulated)" : ""}`, { scope: "row" }),
      h("td", t.levels[i] === "green" && t.partial[i] ? "Partly measured" : LEVEL_NAME[t.levels[i]]),
      h("td", num(t.series.tug_s[i])), h("td", num(t.series.chair_stands[i])),
      h("td", t.stances_held[i] === null ? "not measured" : STANCE_TICKS[t.stances_held[i]]),
      h("td", num(t.series.dual_task_cost_pct[i])));
    tbody.append(tr);
  });
  table.append(thead, tbody);
  $("trend-table").replaceChildren(table);
}

function renderTrends(t) {
  const has = t.dates.length > 0;
  $("trends-empty").hidden = has;
  $("trends-body").hidden = !has;
  if (!has) return;
  // All simulated: say it once per section and chart, not under every date. Mixed: per point.
  const allSim = t.simulated.every(Boolean);
  const sim = allSim ? " (simulated)" : "";
  $("trends-tag").replaceChildren(allSim ? simTag() : "");
  renderLevels(t, allSim);
  const x = simLabels(t.dates.map((d) => when(d)), allSim ? t.dates.map(() => false) : t.simulated);
  const c = t.cutoffs;
  const s = t.series;
  const measured = (vs) => vs.filter((v) => v !== null && v !== undefined);
  lineChart("chart-tug", {
    labels: x, label: `Timed Up and Go, s${sim}`, values: s.tug_s, baseline: t.baseline.tug_s,
    cutoff: c.tug_s, cutoffLabel: `STEADI: ${c.tug_s} s or more flags`, flagAbove: true, fromZero: true,
    suggestedMax: Math.max(c.tug_s + 4, ...measured(s.tug_s).map((v) => v + 2)),
    aria: chartLabel("Timed Up and Go", t.dates, s.tug_s, "s", `STEADI flags ${c.tug_s} seconds or more.`),
  });
  lineChart("chart-chair", {
    labels: x, label: `Chair stands in 30 s${sim}`, values: s.chair_stands, baseline: t.baseline.chair_stands,
    cutoff: c.chair_stands, cutoffLabel: `STEADI: under ${c.chair_stands} flags (${chairGroup(c)})`, flagAbove: false, fromZero: true,
    aria: chartLabel("Chair stands in 30 seconds", t.dates, s.chair_stands, "",
      c.chair_stands ? `STEADI flags under ${c.chair_stands} for ${chairGroup(c)}.` : ""),
  });
  stanceChart(x, t, sim);
  lineChart("chart-cost", {
    labels: x, label: `Dual-task cost, %${sim}`, values: s.dual_task_cost_pct, baseline: t.baseline.dual_task_cost_pct,
    cutoff: null, aria: chartLabel("Dual-task cost", t.dates, s.dual_task_cost_pct, "%", "Ours, not STEADI: no cutoff."),
  });
  renderTrendTable(t);
}

function planRow(name, detail, value, unit) {
  const row = h("div", null, { class: "row" });
  const nameCol = h("div", null, { class: "r-name" });
  nameCol.append(h("p", name, { class: "r-title" }));
  const metaCol = h("div", null, { class: "r-meta" });
  metaCol.append(h("span", detail));
  const valueCol = h("div", null, { class: "r-value" });
  valueCol.append(big(value, unit));
  row.append(nameCol, metaCol, valueCol);
  return row;
}

function renderExercise(plan, adherence, sessions) {
  const sts = plan.sit_to_stand;
  const bal = plan.balance;
  const goal = adherence.target_days_per_week;
  const rows = h("div", null, { class: "rows" });
  rows.append(
    planRow("Sit-to-stands", "Sets × reps, each session", `${sts.sets} × ${sts.reps}`, "reps"),
    planRow("Supported holds", `Holds × seconds, ${STANCE_NAME[bal.stance]} stance`, `${bal.holds} × ${bal.target_s}`, "s"),
    planRow("Exercise days in the last 7", `${goal} planned a week`, adherence.last_7_days, `of ${goal}`),
  );
  $("plan").replaceChildren(rows, h("p", `Why: ${plan.why}.`, { class: "why" }));
  const weeks = adherence.weeks;
  const today = new Date();
  const labels = weeks.map((w, i) => {
    const [y, mo, d] = w.week_start.split("-").map(Number);
    const l = [when(w.week_start)];
    if (i === weeks.length - 1 && new Date(y, mo - 1, d + 7) > today) l.push("so far"); // this week isn't over
    if (w.simulated) l.push("Simulated");
    return l.length === 1 ? l[0] : l;
  });
  charts.adherence?.destroy();
  charts.adherence = new Chart($("chart-adherence"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        { type: "bar", label: "Exercise days per week", data: weeks.map((w) => w.days), backgroundColor: COLOR.blue,
          borderRadius: 2, maxBarThickness: 56, order: 1 },
        // order 0 draws last, so the goal line stays visible over bars that reach it
        { type: "line", label: `Goal: ${goal} days a week`, data: weeks.map(() => goal), pointRadius: 0,
          borderColor: COLOR.ink, backgroundColor: COLOR.ink, borderDash: [8, 6], borderWidth: 2.5, order: 0 },
      ],
    },
    options: { scales: (() => {
      const a = axes(COLOR.muted, COLOR.line);
      Object.assign(a.y, { min: 0, max: 7, ticks: { ...a.y.ticks, precision: 0 } });
      return a;
    })() },
  });
  $("chart-adherence").setAttribute("aria-label", `Exercise days per week, last ${weeks.length} weeks: `
    + `${weeks.map((w) => `${when(w.week_start)} ${w.days}`).join(", ")}. Goal ${goal} days a week; the last week is still going.`);
  const box = $("sessions");
  box.replaceChildren(h("h3", "Recent sessions", { class: "sub" }));
  if (!sessions.length) box.append(h("p", "No exercise sessions yet.", { class: "empty" }));
  for (const e of [...sessions].reverse()) {
    const reps = e.sets.map((x) => x.reps ?? "not measured").join(" + ");
    const holds = e.holds.map((x) => (x.hold_s === undefined ? "not measured"
      : `${Math.round(x.hold_s * 10) / 10}${x.target_s ? ` of ${x.target_s}` : ""} s`)).join(", ");
    const row = h("div", null, { class: "session-row" });
    const whenEl = h("span", when(e.date), { class: "when" });
    if (e.simulated) whenEl.append(simTag());
    row.append(whenEl, h("span", `Sit-to-stands ${reps || "none"} · holds ${holds || "none"}`, { class: "what" }));
    box.append(row);
  }
}

// ---- summary: fetched only when asked, since the AI family text can take a few seconds ------------
function clearSummary() {
  $("family-text").textContent = "";
  $("copy-doctor").hidden = true;
  $("family-summary").hidden = true;
  $("doctor-text").hidden = true;
  $("print-doctor").hidden = true;
  $("download-doctor").hidden = true;
  $("summary-tag").replaceChildren();
  $("doctor-summary-tag").replaceChildren();
}

// Busy buttons stay enabled (aria-disabled) so keyboard focus doesn't drop to the page.
// Who and when: on printed, downloaded and copied doctor text only (on screen, and to the AI, it has no name).
function docHead() {
  const p = lastPerson;
  const who = [p.name, p.profile.age ? `age ${p.profile.age}` : "", p.profile.sex || ""].filter(Boolean).join(", ");
  const today = new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" });
  return `${who}. Summary made ${today}.`;
}

async function makeSummary(e) {
  if (making || !hasCheckin) return;
  const fromDoctor = !!e && e.currentTarget === $("make-summary-doctor");
  making = true;
  const pid = personId;
  const buttons = [$("make-summary"), $("make-summary-doctor")];
  const was = buttons.map((b) => b.textContent);
  for (const b of buttons) {
    b.setAttribute("aria-busy", "true");
    b.setAttribute("aria-disabled", "true");
    b.textContent = "Making the summary…";
  }
  say("");
  hush();
  try {
    const s = await api("GET", `/api/people/${encodeURIComponent(pid)}/summary`);
    if (pid !== personId) return; // the person changed while it was being made
    $("family-text").textContent = s.family; // an always-shown live region, so it's announced
    $("family-by").replaceChildren(s.family_by === "ai" ? h("span", "AI-written", { class: "tag tag-ai" }) : "");
    $("doctor-text").textContent = s.doctor;
    $("doctor-text").dataset.head = docHead(); // printed above the text (index.html print styles)
    for (const id of ["summary-tag", "doctor-summary-tag"]) $(id).replaceChildren(s.simulated ? simTag() : "");
    $("family-summary").hidden = false;
    $("doctor-text").hidden = false;
    $("print-doctor").hidden = false;
    $("download-doctor").hidden = false;
    $("copy-doctor").hidden = false;
    if (fromDoctor) $("doctor-text").focus(); // read out where it appeared
  } catch (err) {
    if (pid === personId) say(`Couldn't make the summary: ${err.message}`);
  } finally {
    making = false;
    for (const [i, b] of buttons.entries()) {
      b.removeAttribute("aria-busy");
      b.removeAttribute("aria-disabled");
      b.textContent = was[i];
    }
  }
}

// http:// on the tablet's local network isn't a secure context, so there's no clipboard API: fall back.
async function copyText(text, b, label) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const t = h("textarea", null, { style: "position: fixed; opacity: 0" });
    t.value = text;
    document.body.append(t);
    t.select();
    const ok = document.execCommand("copy");
    t.remove();
    if (!ok) {
      say("Couldn't copy. Select the summary and copy it instead.");
      return;
    }
  }
  b.textContent = "Copied";
  setTimeout(() => (b.textContent = label), 2000);
}

// ---- Grok: one switch (GET/PUT /api/ai) for the summary, Ask Steady and every other AI call ------------
async function loadAi() {
  renderAi(await api("GET", "/api/ai"));
}

function renderAi(s) {
  aiStatus = s;
  $("ai-line").textContent = s.on ? "Grok: on" : "Grok: off (works offline)";
  $("ai-why").textContent = s.on
    ? "Summaries, questions, Listen, and the animal count are sent to xAI without the name."
    : s.blocked_by === "no key" ? "No xAI key is set, so nothing leaves the laptop."
    : s.blocked_by === "setting" ? "Turned off by the CHECKIN_AI setting, so nothing leaves the laptop."
    : "Nothing leaves the laptop.";
  $("ai-toggle").hidden = !s.available || !!state?.demo; // on the public demo only the host decides
  $("ai-toggle").textContent = s.on ? "Turn Grok off" : "Turn Grok on";
  renderAsk();
  if (!s.on) {
    animalsMode = null; // a recording already in flight is dropped, not sent
    if (recording) stopRecording(false);
  }
  renderAnimalsOptin();
}

function renderAsk() {
  $("ask").hidden = !(aiStatus && aiStatus.on && hasCheckin);
}

function clearAsk() {
  $("ask-out").hidden = true;
  $("ask-q").value = "";
  $("ask-tag").replaceChildren();
}

async function askSteady(e) {
  e.preventDefault();
  const q = $("ask-q").value.trim();
  if (asking || !q) return;
  asking = true;
  const pid = personId;
  const b = $("ask-go");
  b.setAttribute("aria-busy", "true");
  b.textContent = "Asking…";
  say("");
  try {
    const r = await api("POST", `/api/people/${encodeURIComponent(pid)}/ask`, { question: q });
    if (pid !== personId) return;
    $("ask-question").textContent = q;
    $("ask-answer").textContent = r.answer || "Grok couldn't answer just now. Here is the summary instead.";
    $("ask-summary").textContent = r.summary || "";
    $("ask-summary").hidden = !r.summary;
    $("ask-by").replaceChildren(
      r.by === "ai" ? h("span", "AI-written", { class: "tag tag-ai" })
        : r.by === "blocked" ? h("span", `Held back by the claims check: ${r.reason}`, { class: "note" }) : "",
    );
    $("ask-tag").replaceChildren(r.simulated ? simTag() : "");
    $("ask-out").hidden = false;
  } catch (err) {
    if (pid === personId) say(`Couldn't ask: ${err.message}`);
    if (err.status === 503) run(loadAi);
  } finally {
    asking = false;
    b.removeAttribute("aria-busy");
    b.textContent = "Ask";
  }
}

// ---- controls -----------------------------------------------------------------------------------
async function run(fn) {
  try {
    say("");
    await fn();
  } catch (e) {
    say(e.message);
  }
}

function profileBody() {
  const f = $("profile");
  return {
    name: f.name.value.trim(),
    age: f.age.value ? Number(f.age.value) : null,
    sex: f.sex.value || null,
    fallen: f.fallen.checked,
    unsteady: f.unsteady.checked,
    worried: f.worried.checked,
  };
}

// Edit this person, or (isNew) add a person with the same form.
function setProfileMode(isNew) {
  newPerson = isNew;
  $("profile-h").textContent = isNew ? "Add a person" : "Edit profile";
  $("profile-save").textContent = isNew ? "Add person" : "Save";
  if (isNew) $("profile").reset();
  else if (lastPerson) fillProfile(lastPerson);
}

function openProfile(message = "", isNew = false) {
  setProfileMode(isNew);
  go("home");
  const readOnly = !isNew && !!lastPerson?.simulated; // the server refuses edits to simulated people
  $("profile").hidden = readOnly;
  $("profile-panel").hidden = false;
  $("edit-profile").setAttribute("aria-expanded", String(!isNew));
  $("add-person").setAttribute("aria-expanded", String(isNew));
  $("profile-msg").textContent = readOnly
    ? `${lastPerson.name} is example data and can't be changed. Use Add a person to try it with someone real.`
    : message;
  const f = $("profile");
  (readOnly ? $("close-profile") : message && !f.age.value ? f.age : message && !f.sex.value ? f.sex : f.name).focus();
}

// Focus goes back to the control that opened the panel (or to `to`), never to the page.
function closeProfile(to) {
  const back = to instanceof HTMLElement ? to : $(newPerson ? "add-person" : "edit-profile");
  $("profile-panel").hidden = true;
  $("profile").hidden = false;
  $("edit-profile").setAttribute("aria-expanded", "false");
  $("add-person").setAttribute("aria-expanded", "false");
  setProfileMode(false);
  back.focus();
}

function startSession(body) {
  return run(async () => {
    await api("POST", "/api/session", { person_id: personId, ...body });
    go("checkin");
  });
}

// The server refuses a check-in without age and sex (400); then open the profile with the saved values.
// Start check-in shows the setup checklist; "We're ready" starts the session.
function startCheckin() {
  if (lastPerson && !profileReady) {
    openProfile("Add age and sex first. They're used to compare leg strength with others the same age.");
    return;
  }
  ended = false;
  setup = true;
  go("checkin");
  $("setup-h").focus();
}

function beginCheckin() {
  return run(async () => {
    try {
      await chooseAnimals();
      await api("POST", "/api/session", { person_id: personId, mode: "checkin" });
      // the setup screen stays until the "running" state arrives
    } catch (e) {
      setup = false;
      renderCheckin(state);
      if (e.status !== 400) throw e;
      await loadDashboard();
      openProfile("Please add age and sex first, then press Start check-in. "
        + "They're used to compare leg strength with others the same age.");
    }
  });
}

// The big "I'm ready" and the small helper control both press the one button.
function pressButton(e) {
  if (e.currentTarget.getAttribute("aria-disabled") === "true") return; // just after "Go": the server ignores it
  audio = audio || new AudioContext(); // browsers only allow sound after a click
  run(() => api("POST", "/api/button"));
}

for (const id of ["button", "helper"]) {
  $(id).onclick = pressButton;
  $(id).onkeydown = (e) => e.repeat && e.preventDefault(); // holding Enter down is one press, not many
}
$("setup-go").onclick = beginCheckin;
$("animals-on").onchange = $("animals-sample").onchange = renderAnimalsOptin;
$("setup-back").onclick = () => {
  setup = false;
  renderCheckin(state);
  $("start-checkin-2").focus();
};
$("done-again").onclick = () => (state && state.mode === "exercise" ? startSession({ mode: "exercise" }) : startCheckin());
$("start-checkin").onclick = startCheckin;
$("start-checkin-2").onclick = startCheckin;
$("start-exercise").onclick = () => startSession({ mode: "exercise" }); // today's plan; the quick one is on Check-in
$("start-plan").onclick = () => startSession({ mode: "exercise" });
$("start-quick").onclick = () => startSession({ mode: "exercise", plan: QUICK_PLAN });
$("arms-used").onclick = () => run(() => api("POST", "/api/stop", { reason: "arms_used" }));
$("cancel").onclick = () => {
  const what = state && state.mode === "exercise" ? "exercise" : "check-in";
  if (confirm(`Stop the ${what}? Nothing from it will be saved.`)) run(() => api("POST", "/api/stop", { reason: "cancel" }));
};
$("edit-profile").onclick = () => ($("profile-panel").hidden || newPerson ? openProfile() : closeProfile());
$("add-person").onclick = () => ($("profile-panel").hidden || !newPerson ? openProfile("", true) : closeProfile());
$("close-profile").onclick = () => closeProfile();
$("make-summary").onclick = makeSummary;
$("make-summary-doctor").onclick = makeSummary;
$("ask-form").onsubmit = askSteady;
$("ai-toggle").onclick = () => run(async () => renderAi(await api("PUT", "/api/ai", { on: !aiStatus.on })));
$("copy-summary").onclick = () => copyText($("family-text").textContent, $("copy-summary"), "Copy summary");
$("listen-summary").onclick = listenSummary;
$("copy-doctor").onclick = () => copyText(`${docHead()}\n\n${$("doctor-text").textContent}`, $("copy-doctor"), "Copy text");
$("print-doctor").onclick = () => {
  document.body.classList.add("print-doctor"); // the print stylesheet then shows only the doctor text
  window.print();
};
addEventListener("afterprint", () => document.body.classList.remove("print-doctor"));
$("download-doctor").onclick = () => {
  const text = `${docHead()}\n\n${$("doctor-text").textContent}`;
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
  h("a", null, { href: url, download: `fall-risk-screening-summary-${new Date().toLocaleDateString("en-CA")}.txt` }).click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
addEventListener("hashchange", show);
$("person").onchange = (e) => {
  hush();
  personId = e.target.value;
  rememberPerson(personId);
  run(loadDashboard);
};
$("profile").onsubmit = (e) => {
  e.preventDefault();
  run(async () => {
    if (newPerson) {
      const p = await api("POST", "/api/people", profileBody());
      personId = p.id;
      rememberPerson(personId);
    } else {
      await api("PUT", `/api/people/${encodeURIComponent(personId)}`, profileBody());
    }
    await loadPeople();
    closeProfile($("start-checkin")); // saved: the next step is right there (it reads "Start check-in" now)
  });
};

show();
connect();
// Keeps trying until the laptop answers; the WebSocket's reconnect also reloads.
async function firstLoad() {
  try {
    await loadPeople();
  } catch (e) {
    if (lastPerson) return; // a reconnect already loaded it
    $("answer-level").className = "level-tile level-none";
    $("answer-level").textContent = "";
    $("answer").textContent = "Can't load the dashboard yet.";
    $("answer-sub").textContent = "This page keeps trying and loads by itself once it reaches the laptop.";
    say(e.message);
    setTimeout(firstLoad, 5000);
  }
}
// Canvas text only uses the web font once it has loaded, so wait for it before the first charts.
document.fonts.load("16px Archivo").catch(() => {}).then(firstLoad);
