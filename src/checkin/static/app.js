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
};
const VIEWS = ["home", "checkin", "doctor"];
const LEVEL_WORD = { green: "Green", amber: "Amber", red: "Red" };
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
const COLOR = { ink: "#080912", blue: "#2a4093", muted: "#464b5d", line: "#d5d9e2", soft: "#b3c1f4", onBlue: "#e3e8fb" };
const BACK_HOME_MS = 15000;

let personId = null;
let state = null;
let audio = null;
let online = null; // null while the first WebSocket connects
let view = null;
let ended = false; // a session ended while this page watched: show its result on the Check-in view
let homeTimer = null;
let revealed = false;
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

// "2026-08-29T10:00:00" (local time, no zone) -> "Sat 29 Aug, 10:00"; "2026-08-08" -> "8 Aug";
// long: "Saturday 29 August".
function when(iso, long = false) {
  const [y, mo, d, hh = 0, mm = 0] = iso.split(/[-T:]/).map(Number);
  const date = new Date(y, mo - 1, d, hh, mm);
  if (long) return date.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
  const opts = iso.includes("T")
    ? { weekday: "short", day: "numeric", month: "short", hour: "numeric", minute: "2-digit" }
    : { day: "numeric", month: "short" };
  return date.toLocaleString(undefined, opts);
}

const seconds = (v) => `${v} ${v === 1 ? "second" : "seconds"}`;

async function api(method, path, body) {
  const r = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const err = new Error(typeof data.detail === "string" ? data.detail : `${r.status} ${JSON.stringify(data.detail)}`);
    err.status = r.status;
    throw err;
  }
  return data;
}

function say(text) {
  $("msg").textContent = text;
}

function play(name) {
  if (!state || state.base !== "virtual" || !audio) return; // a real base station beeps by itself
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

// ---- views: Home, Check-in, For the doctor (the URL hash; no reloads, the WebSocket stays open) -----
function show() {
  const v = VIEWS.includes(location.hash.slice(1)) ? location.hash.slice(1) : "home";
  if (v !== "checkin" && ended) {
    ended = false;
    clearTimeout(homeTimer);
  }
  for (const x of VIEWS) $(`view-${x}`).hidden = x !== v;
  for (const a of document.querySelectorAll(".views a")) {
    if (a.getAttribute("href") === `#${v}`) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  }
  if (v !== view) scrollTo(0, 0);
  view = v;
  if (state) renderCheckin(state);
  if (v === "doctor") for (const c of Object.values(charts)) c.resize(); // drawn while hidden
}

function go(v) {
  if (location.hash !== `#${v}`) history.pushState(null, "", `#${v}`);
  show();
}

// ---- live state ---------------------------------------------------------------------------------
function stepTitle(step) {
  const [kind, n] = step.id.split("#");
  if (kind === "sit_to_stand") return `Stand up and sit down: round ${n}`;
  if (kind.startsWith("hold_")) return `Hold still at the counter: ${n}`;
  return STEP_TITLE[kind] || step.label;
}

function liveLine(s) {
  const live = s.live || {};
  const step = s.steps.find((x) => x.status === "running");
  if (!step) return "";
  if (live.reps !== undefined) {
    return live.target
      ? `${live.reps} of ${live.target} stands so far`
      : `${live.reps} ${live.reps === 1 ? "stand" : "stands"} so far`;
  }
  if (live.elapsed_s !== undefined) {
    const holding = /^(balance|hold)_/.test(step.id);
    return `${holding ? "Holding" : "Timing"}… ${seconds(Math.floor(live.elapsed_s))}`;
  }
  return "";
}

function renderWarnings() {
  const w = [];
  if (online === false) w.push("Lost the connection to the laptop. Trying again…");
  else if (state) {
    if (!state.base_connected) w.push("The button box isn't connected. Check its cable to the laptop.");
    if (!(state.source.rate_hz > 0)) w.push("The belt isn't sending any movement. Check that it's switched on and charged.");
  }
  $("warning").replaceChildren(...w.map((t) => h("p", t)));
  $("warning").hidden = !w.length;
}

function renderCheckin(s) {
  const screen = s.phase === "running" ? "running" : ended ? "done" : "idle";
  $("ci-idle").hidden = screen !== "idle";
  $("ci-running").hidden = screen !== "running";
  $("ci-done").hidden = screen !== "done";
  $("station").dataset.phase = s.phase;
  if (screen !== "running") return;
  $("led").className = `led ${s.led}`;
  const i = s.steps.findIndex((x) => x.status === "waiting" || x.status === "running");
  const n = i >= 0 ? i + 1 : Math.min(s.steps.filter((x) => x.status !== "pending").length + 1, s.steps.length);
  $("step-count").textContent = s.steps.length ? `Step ${n} of ${s.steps.length}` : "Getting ready";
  $("steps-tag").replaceChildren(s.source.simulated ? simTag() : "");
  $("step-title").textContent = i >= 0 ? stepTitle(s.steps[i]) : "";
  $("prompt").textContent = s.prompt || "Getting ready…";
  $("live").textContent = liveLine(s);
  const chair = s.steps.some((x) => x.id === "chair_stand" && x.status === "running");
  $("arms-used").hidden = !chair;
  $("arms-used").disabled = !chair;
}

function plainRow(list, name, text, tag = "h3") {
  const el = h("div", null, { class: "row two" });
  const left = h("div", null, { class: "r-name" });
  left.append(h(tag, name));
  const right = h("div", null, { class: "r-value" });
  right.append(h("span", text, { class: "text" }));
  el.append(left, right);
  list.append(el);
}

// The result in plain words once a session ends; then back to Home.
function renderDone(s) {
  const r = s.last_record;
  const tile = $("done-level");
  const list = h("div", null, { class: "rows" });
  $("done-list").replaceChildren();
  if (s.phase !== "done" || !r) {
    tile.hidden = true;
    $("done-answer").textContent = s.prompt || "Stopped. Nothing was saved.";
    $("done-sub").textContent = "";
    return;
  }
  tile.hidden = false;
  const held = (v) => (v === null || v === undefined ? "not measured" : `held ${seconds(v)}`);
  if (s.mode === "checkin") {
    const a = answerFor(r, "this");
    tile.className = `level-tile display level-${a.level}`;
    tile.textContent = a.word;
    $("done-answer").textContent = a.text;
    $("done-sub").textContent = a.sub;
    const m = r.metrics;
    plainRow(list, "Stand up and walk", m.tug_s === null ? "not measured" : seconds(m.tug_s));
    plainRow(list, "Walk again, naming animals", m.dual_tug_s === null ? "not measured" : seconds(m.dual_tug_s));
    plainRow(list, "Stand up from the chair",
      m.chair_stands === null ? "not measured" : `${m.chair_stands} times in 30 seconds`);
    plainRow(list, "Feet together", held(m.feet_together_s));
    plainRow(list, "One foot a little ahead", held(m.semi_tandem_s));
    plainRow(list, "One foot in front of the other", held(m.tandem_s));
  } else {
    tile.className = "level-tile display level-none";
    tile.textContent = "Done";
    $("done-answer").textContent = "Exercise done. Nice work.";
    $("done-sub").textContent = "It's saved, and counts towards this week.";
    const counted = r.sets.filter((x) => x.reps !== undefined);
    if (r.sets.length) {
      const total = counted.reduce((sum, x) => sum + x.reps, 0);
      plainRow(list, "Stood up and sat down",
        `${total} times${counted.length < r.sets.length ? " (some not measured)" : ""}`);
    }
    if (r.holds.length) {
      plainRow(list, "Held still at the counter",
        r.holds.map((x) => (x.hold_s === undefined ? "not measured" : seconds(x.hold_s))).join(", "));
    }
  }
  if (r.simulated) $("done-sub").append(" ", simTag());
  $("done-list").append(list);
}

function renderState(s) {
  const was = state && state.phase;
  state = s;
  const running = s.phase === "running";
  document.body.dataset.running = running;
  if (running) {
    ended = false;
    clearTimeout(homeTimer);
    if (view !== "checkin") go("checkin"); // the Check-in view takes over while a session runs
  } else if (was === "running") {
    ended = true;
    renderDone(s);
    if (view !== "checkin") go("checkin");
    homeTimer = setTimeout(() => go("home"), BACK_HOME_MS);
  }
  renderWarnings();
  renderCheckin(s);
  for (const id of ["start-checkin", "start-exercise", "start-checkin-2", "start-plan", "start-quick"]) {
    $(id).disabled = running;
  }
}

function connect() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onopen = () => {
    online = true;
    renderWarnings();
  };
  ws.onmessage = (e) => {
    const ev = JSON.parse(e.data);
    if (ev.type === "state") renderState(ev);
    else if (ev.type === "cue") play(ev.name);
    else if (ev.type === "saved" && ev.person_id === personId) loadDashboard();
  };
  ws.onclose = () => {
    online = false;
    renderWarnings();
    setTimeout(connect, 1000);
  };
}

// ---- dashboard ----------------------------------------------------------------------------------
async function loadPeople() {
  const people = await api("GET", "/api/people");
  const sel = $("person");
  sel.replaceChildren(...people.map((p) => new Option(p.name, p.id)));
  if (!people.some((p) => p.id === personId)) personId = (people.find((p) => !p.simulated) || people[0] || {}).id;
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
}

function renderProfile(person) {
  $("person-tag").replaceChildren(person.simulated ? simTag() : "");
  const f = $("profile");
  f.name.value = person.name;
  f.age.value = person.profile.age ?? "";
  f.sex.value = person.profile.sex ?? "";
  for (const k of ["fallen", "unsteady", "worried"]) f[k].checked = !!person.profile[k];
}

// ---- Home: plain words only ---------------------------------------------------------------------
function answerFor(r, which = "the last") {
  if (!r) {
    return { level: "none", word: "None yet", text: "No check-in yet.",
      sub: "The check-in takes about 3 minutes. Press Start check-in when you're ready." };
  }
  if (!r.alert) {
    return { level: "green", word: "Green", text: `Nothing flagged in ${which} check-in.`,
      sub: "Keep up the exercises most days." };
  }
  return { level: r.level, word: LEVEL_WORD[r.level], text: "This check-in flags increased fall risk.", sub: r.alert.advice };
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
  const verdict = (value, flag, bad, good) => {
    if (value === null || value === undefined) return { cls: "unknown", word: "Not measured.", text: "" };
    return flag ? { cls: "flag", word: "Flagged.", text: bad } : { cls: "ok", word: "Nothing flagged.", text: good };
  };
  const group = (c.chair_label || "").replace(/\s*\(.*\)$/, ""); // drop "(the youngest STEADI group)"
  const chair = !c.chair_stands
    ? { cls: "unknown", word: "Can't compare yet.", text: "Add age and sex in Edit profile to compare with others the same age." }
    : verdict(m.chair_stands, flagged.has("chair_stand"), `Fewer than average for ${group}.`,
      `Average or better for ${group}.`);
  const stances = [m.feet_together_s, m.semi_tandem_s, m.tandem_s];
  const held = stances.every((v) => v === null) ? null : `${stances.filter((v) => v !== null && v >= 10).length} of 3`;
  box.append(
    card("Standing up and walking", m.tug_s, "seconds", "To stand up, walk to the line and back, and sit down.",
      verdict(m.tug_s, flagged.has("tug"), `${c.tug_s} seconds or longer is flagged.`, `Under ${c.tug_s} seconds.`),
      trendLine(latest, "tug_s", "seconds")),
    card("Leg strength", m.chair_stands, "times", "Stood up from a chair in 30 seconds, arms crossed.", chair,
      trendLine(latest, "chair_stands", "times")),
    card("Balance", held, "positions held",
      "10 seconds each, standing still in three positions, each harder than the last.",
      verdict(m.tandem_s, flagged.has("balance"), "Couldn't hold the hardest position for 10 seconds.",
        "Held the hardest position for 10 seconds."),
      trendLine(latest, "tandem_s", "")),
  );
}

function renderHome(d) {
  const latest = d.latest;
  const a = answerFor(latest);
  const tile = $("answer-level");
  tile.className = `level-tile display level-${a.level}`;
  tile.textContent = a.word;
  $("answer").textContent = a.text;
  if (!revealed) {
    $("answer-wrap").classList.add("play"); // the one entrance on the page, on first load only
    revealed = true;
  }
  $("answer-sub").textContent = a.sub;
  const more = [];
  if (latest) {
    const yes = Object.entries(latest.key_questions).filter(([, v]) => v).map(([k]) => ANSWERED_YES[k]);
    if (yes.length) more.push(`Also flagged: ${yes.join("; ")}.`);
    const worse = (latest.declines || []).map((x) => TRACKED_WORDS[x.id] || x.id);
    if (worse.length) more.push(`Worse than usual two check-ins in a row: ${worse.join(", ")}.`);
  }
  $("answer-more").textContent = more.join(" ");
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
  days.append(h("span", `${adherence.last_7_days} of ${adherence.target_days_per_week}`, { class: "num" }),
    h("p", "days of exercise in the past week"));
  const rows = h("div", null, { class: "rows" });
  if (sts.sets) plainRow(rows, "Stand up from a chair and sit back down", `${sts.sets} rounds of ${sts.reps}`, "h4");
  if (bal.holds) {
    plainRow(rows, `Stand still, holding on to the counter, ${STANCE_WORDS[bal.stance]}`,
      `${bal.holds} times, ${bal.target_s} seconds each`, "h4");
  }
  const today = h("div", null, { class: "today" });
  today.append(h("h3", "Today's exercise", { class: "sub" }), rows);
  $("home-exercise").replaceChildren(days, today);
  $("home-ex-tag").replaceChildren(adherence.weeks.some((w) => w.simulated) ? simTag() : "");
  $("plan-words").textContent = [
    sts.sets ? `${sts.sets} rounds of ${sts.reps} stand-ups from a chair` : "",
    bal.holds ? `${bal.holds} holds of ${bal.target_s} seconds at the counter, ${STANCE_WORDS[bal.stance]}` : "",
  ].filter(Boolean).join(", then ") + ".";
}

// ---- For the doctor: every clinical number ----------------------------------------------------------
function renderDoctor(d) {
  const p = d.person;
  const facts = $("doc-facts");
  facts.replaceChildren(h("b", p.name), h("span", `Age ${p.profile.age ?? "not given"}`),
    h("span", p.profile.sex ?? "sex not given"));
  if (p.simulated) facts.append(simTag());
  renderAlert(d.latest);
  renderResults(d.latest);
  renderTrends(d.trends);
  renderExercise(d.plan, d.adherence, d.exercise);
}

function renderAlert(latest) {
  const box = $("alert");
  box.replaceChildren();
  if (!latest) return;
  const head = h("p", null, { class: "alert-head" });
  head.append(h("span", latest.level, { class: `level-tile display level-${latest.level}` }),
    h("span", latest.alert ? "Flags increased fall risk" : "No flags in the latest check-in"),
    h("span", "Level is our summary, not STEADI's.", { class: "meta" }));
  box.append(head);
  if (!latest.alert) return;
  const ul = h("ul", null, { class: "alert-items" });
  for (const item of latest.alert.items) ul.append(h("li", item));
  box.append(ul, h("p", latest.alert.advice, { class: "advice" }), h("p", latest.alert.note, { class: "note" }));
}

// Change from baseline as a line of text; `worse` is past the API's threshold.
function change(latest, key) {
  const c = latest.changes[key];
  const p = h("span");
  if (!c) {
    p.textContent = "Change from baseline: not enough history";
    return p;
  }
  p.append("Change from baseline: ",
    h("b", `${c.change > 0 ? "+" : ""}${c.change}${CHANGE_UNITS[key]}`), ` (baseline ${c.baseline}) `);
  if (c.worse) p.append(h("span", "Worse", { class: "tag tag-worse" }));
  return p;
}

function renderResults(latest) {
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
  const flagged = new Set(latest.flags.map((f) => f.id));
  const sway = (v) => `Sway ${v === null || v === undefined ? "not measured" : `${v} m/s²`}`;
  meta.append(h("span", when(latest.date)), h("span", `Level ${latest.level}`), h("span", `Source ${latest.source}`));
  if (latest.simulated) meta.append(simTag());
  const yes = Object.entries(latest.key_questions).filter(([, v]) => v).map(([k]) => k);
  const rows = [
    { name: "Key questions", text: yes.length ? `Yes: ${yes.join(", ")}` : "All no", cut: "STEADI flags any yes",
      flag: "key_questions" },
    { name: "Timed Up and Go", v: m.tug_s, unit: "s", cut: `STEADI flags ${c.tug_s} s or more`, flag: "tug",
      change: "tug_s" },
    { name: "TUG naming animals", v: m.dual_tug_s, unit: "s", cut: "Ours, not STEADI: tracked vs. baseline" },
    { name: "Dual-task cost", v: m.dual_task_cost_pct, unit: "%", cut: "Ours, not STEADI: tracked vs. baseline",
      change: "dual_task_cost_pct" },
    { name: "30-second chair stand", v: m.chair_stands, unit: "stands", flag: "chair_stand", change: "chair_stands",
      cut: c.chair_stands ? `STEADI flags under ${c.chair_stands} (${c.chair_label})` : "STEADI line needs age and sex" },
    { name: "Balance: feet together", v: m.feet_together_s, unit: "s", extra: sway(m.feet_together_sway) },
    { name: "Balance: semi-tandem", v: m.semi_tandem_s, unit: "s", extra: sway(m.semi_tandem_sway) },
    { name: "Balance: tandem", v: m.tandem_s, unit: "s", extra: sway(m.tandem_sway), cut: `STEADI flags under ${c.tandem_s} s`,
      flag: "balance", change: "tandem_s" },
  ];
  const list = h("div", null, { class: "rows" });
  for (const r of rows) {
    const isFlag = r.flag && flagged.has(r.flag);
    const row = h("div", null, { class: isFlag ? "row flagged" : "row" });
    const name = h("div", null, { class: "r-name" });
    name.append(h("h3", r.name));
    if (isFlag) name.append(h("span", "Flag", { class: "tag tag-flag" }));
    const metaCol = h("div", null, { class: "r-meta" });
    if (r.cut) metaCol.append(h("span", r.cut));
    if (r.extra) metaCol.append(h("span", r.extra));
    if (r.change) metaCol.append(change(latest, r.change));
    const value = h("div", null, { class: "r-value" });
    value.append(r.text !== undefined ? h("span", r.text, { class: "text" }) : big(r.v, r.unit));
    row.append(name, metaCol, value);
    list.append(row);
  }
  box.append(list);
}

// ---- charts -------------------------------------------------------------------------------------
Chart.defaults.font.family = "Archivo, system-ui, sans-serif";
Chart.defaults.font.size = 15;
Chart.defaults.color = COLOR.muted;
Chart.defaults.borderColor = COLOR.line;
Chart.defaults.maintainAspectRatio = false;
Chart.defaults.animation = false;
Object.assign(Chart.defaults.plugins.legend, { align: "start" });
Object.assign(Chart.defaults.plugins.legend.labels, { usePointStyle: true, pointStyle: "line", pointStyleWidth: 32, padding: 18 });
Object.assign(Chart.defaults.plugins.tooltip, {
  backgroundColor: COLOR.ink, padding: 12, cornerRadius: 2, displayColors: false,
  titleFont: { weight: "700", size: 15 }, bodyFont: { size: 15 },
});

function axes(color, grid) {
  return {
    x: { grid: { display: false }, border: { color: grid }, ticks: { color, maxRotation: 0, autoSkipPadding: 16 } },
    y: { grid: { color: grid }, border: { display: false }, ticks: { color, padding: 8 } },
  };
}

function lineChart(id, label, dates, values, cutoff, cutoffLabel) {
  charts[id]?.destroy();
  const datasets = [{
    label, data: values, spanGaps: true, borderColor: COLOR.ink, backgroundColor: COLOR.ink, borderWidth: 3,
    pointRadius: 5, pointHoverRadius: 7, pointBackgroundColor: "#fff", pointBorderColor: COLOR.ink, pointBorderWidth: 2.5,
  }];
  if (cutoff !== null && cutoff !== undefined) {
    datasets.push({ label: cutoffLabel, data: dates.map(() => cutoff), borderColor: COLOR.blue, backgroundColor: COLOR.blue,
      borderDash: [8, 6], borderWidth: 2, pointRadius: 0, pointHitRadius: 0 });
  }
  charts[id] = new Chart($(id), { type: "line", data: { labels: dates, datasets }, options: { scales: axes(COLOR.muted, COLOR.line) } });
}

function renderTrends(t) {
  const s = t.series;
  const c = t.cutoffs;
  const x = simLabels(t.dates.map((d) => when(d)), t.simulated);
  $("trends-empty").hidden = t.dates.length > 0;
  $("charts").hidden = !t.dates.length;
  lineChart("chart-tug", "Timed Up and Go (s)", x, s.tug_s, c.tug_s, "STEADI cutoff (12 s)");
  lineChart("chart-chair", "Chair stands in 30 s", x, s.chair_stands, c.chair_stands, "STEADI below-average line");
  lineChart("chart-tandem", "Tandem stance (s)", x, s.tandem_s, c.tandem_s, "STEADI cutoff (10 s)");
  lineChart("chart-cost", "Dual-task cost (%)", x, s.dual_task_cost_pct, null, "");
}

function planRow(name, detail, value, unit) {
  const row = h("div", null, { class: "row" });
  const nameCol = h("div", null, { class: "r-name" });
  nameCol.append(h("h3", name));
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
  const rows = h("div", null, { class: "rows" });
  rows.append(
    planRow("Sit-to-stands", "Sets × reps, each session", `${sts.sets} × ${sts.reps}`, "reps"),
    planRow("Supported holds", `Holds × seconds, ${bal.stance.replace("_", " ")} stance`, `${bal.holds} × ${bal.target_s}`, "s"),
    planRow("Exercise days in the last 7", `${adherence.target_days_per_week} planned a week`,
      adherence.last_7_days, `of ${adherence.target_days_per_week}`),
  );
  $("plan").replaceChildren(rows, h("p", `Why: ${plan.why}.`, { class: "why" }));
  const weeks = adherence.weeks;
  charts.adherence?.destroy();
  charts.adherence = new Chart($("chart-adherence"), {
    type: "bar",
    data: {
      labels: simLabels(weeks.map((w) => when(w.week_start)), weeks.map((w) => w.simulated)),
      datasets: [
        { type: "bar", label: "Exercise days per week", data: weeks.map((w) => w.days), backgroundColor: COLOR.soft,
          borderColor: COLOR.soft, borderRadius: 2, maxBarThickness: 56 },
        { type: "line", label: "Target", data: weeks.map(() => adherence.target_days_per_week), pointRadius: 0,
          borderColor: "#fff", backgroundColor: "#fff", borderDash: [8, 6], borderWidth: 3 },
      ],
    },
    options: {
      color: COLOR.onBlue,
      scales: (() => {
        const a = axes(COLOR.onBlue, "rgba(255, 255, 255, 0.2)");
        Object.assign(a.y, { min: 0, max: 7 });
        return a;
      })(),
    },
  });
  const box = $("sessions");
  box.replaceChildren(h("h3", "Recent sessions", { class: "sub" }));
  if (!sessions.length) box.append(h("p", "No exercise sessions yet.", { class: "empty" }));
  for (const e of [...sessions].reverse()) {
    const reps = e.sets.map((s) => s.reps ?? "not measured").join(" + ");
    const holds = e.holds.map((x) => (x.hold_s === undefined ? "not measured" : `${x.hold_s} s`)).join(", ");
    const row = h("div", null, { class: "session-row" });
    const whenEl = h("span", when(e.date), { class: "when" });
    if (e.simulated) whenEl.append(simTag());
    row.append(whenEl, h("span", `Sit-to-stands ${reps || "none"} · holds ${holds || "none"}`, { class: "what" }));
    box.append(row);
  }
}

// ---- summary: fetched only when asked, since the AI family text can take a few seconds ------------
function clearSummary() {
  $("family-summary").hidden = true;
  $("doctor-text").hidden = true;
  $("print-doctor").hidden = true;
  $("download-doctor").hidden = true;
  $("summary-tag").replaceChildren();
  $("doctor-summary-tag").replaceChildren();
}

async function makeSummary() {
  const pid = personId;
  const buttons = [$("make-summary"), $("make-summary-doctor")];
  const labels = buttons.map((b) => b.querySelector(".roll > span"));
  const was = labels.map((l) => l.textContent);
  for (const [i, b] of buttons.entries()) {
    b.disabled = true;
    b.setAttribute("aria-busy", "true");
    labels[i].textContent = "Making the summary…";
  }
  say("");
  try {
    const s = await api("GET", `/api/people/${encodeURIComponent(pid)}/summary`);
    if (pid !== personId) return; // the person changed while it was being made
    $("family-text").textContent = s.family;
    $("family-by").replaceChildren(s.family_by === "ai" ? h("span", "AI-written", { class: "tag tag-ai" }) : "");
    $("doctor-text").textContent = s.doctor;
    for (const id of ["summary-tag", "doctor-summary-tag"]) $(id).replaceChildren(s.simulated ? simTag() : "");
    $("family-summary").hidden = false;
    $("doctor-text").hidden = false;
    $("print-doctor").hidden = false;
    $("download-doctor").hidden = false;
  } catch (e) {
    if (pid === personId) say(`Couldn't make the summary: ${e.message}`);
  } finally {
    for (const [i, b] of buttons.entries()) {
      b.disabled = false;
      b.removeAttribute("aria-busy");
      labels[i].textContent = was[i];
    }
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

function openProfile(message = "") {
  go("home");
  $("profile-panel").hidden = false;
  $("edit-profile").setAttribute("aria-expanded", "true");
  $("profile-msg").textContent = message;
  const f = $("profile");
  (message && !f.age.value ? f.age : message && !f.sex.value ? f.sex : f.name).focus();
}

function closeProfile() {
  $("profile-panel").hidden = true;
  $("edit-profile").setAttribute("aria-expanded", "false");
}

function startSession(body) {
  return run(async () => {
    await api("POST", "/api/session", { person_id: personId, ...body });
    go("checkin");
  });
}

// The server refuses a check-in without age and sex (400); then open the profile with the saved values.
function startCheckin() {
  return run(async () => {
    try {
      await api("POST", "/api/session", { person_id: personId, mode: "checkin" });
      go("checkin");
    } catch (e) {
      if (e.status !== 400) throw e;
      await loadDashboard();
      openProfile("Please add age and sex first, then press Start check-in. "
        + "They're used to compare leg strength with others the same age.");
    }
  });
}

$("button").onclick = () => {
  audio = audio || new AudioContext(); // browsers only allow sound after a click
  run(() => api("POST", "/api/button"));
};
$("start-checkin").onclick = startCheckin;
$("start-checkin-2").onclick = startCheckin;
$("start-exercise").onclick = () => {
  go("checkin"); // the exercise choices: today's plan, or the quick exercise
  $("start-plan").focus();
};
$("start-plan").onclick = () => startSession({ mode: "exercise" });
$("start-quick").onclick = () => startSession({ mode: "exercise", plan: QUICK_PLAN });
$("arms-used").onclick = () => run(() => api("POST", "/api/stop", { reason: "arms_used" }));
$("cancel").onclick = () => run(() => api("POST", "/api/stop", { reason: "cancel" }));
$("edit-profile").onclick = () => ($("profile-panel").hidden ? openProfile() : closeProfile());
$("close-profile").onclick = closeProfile;
$("make-summary").onclick = makeSummary;
$("make-summary-doctor").onclick = makeSummary;
$("print-doctor").onclick = () => {
  document.body.classList.add("print-doctor"); // the print stylesheet then shows only the doctor text
  window.print();
};
addEventListener("afterprint", () => document.body.classList.remove("print-doctor"));
$("download-doctor").onclick = () => {
  const url = URL.createObjectURL(new Blob([$("doctor-text").textContent], { type: "text/plain" }));
  h("a", null, { href: url, download: `fall-risk-screening-summary-${new Date().toLocaleDateString("en-CA")}.txt` }).click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
addEventListener("hashchange", show);
$("person").onchange = (e) => {
  personId = e.target.value;
  run(loadDashboard);
};
$("profile").onsubmit = (e) => {
  e.preventDefault();
  run(async () => {
    await api("PUT", `/api/people/${encodeURIComponent(personId)}`, profileBody());
    $("profile-msg").textContent = "Saved.";
    await loadPeople();
  });
};
$("new-person").onclick = () => run(async () => {
  const p = await api("POST", "/api/people", profileBody());
  personId = p.id;
  $("profile-msg").textContent = `Saved ${p.name} as a new person.`;
  await loadPeople();
});

show();
connect();
// Canvas text only uses the web font once it has loaded, so wait for it before the first charts.
run(async () => {
  await document.fonts.load("16px Archivo").catch(() => {});
  await loadPeople();
});
