// SheetNest 웹 화면 v2 (실무용). 계산은 worker.js(브라우저 안의 Python)가 하고, 이 파일은 화면만 맡는다.
// 이전 화면(web/)과 계산 결과는 같고, 결론 카드, 실제 크기 환산, 멈추기를 더했다.
import { cutSvg, download, dxf, fmt, partSvg, stripSvg } from "./export.js";
import { TIMING } from "./timing.js";

const $ = (id) => document.getElementById(id);
const el = {
  engine: $("engine"),
  instance: $("instance"),
  instanceNote: $("instance-note"),
  file: $("file"),
  uploadGo: $("upload-go"),
  optWidth: $("opt-width"),
  optRot: $("opt-rot"),
  optUnit: $("opt-unit"),
  summary: $("summary"),
  parts: $("parts"),
  realWidth: $("real-width"),
  realUnit: $("real-unit"),
  methods: $("methods"),
  run: $("run"),
  runRec: $("run-rec"),
  recommend: $("recommend"),
  stop: $("stop"),
  timeLimit: $("time-limit"),
  results: $("results"),
  verdict: $("verdict"),
  theadRow: $("thead-row"),
  tbody: document.querySelector("#table tbody"),
  counters: $("counters"),
  strips: $("strips"),
  play: $("play"),
  step: $("step"),
  stepOut: $("step-out"),
};

const READY_TEXT = ""; // 준비가 끝나면 상태 줄을 숨긴다

const COUNTER_LABELS = {
  overlap_checks: ["정밀 겹침 판정", "회"],
  bbox_rejects: ["박스 단계 제외", "회"],
  columns: ["살펴본 열", "개"],
  lifts: ["겹침 풀기", "회"],
  nfp_computed: ["NFP 계산", "개"],
  nfp_cache_hits: ["NFP 재사용", "회"],
  candidate_evals: ["후보점 판정", "회"],
  grid_checks: ["격자 검사", "회"],
  cell_size: ["격자 한 칸", ""],
};

const METHOD_DESC = {
  trig: "원판을 일정 간격의 세로줄로 나누고, 줄마다 겹치지 않는 가장 낮은 자리를 직접 계산합니다.",
  nfp: "두 조각이 맞닿는 경계(NFP)를 미리 만들어 두고, 점 하나로 겹치는지 판정합니다.",
  raster: "원판을 작은 칸으로 나눠 칸끼리 비교합니다. 계산은 빠르지만 칸 단위라 길이가 조금 길게 나올 수 있습니다.",
};

const GROUP_LABELS = { "실험 인스턴스": "보고서 실험 도면", "기타 벤치마크": "그 밖의 공개 도면" };


// 실제 원판 폭 단위 → cm
const TO_CM = { mm: 0.1, cm: 1, m: 100, in: 2.54 };

// 도면 목록에서 "올린 파일"을 뜻하는 값
const UPLOAD_VALUE = "__upload__";

const state = {
  phase: "init", // init, loading, idle, computing, restarting
  methods: [],
  instances: [],
  inst: null, // { summary, items }
  source: null, // 지금 도면을 다시 불러올 정보 (멈춘 뒤 복구용)
  pendingSource: null,
  uploadSource: null, // 마지막으로 올린 파일 (목록에서 다시 고를 수 있게)
  restoring: false,
  autoReal: false, // 실제 폭 칸을 도면 단위에서 자동으로 채웠는지
  selected: [],
  results: {},
  running: new Set(), // 지금 계산 중인 방법들
  runId: 0,
  runKind: "all", // rec: 추천 방법만, all: 고른 방법 모두
  rec: null, // 계산을 시작할 때의 추천(결과와 견주어 보여 준다)
  limitMs: null, // 시간 제한(ms). 없으면 null
  limitText: "",
  instText: null, // 계산 작업자에게 넘길 도면(팀 공통 JSON)
  step: 0,
  timer: null,
  clock: null,
  t0: 0,
};

const query = new URLSearchParams(location.search);
let worker = null;
startWorker();

function startWorker() {
  worker = new Worker("worker.js");
  worker.onmessage = onMessage;
  worker.onerror = (e) => onError({ during: "init", text: e.message || "계산을 시작하지 못했습니다" });
  worker.postMessage({ type: "init", pyodide: query.get("pyodide") || undefined });
}

function onMessage(ev) {
  const m = ev.data;
  if (m.type === "status") setEngine(m.text);
  else if (m.type === "ready") onReady(m);
  else if (m.type === "instance") onInstance(m.data, m.features);
  else if (m.type === "instanceJson") {
    if (m.purpose === "run") {
      state.instText = m.text;
      const waiting = instTextWaiters;
      instTextWaiters = [];
      for (const f of waiting) f(m.text);
    } else download(`${state.inst.summary.name}_instance.json`, m.text, "application/json");
  } else if (m.type === "error") onError(m);
}

// ---------------------------------------------------------------- 계산 작업자
// 화면 쪽 작업자(worker)는 도면 읽기만 맡고, 계산은 방법마다 따로 띄운 작업자가 동시에 한다.
// 시간 제한을 넘긴 방법은 그 작업자만 끝내면 되므로 다른 방법의 계산과 도면은 그대로 남는다.
const runners = {};
let instTextWaiters = [];

function getInstanceText() {
  if (state.instText) return Promise.resolve(state.instText);
  return new Promise((resolve) => {
    instTextWaiters.push(resolve);
    if (instTextWaiters.length === 1) worker.postMessage({ type: "instanceJson", purpose: "run" });
  });
}

function runner(method) {
  if (runners[method]) return runners[method];
  const w = new Worker("worker.js");
  const r = { worker: w, on: {}, timer: null };
  r.ready = new Promise((resolve, reject) => {
    r.on.ready = resolve;
    r.on.fail = reject;
  });
  w.onmessage = (ev) => onRunnerMessage(method, r, ev.data);
  w.onerror = (e) => onRunnerMessage(method, r, { type: "error", during: "init", text: e.message || "계산을 시작하지 못했습니다" });
  w.postMessage({ type: "init", pyodide: query.get("pyodide") || undefined });
  runners[method] = r;
  return r;
}

function dropRunner(method) {
  const r = runners[method];
  if (!r) return;
  clearTimeout(r.timer);
  r.worker.terminate();
  delete runners[method];
}

function onRunnerMessage(method, r, m) {
  if (m.type === "ready") r.on.ready();
  else if (m.type === "loaded") r.on.loaded && r.on.loaded();
  else if (m.type === "running") {
    // 시간 제한은 작업자 준비와 도면 넣기를 빼고, 실제 계산을 시작한 때부터 잰다
    state.running.add(method);
    if (state.limitMs) r.timer = setTimeout(() => onTimeout(method), state.limitMs);
    renderResults();
  } else if (m.type === "result") {
    clearTimeout(r.timer);
    // 탭이 뒤에 있으면 브라우저가 타이머를 늦게 울릴 수 있다. 제한을 넘겨 끝난 결과는 시간 초과로 센다
    const late = state.limitMs && m.result.status === "ok" && m.result.time_place_ms > state.limitMs;
    finishMethod(method, late ? { method, status: "timeout" } : m.result);
  } else if (m.type === "error") {
    const text = friendly(m.text);
    if (m.during === "init") {
      dropRunner(method);
      r.on.fail(new Error(text));
    } else {
      clearTimeout(r.timer);
      finishMethod(method, { method, status: "error", message: text });
    }
  }
}

async function launch(method, text, params, id) {
  const live = () => id === state.runId && state.phase === "computing" && !state.results[method];
  const r = runner(method);
  try {
    await r.ready;
  } catch (e) {
    if (live()) finishMethod(method, { method, status: "error", message: `계산을 시작하지 못했습니다: ${e.message}` });
    return;
  }
  if (!live()) return;
  await new Promise((resolve) => {
    r.on.loaded = resolve;
    r.worker.postMessage({ type: "loadJson", text });
  });
  if (!live()) return;
  r.worker.postMessage({ type: "run", methods: [method], params: { [method]: params } });
}

function onTimeout(method) {
  if (state.results[method] || state.phase !== "computing") return;
  dropRunner(method);
  finishMethod(method, { method, status: "timeout" });
}

function finishMethod(method, result) {
  state.results[method] = result;
  state.running.delete(method);
  renderResults();
  if (state.phase === "computing" && state.selected.every((n) => state.results[n])) onDone();
}

function setEngine(text, cls = "") {
  el.engine.hidden = !text;
  el.engine.textContent = text;
  el.engine.className = `engine ${cls}`.trim();
}

function setUi() {
  const idle = state.phase === "idle";
  const computing = state.phase === "computing";
  const clock = computing ? `계산 중 ${((performance.now() - state.t0) / 1000).toFixed(1)}초` : "";
  const rec = idle && state.inst ? recommend() : null;
  el.run.disabled = !idle || !state.inst || !checkedMethods().length;
  el.run.textContent = computing && state.runKind === "all" ? clock : "고른 방법 모두 계산해 비교";
  el.runRec.disabled = !rec || !rec.method;
  el.runRec.textContent =
    computing && state.runKind === "rec" ? clock : rec && rec.method ? `추천 방법으로 계산 (${labelOf(rec.method)})` : "추천 방법으로 계산";
  if (idle) renderRecommend(rec);
  el.stop.hidden = !computing;
  el.instance.disabled = !idle;
  el.uploadGo.disabled = !idle || !el.file.files.length;
}

function startClock() {
  state.t0 = performance.now();
  state.clock = setInterval(setUi, 200);
}

function stopClock() {
  if (state.clock) clearInterval(state.clock);
  state.clock = null;
}

// ---------------------------------------------------------------- 준비
function onReady({ methods, instances }) {
  if (state.restoring) {
    setEngine("다시 준비했습니다. 도면을 다시 불러오고 있습니다.");
    reloadSource();
    return;
  }
  state.methods = methods;
  state.instances = instances;
  setEngine(READY_TEXT, "ready");

  const groups = new Map();
  for (const it of instances) {
    if (!groups.has(it.group)) groups.set(it.group, []);
    groups.get(it.group).push(it);
  }
  el.instance.innerHTML = "";
  for (const [group, items] of groups) {
    const og = document.createElement("optgroup");
    og.label = GROUP_LABELS[group] || group;
    for (const it of items) {
      const o = document.createElement("option");
      o.value = it.file;
      const bits = [it.pieces ? `조각 ${it.pieces}개` : "", isSlow(it.name) ? "오래 걸림" : ""].filter(Boolean);
      o.textContent = bits.length ? `${it.name} (${bits.join(", ")})` : it.name;
      og.appendChild(o);
    }
    el.instance.appendChild(og);
  }
  renderMethods();
  if (instances.length) loadBuiltin(instances[0].file);
}

function renderMethods() {
  el.methods.innerHTML = "";
  for (const m of state.methods) {
    const box = document.createElement("div");
    box.className = `method${m.implemented ? "" : " off"}`;
    const id = `m-${m.name}`;
    const stateText = m.implemented ? (m.note ? "오류 있음" : "") : "구현 중";
    box.innerHTML =
      `<label><input type="checkbox" id="${id}" value="${m.name}" ${m.implemented ? "checked" : "disabled"}>` +
      `${m.label}<span class="state">${stateText}</span></label>` +
      (METHOD_DESC[m.name] ? `<p class="desc">${METHOD_DESC[m.name]}</p>` : "") +
      `<p class="eta" data-eta="${m.name}"></p>`;
    for (const p of m.params || []) {
      const row = document.createElement("div");
      row.className = "param";
      row.innerHTML =
        `<label for="p-${m.name}-${p.key}">${p.label}</label>` +
        `<input type="number" id="p-${m.name}-${p.key}" data-method="${m.name}" data-key="${p.key}" ` +
        `min="${p.min ?? ""}" max="${p.max ?? ""}" step="${p.step ?? 1}" placeholder="기본값" ${m.implemented ? "" : "disabled"}>`;
      box.appendChild(row);
    }
    el.methods.appendChild(box);
  }
}
el.methods.addEventListener("change", setUi);
el.methods.addEventListener("input", setUi);

function checkedMethods() {
  return [...el.methods.querySelectorAll('input[type="checkbox"]:checked')].map((c) => c.value);
}

function methodParams() {
  const out = {};
  for (const inp of el.methods.querySelectorAll("input[data-method]")) {
    if (inp.value === "") continue;
    (out[inp.dataset.method] ||= {})[inp.dataset.key] = Number(inp.value);
  }
  return out;
}

const labelOf = (name) => (state.methods.find((m) => m.name === name) || {}).label || name;

// ---------------------------------------------------------------- 도면
function loadBuiltin(file) {
  const entry = state.instances.find((i) => i.file === file);
  const note = entry && entry.note ? entry.note.replace(/^\d+\.\s*/, "") : "";
  el.instanceNote.textContent = [note]
    .filter(Boolean)
    .map((t) => (/[.!?]$/.test(t) ? t : `${t}.`))
    .join(" ");
  state.pendingSource = { kind: "builtin", file };
  state.phase = "loading";
  setUi();
  worker.postMessage({ type: "loadBuiltin", file });
}

function postSource(src) {
  if (src.kind === "builtin") {
    worker.postMessage({ type: "loadBuiltin", file: src.file });
  } else {
    const buffer = src.buffer.slice(0);
    worker.postMessage({ type: "loadUpload", name: src.name, buffer, options: src.options }, [buffer]);
  }
}

function reloadSource() {
  if (state.source) postSource(state.source);
}

function loadUploaded(src) {
  el.instanceNote.textContent = `${src.name} 불러오는 중입니다.`;
  state.pendingSource = src;
  state.phase = "loading";
  setUi();
  postSource(src);
}

// 올린 파일을 도면 목록 맨 위에 보여 주고 고른 상태로 둔다
function markUpload(src) {
  let opt = document.getElementById("opt-upload");
  if (!opt) {
    const og = document.createElement("optgroup");
    og.label = "올린 도면";
    opt = document.createElement("option");
    opt.id = "opt-upload";
    opt.value = UPLOAD_VALUE;
    og.appendChild(opt);
    el.instance.prepend(og);
  }
  opt.textContent = `올린 파일: ${src.name}`;
  el.instance.value = UPLOAD_VALUE;
  state.uploadSource = src;
}

function showSourceInList() {
  const src = state.source;
  if (!src) return;
  el.instance.value = src.kind === "upload" ? UPLOAD_VALUE : src.file;
}

el.instance.addEventListener("change", () => {
  if (el.instance.value === UPLOAD_VALUE) {
    if (state.uploadSource) loadUploaded(state.uploadSource);
    return;
  }
  loadBuiltin(el.instance.value);
});
el.file.addEventListener("change", setUi);
el.uploadGo.addEventListener("click", async () => {
  const f = el.file.files[0];
  if (!f || state.phase !== "idle") return;
  const options = {
    width: el.optWidth.value ? Number(el.optWidth.value) : null,
    rotations: el.optRot.value.split(",").map(Number),
    unit: el.optUnit.value,
  };
  const buffer = await f.arrayBuffer();
  loadUploaded({ kind: "upload", name: f.name, buffer, options });
});

function onInstance(data, features) {
  state.inst = data;
  state.inst.features = features || null;
  state.instText = null;
  if (state.restoring) {
    // 멈춘 뒤 새 실행 환경에 같은 도면을 다시 넣은 경우: 끝난 결과는 그대로 둔다
    state.restoring = false;
    state.phase = "idle";
    setEngine("멈췄습니다. 끝난 방법의 결과는 그대로 두었으니 바로 다시 계산할 수 있습니다.", "ready");
    setUi();
    return;
  }
  state.source = state.pendingSource;
  if (state.source && state.source.kind === "upload") {
    markUpload(state.source);
    el.instanceNote.textContent = "직접 올린 도면입니다.";
  }
  state.results = {};
  state.selected = [];
  el.results.hidden = true;
  setEngine(READY_TEXT, "ready");
  const s = data.summary;
  const unit = s.unit ? ` ${s.unit}` : "";
  el.summary.hidden = false;
  el.summary.innerHTML =
    `<div><b>${s.types}종</b>조각 종류</div>` +
    `<div><b>${s.pieces}개</b>놓을 조각</div>` +
    `<div><b>${fmt(s.width)}${unit}</b>원판 폭 (도면)</div>` +
    `<div><b>${fmt(s.lower_bound)}${unit}</b>이론상 최소 길이</div>`;
  el.parts.innerHTML = data.items
    .map((it) => `<figure>${partSvg(it)}<figcaption>${it.quantity}개</figcaption></figure>`)
    .join("");
  // 도면에 단위가 있으면(예: SVG mm) 실제 폭 칸을 도면 값으로 채운다. 사용자가 직접 적은 값은 건드리지 않는다.
  if (s.unit && TO_CM[s.unit]) {
    if (!el.realWidth.value || state.autoReal) {
      el.realWidth.value = String(Number(s.width.toPrecision(6)));
      el.realUnit.value = s.unit;
      state.autoReal = true;
    }
  } else if (state.autoReal) {
    el.realWidth.value = "";
    state.autoReal = false;
  }
  state.phase = "idle";
  setUi();
}

// 도면 1단위가 실제로 몇 cm인지. 실제 폭을 적지 않았으면 null.
function realScale() {
  const v = Number(el.realWidth.value);
  if (!state.inst || !(v > 0)) return null;
  return (v * TO_CM[el.realUnit.value]) / state.inst.summary.width;
}

function fmtCm(cm) {
  const a = Math.abs(cm);
  if (a >= 100) return `${(Math.round(cm) / 100).toFixed(2)} m`; // 202.5cm → 2.03m (반올림 오차 방지)
  if (a >= 1) return `${cm.toFixed(1)} cm`;
  return `${(cm * 10).toFixed(1)} mm`;
}

// 도면 단위 길이를 화면 글자로: 실제 폭을 적었으면 실제 길이, 아니면 도면 단위
function lenText(v) {
  const k = realScale();
  if (k) return fmtCm(v * k);
  const u = state.inst.summary.unit;
  return `${fmt(v, 5)}${u ? ` ${u}` : ""}`;
}

for (const input of [el.realWidth, el.realUnit]) {
  input.addEventListener("input", () => {
    state.autoReal = false;
    if (!el.results.hidden) renderResults();
  });
}

// ---------------------------------------------------------------- 실행
// ---------------------------------------------------------------- 계산 전 예상 시간과 추천
// 길이는 예측식이 없다. 지금까지 잰 결과에서 NFP가 가장 짧은 경우가 대부분이었고(실제 도면 13개 중 12개, 복제 입력 27개 중 23개),
// 예외는 대개 삼각법이어서, 시간 안에 끝날 것으로 예상되는 방법 중 NFP, 삼각법, 래스터 순으로 추천한다.
const LENGTH_ORDER = ["nfp", "trig", "raster"];
const MARGIN = { builtin: 1.3, upload: 3 }; // 예상 시간에 곱하는 여유. 올린 도면은 어림값이라 넉넉히 둔다

const builtinName = () => (state.instances.find((i) => i.file === (state.source || {}).file) || {}).name;

// 브라우저에서 걸릴 예상 시간(초). 알 수 없으면 undefined, 잰 상한(6분)을 넘겼으면 Infinity
function expectedSeconds(method) {
  if (!state.inst || !state.source) return undefined;
  if ((methodParams()[method] || {}).rows) return undefined; // 설정값을 바꾸면 미리 잰 값과 달라진다
  if (state.source.kind === "builtin") {
    const row = TIMING.table[builtinName()];
    if (!row || !(method in row)) return undefined;
    return row[method] === null ? Infinity : row[method] * TIMING.factor;
  }
  const f = state.inst.features;
  const k = TIMING.model[method];
  if (!f || !k || !f.S) return undefined;
  if (k.sOver && f.S >= k.sOver) return Infinity; // 이만큼 복잡한 도면은 실험 3에서 모두 10분을 넘겼다
  const s = state.inst.summary;
  return Math.exp(k.a + k.n * Math.log(s.pieces) + k.s * Math.log(f.S) + k.t * Math.log(s.types)) * TIMING.factor;
}

const tableLimitSeconds = () => Math.round((TIMING.capSeconds * TIMING.factor) / 60) * 60; // 표가 답할 수 있는 가장 긴 시간(약 10분)

function isSlow(name) {
  const row = TIMING.table[name];
  return !!row && Object.values(row).some((s) => s === null || s * TIMING.factor > 60);
}

function etaText(t) {
  if (t === undefined) return "";
  if (t === Infinity) return `${Math.round(tableLimitSeconds() / 60)}분 이상`;
  if (t < 1) return "1초 미만";
  if (t < 60) return `약 ${t < 10 ? Number(t.toPrecision(2)) : Math.round(t)}초`;
  const min = Math.floor(t / 60);
  const sec = Math.round((t - min * 60) / 10) * 10;
  return sec === 60 ? `약 ${min + 1}분` : sec ? `약 ${min}분 ${sec}초` : `약 ${min}분`;
}

function recommend() {
  const p = priority();
  const limit = p === "limit" ? Number(el.timeLimit.value) / 1000 : Infinity;
  const limitText = p === "limit" ? el.timeLimit.selectedOptions[0].textContent : "";
  const margin = MARGIN[(state.source || {}).kind] || MARGIN.upload;
  const names = state.methods.filter((m) => m.implemented).map((m) => m.name);
  const exp = Object.fromEntries(names.map((n) => [n, expectedSeconds(n)]));
  const known = names.filter((n) => exp[n] !== undefined);
  const fits = (n, lim = limit) => exp[n] !== undefined && exp[n] !== Infinity && exp[n] * margin <= lim;
  let method = null;
  if (p === "speed") {
    method = known.filter((n) => exp[n] !== Infinity).sort((x, y) => exp[x] - exp[y])[0] || null;
  } else {
    method = LENGTH_ORDER.find((n) => names.includes(n) && fits(n)) || null;
  }
  return { p, limit, limitText, exp, names, known, method, fits };
}

function renderRecommend(rec) {
  for (const node of el.methods.querySelectorAll("[data-eta]")) {
    const n = node.dataset.eta;
    const t = rec ? rec.exp[n] : undefined;
    const over = rec && t !== undefined && rec.p !== "speed" && !rec.fits(n);
    node.className = over ? "eta over" : "eta";
    node.innerHTML = t === undefined ? "" : `예상 시간 <b>${etaText(t)}</b>${over ? (rec.p === "limit" ? " · 시간 초과 예상" : " · 얼마나 걸릴지 모름") : ""}`;
  }
  if (!rec) return;
  el.recommend.hidden = false;
  const src =
    (state.source || {}).kind === "builtin"
      ? "예상 시간은 이 도면을 미리 재어 둔 값으로 계산했습니다."
      : "예상 시간은 조각 수와 모양 복잡도로 어림한 값이라 실제와 2~3배 다를 수 있습니다.";
  if (!rec.known.length) {
    el.recommend.innerHTML =
      `<p class="r-head"><span>추천</span>없음</p>` +
      `<p>${Object.keys(methodParams()).length ? "방법 설정값을 바꾸면 미리 잰 시간과 달라져서" : "이 도면은 예상 시간을 알 수 없어서"} 추천하지 않습니다. 고른 방법을 모두 계산해 비교하면 됩니다.</p>`;
    return;
  }
  const L = (n) => labelOf(n);
  const eta = (n) => etaText(rec.exp[n]);
  let head = "";
  let why = "";
  if (rec.p === "speed") {
    head = L(rec.method);
    why = `가장 빨리 끝날 것으로 예상됩니다(${eta(rec.method)}).${rec.method === "nfp" ? "" : " 원판 길이는 NFP보다 길게 나올 수 있습니다."}`;
  } else if (!rec.method) {
    head = "없음";
    why = `${rec.limitText} 안에 끝날 것으로 예상되는 방법이 없습니다. 시간 제한을 늘리면 추천할 수 있습니다.`;
  } else {
    head = L(rec.method);
    const within = rec.p === "limit" ? `${rec.limitText} 안에 끝날 것으로 예상되고(${eta(rec.method)})` : `${eta(rec.method)} 걸릴 것으로 예상되고`;
    const skipped = LENGTH_ORDER.slice(0, LENGTH_ORDER.indexOf(rec.method)).filter((n) => rec.names.includes(n));
    const skipText = skipped.length
      ? `${skipped.map((n) => `${L(n)}${josa(L(n), "은", "는")} ${rec.exp[n] === undefined ? "예상 시간을 몰라" : `${eta(n)} 걸릴 것으로 예상되어`}`).join(", ")} 뺐습니다. `
      : "";
    why =
      rec.method === "nfp"
        ? `${within}, 지금까지 잰 도면 대부분에서 NFP가 가장 짧았습니다.`
        : `${skipText}${L(rec.method)}${josa(L(rec.method), "은", "는")} ${within}, 남은 방법 중에서는 대체로 가장 짧습니다.`;
    // 시간 제한을 늘리면 더 앞 순서의 방법을 추천할 수 있는지
    if (rec.p === "limit") {
      for (const o of [...el.timeLimit.options].filter((o) => Number(o.value) / 1000 > rec.limit)) {
        const better = LENGTH_ORDER.find((n) => rec.names.includes(n) && rec.fits(n, Number(o.value) / 1000));
        if (better && better !== rec.method) {
          why += ` 시간 제한을 ${o.textContent}으로 늘리면 ${L(better)}(${eta(better)})${josa(L(better), "을", "를")} 추천합니다.`;
          break;
        }
      }
    }
  }
  el.recommend.innerHTML = `<p class="r-head"><span>추천</span>${head}</p><p>${why}</p><p class="r-src">${src}</p>`;
}

// 우선순위. 자재 절약 우선은 시간 제한 없이, 시간 제한 안에서 자재 절약은 정한 시간까지만 돌린다.
// 계산 속도 우선은 가장 빨리 끝날 것으로 예상되는 방법을 추천한다.
// 시간 제한 선택지(1초, 10초, 1분, 10분)는 실험 3의 제한 시간 T와 같다(experiments/README.md).
function priority() {
  const c = document.querySelector('input[name="priority"]:checked');
  return c ? c.value : "limit";
}

el.timeLimit.addEventListener("change", () => {
  document.querySelector('input[name="priority"][value="limit"]').checked = true;
  setUi();
});
$("priority").addEventListener("change", setUi);

el.run.addEventListener("click", () => startRun(checkedMethods(), "all"));
el.runRec.addEventListener("click", () => {
  const rec = recommend();
  if (rec.method) startRun([rec.method], "rec");
});

function startRun(methods, kind) {
  const p = priority();
  if (!methods.length || !state.inst || state.phase !== "idle") return;
  stopPlay();
  const id = ++state.runId;
  state.runKind = kind;
  state.rec = recommend();
  state.selected = methods;
  state.results = {};
  state.running = new Set();
  state.limitMs = p === "limit" ? Number(el.timeLimit.value) : null;
  state.limitText = p === "limit" ? el.timeLimit.selectedOptions[0].textContent : "";
  state.step = state.inst.summary.pieces;
  el.results.hidden = false;
  state.phase = "computing";
  startClock();
  setUi();
  renderResults();
  const params = methodParams();
  getInstanceText().then((text) => {
    if (id !== state.runId || state.phase !== "computing") return;
    for (const m of methods) launch(m, text, params[m] || {}, id);
  });
}

el.stop.addEventListener("click", () => {
  if (state.phase !== "computing") return;
  // Python 계산은 중간에 끊을 수 없어서 아직 계산 중인 방법의 작업자를 통째로 끝낸다(다음 계산 때 새로 띄운다)
  state.runId++;
  for (const n of state.selected) {
    if (state.results[n]) continue;
    dropRunner(n);
    state.results[n] = { method: n, status: "stopped" };
  }
  onDone();
  setEngine("멈췄습니다. 끝난 방법의 결과는 그대로 두었으니 바로 다시 계산할 수 있습니다.", "ready");
});

function onDone() {
  stopClock();
  state.running = new Set();
  state.phase = "idle";
  setUi();
  renderResults();
  el.results.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });
}

// 계산 코드(web/bridge.py)가 보내는 안내문을 이 화면의 말투로 바꾼다. bridge.py는 이전 화면과 같이 써서 고치지 않는다.
const FRIENDLY_ERRORS = [
  [/^JSON 형식이 아닙니다\. 팀 공통 instance JSON이나 sparrow JSON 파일인지 확인하세요\.$/, "JSON 형식이 아닙니다. 팀 공통 instance JSON이나 sparrow JSON 파일을 올리면 됩니다."],
  [/^원판 폭을 알 수 없습니다\. 원판 폭 칸에 값을 적고 다시 불러오세요\.$/, "원판 폭을 찾지 못했습니다. 원판 폭 칸에 값을 적고 다시 불러오면 됩니다."],
  [/^지원하지 않는 파일 형식: (\S*) \(JSON, DXF, SVG, XML만 가능\)$/, "이 파일 형식($1)은 읽을 수 없습니다. JSON, DXF, SVG, XML 파일만 올릴 수 있습니다."],
  [/^형식 검사 실패: /, "도면 내용에 문제가 있습니다: "],
];

function friendly(text) {
  let t = String(text ?? "");
  for (const [re, to] of FRIENDLY_ERRORS) t = t.replace(re, to);
  return t;
}

function onError({ during, text: raw }) {
  const text = friendly(raw);
  if (during === "init") {
    stopClock();
    state.restoring = false;
    state.phase = "init";
    setEngine(`계산 준비를 하지 못했습니다. 인터넷 연결을 확인한 뒤 새로 고침하면 다시 준비합니다. (${text})`, "fail");
    setUi();
    return;
  }
  setEngine(`${during === "run" ? "계산" : "도면 읽기"} 중에 문제가 생겼습니다: ${text}`, "fail");
  if (during === "run") {
    for (const n of state.selected) if (!state.results[n]) state.results[n] = { method: n, status: "error", message: text };
    renderResults();
  } else if (state.inst && !state.restoring) {
    el.instanceNote.textContent = `이 파일은 불러오지 못했습니다. 지금 도면(${state.inst.summary.name})은 그대로입니다.`;
    showSourceInList();
  }
  state.restoring = false;
  state.phase = state.inst ? "idle" : "init";
  setUi();
}

// ---------------------------------------------------------------- 결과 화면
const isValid = (r) => r.valid && !(r.rule_errors || []).length;

function okResults() {
  return state.selected.map((n) => state.results[n]).filter((r) => r && r.status === "ok");
}

function renderResults() {
  if (!state.inst) return;
  renderVerdict();
  renderTable();
  renderCounters();
  el.step.max = String(state.inst.summary.pieces);
  el.step.value = String(state.step);
  renderStrips();
}

// 길이가 같으면(오차 안) 빠른 쪽을 앞에 둔다
function byLength(a, b) {
  const eps = 1e-9 * Math.max(1, state.inst.summary.width);
  return Math.abs(a.length - b.length) <= eps ? a.time_place_ms - b.time_place_ms : a.length - b.length;
}

// 표와 배치 그림의 순서: 검사를 통과한 결과를 짧은 순으로, 그다음 검사 실패, 그다음 아직 없는 결과(고른 순서)
function shortestFirst() {
  const group = (n) => {
    const r = state.results[n];
    return !r || r.status !== "ok" ? 2 : isValid(r) ? 0 : 1;
  };
  return state.selected
    .map((n, i) => [n, i])
    .sort(([a, i], [b, j]) => group(a) - group(b) || (group(a) < 2 ? byLength(state.results[a], state.results[b]) : 0) || i - j)
    .map(([n]) => n);
}

// 길이가 서로 다를 때 가장 짧은 방법 이름 (같거나 하나뿐이면 null)
function shortestName() {
  const valid = okResults().filter(isValid);
  if (valid.length < 2) return null;
  const eps = 1e-9 * Math.max(1, state.inst.summary.width);
  const sorted = [...valid].sort(byLength);
  return sorted[sorted.length - 1].length - sorted[0].length > eps ? sorted[0].method : null;
}

// 받침이 있으면 앞의 조사, 없으면 뒤의 조사. 한글이 아닌 끝(예: NFP)은 받침이 없는 것으로 본다
function josa(word, withFinal, withoutFinal) {
  const c = String(word).charCodeAt(String(word).length - 1);
  return c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 ? withFinal : withoutFinal;
}

function renderVerdict() {
  const s = state.inst.summary;
  const oks = okResults();
  const timed = state.selected.filter((n) => state.results[n] && state.results[n].status === "timeout");
  if (!oks.length) {
    el.verdict.innerHTML =
      state.phase === "computing"
        ? `<p class="v-wait">계산 중입니다. 첫 결과가 나오면 여기에 가장 짧은 배치를 보여 드리겠습니다.</p>`
        : timed.length
          ? `<p class="v-wait">${
              state.runKind === "rec" && state.rec && state.rec.method
                ? `추천한 ${labelOf(state.rec.method)}${josa(labelOf(state.rec.method), "이", "가")} 예상(${etaText(state.rec.exp[state.rec.method])})과 달리 ${state.limitText} 안에 끝나지 않았습니다.`
                : `${state.limitText} 안에 끝난 방법이 없습니다.`
            } 시간 제한을 늘려서 다시 계산하면 됩니다.</p>`
          : `<p class="v-wait">보여 드릴 결과가 없습니다. 아래 표에서 이유를 확인할 수 있습니다.</p>`;
    return;
  }
  const valid = oks.filter(isValid);
  const pool = [...(valid.length ? valid : oks)].sort(byLength);
  const best = pool[0];
  const eps = 1e-9 * Math.max(1, s.width);
  const k = realScale();
  const unit = s.unit ? ` ${s.unit}` : "";
  const lenOf = (r) => (k ? fmtCm(r.length * k) : `${fmt(r.length, 6)}${unit}`);
  const diffOf = (d) => (k ? fmtCm(d * k) : `${fmt(d, 4)} (${((d / best.length) * 100).toFixed(1)}%)`);

  const many = pool.length > 1;
  const longest = pool[pool.length - 1];
  const allSame = many && longest.length - best.length <= eps;
  const within = timed.length ? `${state.limitText} 안에 끝난 방법 중 ` : "";
  const win = !many
    ? timed.length
      ? `<p class="v-win"><b>${labelOf(best.method)}</b> 배치만 ${state.limitText} 안에 끝났습니다</p>`
      : `<p class="v-win"><b>${labelOf(best.method)}</b> 배치 결과입니다</p>`
    : allSame
      ? `<p class="v-win">${within}계산한 방법의 길이가 모두 같습니다</p>`
      : `<p class="v-win"><b>${labelOf(best.method)}</b> 배치가 ${within}가장 짧습니다</p>`;
  const basis = k
    ? `실제 원판 폭 ${fmt(Number(el.realWidth.value), 6)} ${el.realUnit.value} 기준`
    : `원판 폭 ${fmt(s.width)}의 ${(best.length / s.width).toFixed(2)}배입니다. 실제 원판 폭을 적으면 m 단위로 바꿔 드립니다.`;

  const lb = s.lower_bound;
  const minPct = Math.min(100, (lb / best.length) * 100);
  const tape =
    `<div class="tape" role="img" aria-label="이론상 최소 ${lenText(lb)}, 더 쓴 길이 ${lenText(best.length - lb)}">` +
    `<span class="min" style="width:${minPct}%"></span><span class="extra" style="width:${100 - minPct}%"></span></div>` +
    `<div class="tape-labels"><span>이론상 최소 ${lenText(lb)}</span><span>더 쓴 길이 ${lenText(best.length - lb)}</span></div>`;

  const stats =
    `<dl class="v-stats">` +
    `<div><dt>버려지는 부분</dt><dd>${((1 - best.utilization) * 100).toFixed(1)}%</dd></div>` +
    `<div><dt>이론상 최소보다</dt><dd>+${(best.over_lower_bound * 100).toFixed(1)}%</dd></div>` +
    `</dl>`;

  // 방법별 길이를 짧은 순으로. 검사를 통과하지 못한 결과는 맨 뒤에 따로 표시
  let rank = "";
  if (oks.length + timed.length > 1) {
    const failed = oks.filter((r) => !pool.includes(r));
    const items = pool.map((r) => {
      const d = r.length - best.length;
      const top = d <= eps;
      const tag = top ? (allSame ? "같음" : "가장 짧음") : `+${diffOf(d)}`;
      return `<li${top ? ' class="is-best"' : ""}><span class="r-name">${labelOf(r.method)}</span><span class="r-len">${lenOf(r)}</span><span class="r-diff">${tag}</span></li>`;
    });
    for (const r of failed) {
      items.push(`<li class="fail"><span class="r-name">${labelOf(r.method)}</span><span class="r-len">${lenOf(r)}</span><span class="r-diff">검사 실패</span></li>`);
    }
    for (const n of timed) {
      items.push(`<li class="fail"><span class="r-name">${labelOf(n)}</span><span class="r-len">없음</span><span class="r-diff">시간 초과</span></li>`);
    }
    rank = `<p class="v-sub">방법별 원판 길이 (짧은 순)</p><ol class="v-rank">${items.join("")}</ol>`;
  }

  // 계산 전 추천과 실제 결과를 견준다. 다르면 그대로 알려 준다
  const rec = state.rec;
  const pct = (longer) => (((longer.length - best.length) / longer.length) * 100).toFixed(1);
  let recNote = "";
  if (state.runKind === "rec") {
    recNote = `<p class="v-note">추천 방법만 계산했습니다. 추천이 맞는지 확인하려면 "고른 방법 모두 계산해 비교"를 누르면 됩니다.</p>`;
  } else if (state.phase !== "computing" && rec && rec.method && state.selected.length > 1 && state.selected.includes(rec.method)) {
    const R = labelOf(rec.method);
    const rr = state.results[rec.method];
    if (rr.status === "timeout") {
      recNote = `<p class="v-diff">추천한 ${R}${josa(R, "은", "는")} 예상(${etaText(rec.exp[rec.method])})과 달리 ${state.limitText} 안에 끝나지 않았습니다.</p>`;
    } else if (rr.status === "ok" && rec.p === "speed") {
      const fastest = [...pool].sort((x, y) => x.time_place_ms - y.time_place_ms)[0];
      const F = labelOf(fastest.method);
      recNote =
        fastest.method === rec.method
          ? `<p class="v-note">가장 빠를 것으로 추천한 ${R}${josa(R, "이", "가")} 실제로도 가장 빨랐습니다.</p>`
          : `<p class="v-diff">추천은 ${R}${josa(R, "이었", "였")}지만, 실제로는 ${F}${josa(F, "이", "가")} 가장 빨랐습니다.</p>`;
    } else if (rr.status === "ok") {
      const B = labelOf(best.method);
      recNote =
        rr.length - best.length <= eps
          ? `<p class="v-note">추천한 ${R}${josa(R, "이", "가")} 실제로도 가장 짧았습니다.</p>`
          : `<p class="v-diff">추천은 ${R}${josa(R, "이었", "였")}지만, 이번에는 ${B}${josa(B, "이", "가")} ${R}보다 <b>${pct(rr)}%</b> 짧았습니다.</p>`;
    }
  } else if (state.phase !== "computing") {
    // 추천이 없을 때(예상 시간을 모름): NFP가 대개 가장 짧다는 사실과 다르면 알려 준다
    const nfp = pool.find((r) => r.method === "nfp");
    if (nfp && nfp.length - best.length > eps) {
      const B = labelOf(best.method);
      recNote = `<p class="v-diff">보통은 NFP가 가장 짧지만, 이번에는 ${B}${josa(B, "이", "가")} NFP보다 <b>${pct(nfp)}%</b> 짧았습니다.</p>`;
    }
  }
  const timeoutNote = timed.length
    ? `<p class="v-note">${timed.map(labelOf).join(", ")}${josa(labelOf(timed[timed.length - 1]), "은", "는")} ${state.limitText} 안에 끝나지 않아 후보에서 뺐습니다. 시간 제한을 늘리면 더 짧은 배치가 나올 수 있습니다.</p>`
    : "";

  const save =
    k && many && !allSame
      ? `<p class="v-diff">같은 작업을 100번 하면 ${labelOf(longest.method)} 배치보다 원판을 <b>${fmtCm((longest.length - best.length) * k * 100)}</b> 덜 씁니다.</p>`
      : "";

  const bad = oks.filter((r) => !isValid(r));
  const check = bad.length
    ? `<p class="v-check bad">${bad.map((r) => labelOf(r.method)).join(", ")} 배치가 검사를 통과하지 못했습니다: ` +
      `${escapeHtml([...bad[0].valid_errors, ...bad[0].rule_errors][0] || "")}</p>`
    : `<p class="v-check ok">겹친 조각도, 원판 밖으로 나간 조각도 없습니다. ` +
      `${oks.length > 1 ? `${oks.length}개 방법 모두 개수와 순서까지 확인했습니다.` : "개수와 순서도 맞습니다."}</p>`;

  const pending = state.phase === "computing" ? `<p class="v-note">아직 계산 중인 방법이 있어서 가장 짧은 배치가 바뀔 수 있습니다.</p>` : "";
  const actions =
    `<div class="v-actions"><span>${many && !allSame ? "가장 짧은 배치" : "이 배치"} 내려받기${k ? " (실제 크기, mm)" : " (도면 단위)"}</span>` +
    `<button type="button" class="quiet" data-act="svg" data-m="${best.method}">커터용 SVG</button>` +
    `<button type="button" class="quiet" data-act="dxf" data-m="${best.method}">DXF</button></div>`;

  el.verdict.innerHTML =
    `<div class="v-head">${win}<p class="v-label">필요한 원판 길이</p><p class="v-big">${lenOf(best)}</p><p class="v-basis">${basis}</p></div>` +
    `<div class="v-body">${tape}${stats}${rank}${recNote}${save}${timeoutNote}${check}${pending}${actions}</div>`;
}

function renderHead(k) {
  const cols = ["방법", "원판 길이", ...(k ? ["실제 길이"] : []), "원판 사용률", "이론상 최소보다", "전체 시간", "가능 위치 계산이 차지한 시간"];
  el.theadRow.innerHTML = cols
    .map((c, i) => `<th scope="col"${i === cols.length - 1 ? ' class="bar-col"' : ""}>${c}</th>`)
    .join("");
  return cols.length;
}

function statusText(name, r) {
  if (!r) return state.running.has(name) ? "계산 중" : state.phase === "computing" ? "계산 준비 중" : "";
  if (r.status === "stopped") return "멈춰서 계산하지 않았습니다";
  if (r.status === "timeout") return `시간 초과: ${state.limitText} 안에 끝나지 않아 멈췄습니다`;
  if (r.status === "not_implemented") return "아직 만드는 중인 방법입니다";
  return `문제가 생겼습니다: ${escapeHtml(r.message)}`;
}

function renderTable() {
  const k = realScale();
  const ncol = renderHead(k);
  const oks = okResults();
  const win = shortestName(); // 길이가 서로 다를 때만 가장 짧은 행을 표시
  const maxTime = Math.max(...oks.map((r) => r.time_place_ms), 1e-9);
  const unit = state.inst.summary.unit ? ` ${state.inst.summary.unit}` : "";
  el.tbody.innerHTML = shortestFirst()
    .map((name) => {
      const r = state.results[name];
      const label = labelOf(name);
      if (!r || r.status !== "ok") {
        return `<tr><td class="name">${label}</td><td colspan="${ncol - 1}" class="muted" style="text-align:left">${statusText(name, r)}</td></tr>`;
      }
      const core = (r.time_feasible_ms / maxTime) * 100;
      const rest = ((r.time_place_ms - r.time_feasible_ms) / maxTime) * 100;
      const why = [...r.valid_errors, ...r.rule_errors].join("\n");
      const flag = isValid(r) ? "" : ` <span class="badge bad" title="${escapeHtml(why)}">검사 실패</span>`;
      const best = name === win ? "best" : "";
      const tag = best ? ` <span class="badge win">가장 짧음</span>` : "";
      return (
        `<tr${best ? ' class="best-row"' : ""}><td class="name">${label}${tag}${flag}</td>` +
        `<td class="${best}">${fmt(r.length, 6)}${unit}</td>` +
        (k ? `<td class="${best}">${fmtCm(r.length * k)}</td>` : "") +
        `<td>${(r.utilization * 100).toFixed(1)}%</td>` +
        `<td>+${(r.over_lower_bound * 100).toFixed(1)}%</td>` +
        `<td>${fmtMs(r.time_place_ms)}</td>` +
        `<td class="bar-col"><div class="bar"><div class="track"><div class="core" style="width:${core}%"></div>` +
        `<div class="rest" style="width:${rest}%"></div></div>` +
        `<span class="pct">${(r.feasible_ratio * 100).toFixed(1)}%</span></div></td></tr>`
      );
    })
    .join("");
}

function renderCounters() {
  const oks = okResults();
  el.counters.innerHTML = oks.length
    ? `<table class="mini"><tbody>${oks
        .map((r) => `<tr><th scope="row">${labelOf(r.method)}</th><td>${counterText(r.counters)}</td></tr>`)
        .join("")}</tbody></table>`
    : "";
}

function counterText(counters) {
  return Object.entries(counters)
    .filter(([key, v]) => !(key === "bbox_rejects" && v === 0))
    .map(([key, v]) => {
      const [label, suffix] = COUNTER_LABELS[key] || [key, ""];
      const val = typeof v === "number" ? (Number.isInteger(v) ? v.toLocaleString("ko-KR") : fmt(v)) : v;
      return `${label} ${val}${suffix}`;
    })
    .join(", ");
}

function fmtMs(ms) {
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}초` : `${ms.toFixed(ms < 10 ? 1 : 0)}ms`;
}

function renderStrips() {
  const s = state.inst.summary;
  const oks = okResults();
  const k = realScale();
  const scaleLength = Math.max(...oks.map((r) => r.length), s.lower_bound);
  el.stepOut.textContent = `${state.step} / ${s.pieces}개`;
  el.strips.innerHTML = "";
  const win = shortestName();
  for (const name of shortestFirst()) {
    const r = state.results[name];
    const label = labelOf(name);
    const card = document.createElement("article");
    card.className = name === win ? "strip best" : "strip";
    if (!r) {
      const txt = state.running.has(name) ? "계산 중입니다." : state.phase === "computing" ? "계산을 준비하고 있습니다." : "";
      card.innerHTML = `<header><h4>${label}</h4></header><p class="msg">${txt}</p>`;
    } else if (r.status === "timeout") {
      card.innerHTML = `<header><h4>${label}</h4></header><p class="msg">시간 초과: ${state.limitText} 안에 끝나지 않아 멈췄습니다.</p>`;
    } else if (r.status === "stopped") {
      card.innerHTML = `<header><h4>${label}</h4></header><p class="msg">멈춰서 계산하지 않았습니다.</p>`;
    } else if (r.status === "not_implemented") {
      card.innerHTML = `<header><h4>${label}</h4></header><p class="msg">아직 만드는 중인 방법입니다. 코드가 합쳐지면 이 자리에 결과가 나옵니다.</p>`;
    } else if (r.status !== "ok") {
      card.innerHTML = `<header><h4>${label}</h4></header><p class="msg err">${escapeHtml(r.message)}\n${escapeHtml(r.trace || "")}</p>`;
    } else {
      card.innerHTML =
        `<header><h4>${label}${name === win ? ` <span class="badge win">가장 짧음</span>` : ""}</h4>` +
        `<span class="nums">길이 ${fmt(r.length, 6)}${k ? ` (${fmtCm(r.length * k)})` : ""}, 사용률 ${(r.utilization * 100).toFixed(1)}%</span>` +
        `<span class="tools">` +
        `<button type="button" class="quiet" data-act="svg" data-m="${name}">커터용 SVG</button>` +
        `<button type="button" class="quiet" data-act="dxf" data-m="${name}">DXF</button>` +
        `<button type="button" class="quiet" data-act="json" data-m="${name}">결과 JSON</button>` +
        `</span></header>` +
        `<div class="canvas">${stripSvg(r, s.width, { scaleLength, upto: state.step, lowerBound: s.lower_bound })}</div>`;
    }
    el.strips.appendChild(card);
  }
}

// 결론 카드와 배치 그림의 내려받기 단추
function onDownload(ev) {
  const b = ev.target.closest("button[data-act]");
  if (!b) return;
  const r = state.results[b.dataset.m];
  const s = state.inst.summary;
  const k = realScale();
  const base = `${s.name}_${r.method}`;
  if (b.dataset.act === "svg") {
    if (k) download(`${base}_mm.svg`, cutSvg(r, s.width, "mm", k * 10), "image/svg+xml");
    else download(`${base}.svg`, cutSvg(r, s.width, s.unit), "image/svg+xml");
  } else if (b.dataset.act === "dxf") {
    if (k) download(`${base}_mm.dxf`, dxf(r, s.width, k * 10, "mm"), "application/dxf");
    else download(`${base}.dxf`, dxf(r, s.width), "application/dxf");
  } else {
    download(`${base}_solution.json`, JSON.stringify(r.solution, null, 1), "application/json");
  }
}
el.strips.addEventListener("click", onDownload);
el.verdict.addEventListener("click", onDownload);

// ---------------------------------------------------------------- 놓는 순서 재생
el.step.addEventListener("input", () => {
  stopPlay();
  state.step = Number(el.step.value);
  renderStrips();
});

el.play.addEventListener("click", () => {
  if (state.timer) return stopPlay();
  const n = state.inst.summary.pieces;
  if (prefersReducedMotion()) {
    state.step = n;
    el.step.value = String(n);
    return renderStrips();
  }
  state.step = 0;
  el.play.textContent = "멈춤";
  const interval = Math.max(40, Math.min(250, 8000 / n));
  state.timer = setInterval(() => {
    state.step += 1;
    el.step.value = String(state.step);
    renderStrips();
    if (state.step >= n) stopPlay();
  }, interval);
});

function stopPlay() {
  if (state.timer) clearInterval(state.timer);
  state.timer = null;
  el.play.textContent = "놓는 순서 재생";
}

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}
