"use strict";
// Bare-bones dashboard: renders GET /api/people/{id}/dashboard and the /ws state stream (docs/API.md).

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
const STEP_UNITS = { tug_s: " s", stands: " stands", hold_s: " s held" };

let personId = null;
let state = null;
let audio = null;
const charts = {};

function h(tag, text, attrs = {}) {
  const el = document.createElement(tag);
  if (text !== undefined && text !== null) el.textContent = text;
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  return el;
}

async function api(method, path, body) {
  const r = await fetch(path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(typeof data.detail === "string" ? data.detail : `${r.status} ${JSON.stringify(data.detail)}`);
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

// ---- live state ---------------------------------------------------------------------------------
function stepSummary(r) {
  if (!r) return "";
  if (r.error) return `not measured: ${r.error}`;
  const parts = [];
  for (const [k, unit] of Object.entries(STEP_UNITS)) {
    if (k in r) parts.push(r[k] === null ? "not measured" : `${r[k]}${unit}`);
  }
  if ("reps" in r) parts.push(`${r.reps} of ${r.target} reps`);
  if (r.sway !== undefined) parts.push(`sway ${r.sway} m/s²`);
  if (r.method && r.method !== "sensor") parts.push(`(${r.method})`);
  if (r.arms_used) parts.push("(arms used)");
  return parts.join(" ");
}

function renderState(s) {
  state = s;
  $("led").className = `led ${s.led}`;
  $("base").textContent = `${s.base}${s.base_connected ? "" : " (not connected)"}`;
  const src = s.source;
  $("source").textContent = `${src.kind}, ${src.rate_hz} Hz`;
  if (src.simulated) $("source").append(" ", h("span", "Simulated", { class: "tag" }));
  $("prompt").textContent = s.prompt || "";
  const live = s.live || {};
  $("live").textContent = [
    live.elapsed_s !== undefined ? `${live.elapsed_s} s` : "",
    live.reps !== undefined ? `${live.reps}${live.target ? ` of ${live.target}` : ""} counted` : "",
  ].filter(Boolean).join(" · ");
  const list = $("steps");
  list.replaceChildren();
  for (const step of s.steps) {
    list.append(h("li", `${step.label}: ${step.status}${step.result ? ` — ${stepSummary(step.result)}` : ""}`));
  }
  const busy = s.phase === "running";
  for (const id of ["start-checkin", "start-exercise", "start-quick"]) $(id).disabled = busy;
  $("cancel").disabled = $("arms-used").disabled = !busy;
}

function connect() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onmessage = (e) => {
    const ev = JSON.parse(e.data);
    if (ev.type === "state") renderState(ev);
    else if (ev.type === "cue") play(ev.name);
    else if (ev.type === "saved" && ev.person_id === personId) loadDashboard();
  };
  ws.onclose = () => {
    $("source").textContent = "server disconnected, retrying…";
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
  renderAlert(d.alert, d.latest);
  renderResults(d.latest);
  renderTrends(d.trends);
  renderExercise(d.plan, d.adherence, d.exercise);
}

function renderProfile(person) {
  $("person-tag").replaceChildren(person.simulated ? h("span", "Simulated", { class: "tag" }) : "");
  const f = $("profile");
  f.name.value = person.name;
  f.age.value = person.profile.age ?? "";
  f.sex.value = person.profile.sex ?? "";
  for (const k of ["fallen", "unsteady", "worried"]) f[k].checked = !!person.profile[k];
  if (!person.simulated && !(person.profile.age && person.profile.sex)) $("profile-box").open = true;
}

function renderAlert(alert, latest) {
  const box = $("alert");
  box.replaceChildren();
  if (!latest) {
    box.append(h("p", "No check-in yet."));
    return;
  }
  if (!alert) {
    box.append(h("p", "No flags in the latest check-in. Keep up the exercises most days."));
    return;
  }
  box.append(h("p", `${alert.level.toUpperCase()}: ${alert.title}`, { class: "flag" }));
  const ul = h("ul");
  for (const item of alert.items) ul.append(h("li", item));
  box.append(ul, h("p", alert.advice), h("p", alert.note));
}

function change(latest, key) {
  const c = latest.changes[key];
  if (!c) return "not enough history";
  return `${c.change > 0 ? "+" : ""}${c.change} vs. baseline ${c.baseline}${c.worse ? " (worse)" : ""}`;
}

function renderResults(latest) {
  const box = $("results");
  box.replaceChildren();
  if (!latest) {
    box.append(h("p", "No check-in yet."));
    return;
  }
  const m = latest.metrics;
  const flagged = new Set(latest.flags.map((f) => f.id));
  const fmt = (v, unit) => (v === null || v === undefined ? "not measured" : `${v}${unit}`);
  const header = h("p", `${latest.date.replace("T", " ")} · level ${latest.level} · source ${latest.source} `);
  if (latest.simulated) header.append(h("span", "Simulated", { class: "tag" }));
  const table = h("table");
  const head = h("tr");
  head.append(h("th", "Test"), h("th", "Result"), h("th", "STEADI flags when"), h("th", "Flag"),
    h("th", "Change from baseline"));
  table.append(head);
  const yes = Object.entries(latest.key_questions).filter(([, v]) => v).map(([k]) => k);
  const rows = [
    ["Key questions", yes.length ? `yes: ${yes.join(", ")}` : "all no", "any yes", "key_questions", null],
    ["Timed Up and Go", fmt(m.tug_s, " s"), `${latest.cutoffs.tug_s} s or more`, "tug", "tug_s"],
    ["TUG naming animals", fmt(m.dual_tug_s, " s"), "(ours: tracked vs. baseline)", null, null],
    ["Dual-task cost", fmt(m.dual_task_cost_pct, "%"), "(ours: tracked vs. baseline)", null, "dual_task_cost_pct"],
    ["30-second chair stand", fmt(m.chair_stands, " stands"),
      latest.cutoffs.chair_stands ? `under ${latest.cutoffs.chair_stands} (${latest.cutoffs.chair_label})` : "needs age and sex",
      "chair_stand", "chair_stands"],
    ["Balance: feet together", `${fmt(m.feet_together_s, " s")}, sway ${fmt(m.feet_together_sway, " m/s²")}`, "", null, null],
    ["Balance: semi-tandem", `${fmt(m.semi_tandem_s, " s")}, sway ${fmt(m.semi_tandem_sway, " m/s²")}`, "", null, null],
    ["Balance: tandem", `${fmt(m.tandem_s, " s")}, sway ${fmt(m.tandem_sway, " m/s²")}`,
      `under ${latest.cutoffs.tandem_s} s`, "balance", "tandem_s"],
  ];
  for (const [name, value, cutoff, flagId, changeKey] of rows) {
    const tr = h("tr");
    const isFlag = flagId && flagged.has(flagId);
    tr.append(h("td", name), h("td", value), h("td", cutoff), h("td", isFlag ? "FLAG" : "", isFlag ? { class: "flag" } : {}),
      h("td", changeKey ? change(latest, changeKey) : ""));
    table.append(tr);
  }
  box.append(header, table);
}

function lineChart(id, label, dates, values, cutoff, cutoffLabel) {
  charts[id]?.destroy();
  const datasets = [{ label, data: values, spanGaps: true }];
  if (cutoff !== null && cutoff !== undefined) {
    datasets.push({ label: cutoffLabel, data: dates.map(() => cutoff), borderDash: [6, 4], pointRadius: 0 });
  }
  charts[id] = new Chart($(id), { type: "line", data: { labels: dates, datasets }, options: { animation: false } });
}

function renderTrends(t) {
  const s = t.series;
  const c = t.cutoffs;
  lineChart("chart-tug", "Timed Up and Go (s)", t.dates, s.tug_s, c.tug_s, "STEADI cutoff (12 s)");
  lineChart("chart-chair", "Chair stands in 30 s", t.dates, s.chair_stands, c.chair_stands, "STEADI below-average line");
  lineChart("chart-tandem", "Tandem stance (s)", t.dates, s.tandem_s, c.tandem_s, "STEADI cutoff (10 s)");
  lineChart("chart-cost", "Dual-task cost (%)", t.dates, s.dual_task_cost_pct, null, "");
}

function renderExercise(plan, adherence, sessions) {
  const sts = plan.sit_to_stand;
  const bal = plan.balance;
  $("plan").textContent = `Plan: ${sts.sets} sets of ${sts.reps} sit-to-stands; ${bal.holds} supported holds of ` +
    `${bal.target_s} s (${bal.stance.replace("_", " ")}). Why: ${plan.why}. ` +
    `Exercise days in the last 7: ${adherence.last_7_days} of ${adherence.target_days_per_week} planned.`;
  const weeks = adherence.weeks;
  charts.adherence?.destroy();
  charts.adherence = new Chart($("chart-adherence"), {
    type: "bar",
    data: {
      labels: weeks.map((w) => w.week_start),
      datasets: [
        { type: "bar", label: "Exercise days per week", data: weeks.map((w) => w.days) },
        { type: "line", label: "Target", data: weeks.map(() => adherence.target_days_per_week), pointRadius: 0,
          borderDash: [6, 4] },
      ],
    },
    options: { animation: false, scales: { y: { min: 0, max: 7 } } },
  });
  const box = $("sessions");
  box.replaceChildren(h("h3", "Recent sessions"));
  const ul = h("ul");
  for (const e of [...sessions].reverse()) {
    const reps = e.sets.map((s) => s.reps).join(" + ");
    const holds = e.holds.map((x) => `${x.hold_s} s`).join(", ");
    const li = h("li", `${e.date.replace("T", " ")}: sit-to-stands ${reps || "none"}; holds ${holds || "none"} `);
    if (e.simulated) li.append(h("span", "Simulated", { class: "tag" }));
    ul.append(li);
  }
  box.append(ul);
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

function startSession(body) {
  return run(async () => {
    await api("POST", "/api/session", { person_id: personId, ...body });
    say("Press the button when ready.");
  });
}

$("button").onclick = () => {
  audio = audio || new AudioContext(); // browsers only allow sound after a click
  run(() => api("POST", "/api/button"));
};
$("start-checkin").onclick = () => startSession({ mode: "checkin" });
$("start-exercise").onclick = () => startSession({ mode: "exercise" });
$("start-quick").onclick = () => startSession({ mode: "exercise", plan: QUICK_PLAN });
$("arms-used").onclick = () => run(() => api("POST", "/api/stop", { reason: "arms_used" }));
$("cancel").onclick = () => run(() => api("POST", "/api/stop", { reason: "cancel" }));
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
  $("profile-msg").textContent = `Created ${p.name}.`;
  await loadPeople();
});

connect();
run(loadPeople);
