// SheetNest 웹 화면 v2 (실무용). 계산은 worker.js(브라우저 안의 Python)가 하고, 이 파일은 화면만 맡는다.
// 이전 화면(web/)과 계산 결과는 같고, 결론 카드, 실제 크기 환산, 멈추기를 더했다.
import { cutSvg, download, dxf, fmt, partSvg, stripSvg } from "./export.js";

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
  stop: $("stop"),
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
  trig: "원판을 일정 간격의 세로줄로 나누고, 줄마다 겹치지 않는 가장 낮은 자리를 직접 계산해요.",
  nfp: "두 조각이 맞닿는 경계(NFP)를 미리 만들어 두고, 점 하나로 빠르게 판정해요.",
  raster: "원판을 작은 칸으로 나눠 칸끼리 비교해요. 빠르지만 칸 단위라 조금 덜 촘촘해요.",
};

const GROUP_LABELS = { "실험 인스턴스": "보고서 실험 도면", "기타 벤치마크": "그 밖의 공개 도면" };

// 꼭짓점이 150~1000개라 브라우저에서 몇 분 이상 걸리는 도면
const SLOW = new Set(["gardeyn2", "gardeyn3", "gardeyn4", "gardeyn5", "gardeyn6", "gardeyn7", "gardeyn8", "gardeyn9"]);
// 방법에 따라 오래 걸리는 도면과 브라우저에서 걸리는 대략의 시간 (2026-11-25 측정, rows 기본값)
const SLOW_METHOD = { gardeyn1: { nfp: "10분 이상", trig: "약 2분" } };

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
  running: null,
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
  worker.onerror = (e) => onError({ during: "init", text: e.message || "계산을 시작하지 못했어요" });
  worker.postMessage({ type: "init", pyodide: query.get("pyodide") || undefined });
}

function onMessage(ev) {
  const m = ev.data;
  if (m.type === "status") setEngine(m.text);
  else if (m.type === "ready") onReady(m);
  else if (m.type === "instance") onInstance(m.data);
  else if (m.type === "running") {
    state.running = m.method;
    renderResults();
  } else if (m.type === "result") {
    state.results[m.result.method] = m.result;
    state.running = null;
    renderResults();
  } else if (m.type === "done") onDone();
  else if (m.type === "instanceJson") {
    download(`${state.inst.summary.name}_instance.json`, m.text, "application/json");
  } else if (m.type === "error") onError(m);
}

function setEngine(text, cls = "") {
  el.engine.hidden = !text;
  el.engine.textContent = text;
  el.engine.className = `engine ${cls}`.trim();
}

function setUi() {
  const idle = state.phase === "idle";
  const computing = state.phase === "computing";
  el.run.disabled = !idle || !state.inst || !checkedMethods().length;
  el.run.textContent = computing ? `계산 중 ${((performance.now() - state.t0) / 1000).toFixed(1)}초` : "배치 계산";
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
    setEngine("다시 준비했어요. 도면을 다시 불러오고 있어요.");
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
      const bits = [it.pieces ? `조각 ${it.pieces}개` : "", SLOW.has(it.name) || SLOW_METHOD[it.name] ? "오래 걸림" : ""].filter(Boolean);
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
      (METHOD_DESC[m.name] ? `<p class="desc">${METHOD_DESC[m.name]}</p>` : "");
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
  const slow =
    entry && SLOW.has(entry.name)
      ? "꼭짓점이 많은 도면이라 브라우저에서 몇 분 넘게 걸릴 수 있어요. 계산 중에 멈추기를 누르면 바로 멈춰요."
      : "";
  const slowM = entry && SLOW_METHOD[entry.name]
    ? `이 도면은 브라우저에서 ${Object.entries(SLOW_METHOD[entry.name])
        .map(([m, t]) => `${labelOf(m)} ${t}`)
        .join(", ")}이 걸려요. 빨리 보려면 그 방법의 체크를 꺼 주세요.`
    : "";
  el.instanceNote.textContent = [note, slow, slowM]
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
  el.instanceNote.textContent = `${src.name} 불러오는 중이에요.`;
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

function onInstance(data) {
  state.inst = data;
  if (state.restoring) {
    // 멈춘 뒤 새 실행 환경에 같은 도면을 다시 넣은 경우: 끝난 결과는 그대로 둔다
    state.restoring = false;
    state.phase = "idle";
    setEngine("멈췄어요. 끝난 방법의 결과는 그대로 두었으니 바로 다시 계산할 수 있어요.", "ready");
    setUi();
    return;
  }
  state.source = state.pendingSource;
  if (state.source && state.source.kind === "upload") {
    markUpload(state.source);
    el.instanceNote.textContent = "직접 올린 도면이에요.";
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
el.run.addEventListener("click", () => {
  const methods = checkedMethods();
  if (!methods.length || !state.inst || state.phase !== "idle") return;
  stopPlay();
  state.selected = methods;
  state.results = {};
  state.running = null;
  state.step = state.inst.summary.pieces;
  el.results.hidden = false;
  state.phase = "computing";
  startClock();
  setUi();
  renderResults();
  worker.postMessage({ type: "run", methods, params: methodParams() });
});

el.stop.addEventListener("click", () => {
  if (state.phase !== "computing") return;
  // Python 계산은 중간에 끊을 수 없어서 작업자를 통째로 끝내고 새로 띄운다
  worker.terminate();
  stopClock();
  for (const n of state.selected) if (!state.results[n]) state.results[n] = { method: n, status: "stopped" };
  state.running = null;
  state.restoring = true;
  state.phase = "restarting";
  setUi();
  renderResults();
  setEngine("계산을 멈췄어요. 다시 계산할 수 있게 준비하고 있어요 (몇 초 걸려요).");
  startWorker();
});

function onDone() {
  stopClock();
  state.running = null;
  state.phase = "idle";
  setUi();
  renderResults();
  el.results.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });
}

// 계산 코드(web/bridge.py)가 보내는 안내문을 이 화면의 말투로 바꾼다. bridge.py는 이전 화면과 같이 써서 고치지 않는다.
const FRIENDLY_ERRORS = [
  [/^JSON 형식이 아닙니다\. 팀 공통 instance JSON이나 sparrow JSON 파일인지 확인하세요\.$/, "JSON 형식이 아니에요. 팀 공통 instance JSON이나 sparrow JSON 파일인지 확인해 주세요."],
  [/^원판 폭을 알 수 없습니다\. 원판 폭 칸에 값을 적고 다시 불러오세요\.$/, "원판 폭을 찾지 못했어요. 원판 폭 칸에 값을 적고 다시 불러와 주세요."],
  [/^지원하지 않는 파일 형식: (\S*) \(JSON, DXF, SVG, XML만 가능\)$/, "이 파일 형식($1)은 읽을 수 없어요. JSON, DXF, SVG, XML 파일을 올려 주세요."],
  [/^형식 검사 실패: /, "도면 내용에 문제가 있어요: "],
];

function friendly(text) {
  let t = String(text ?? "");
  for (const [re, to] of FRIENDLY_ERRORS) t = t.replace(re, to);
  return t;
}

function onError({ during, text: raw }) {
  const text = friendly(raw);
  stopClock();
  state.running = null;
  if (during === "init") {
    state.restoring = false;
    state.phase = "init";
    setEngine(`계산 준비를 하지 못했어요. 인터넷 연결을 확인하고 새로 고침해 주세요. (${text})`, "fail");
    setUi();
    return;
  }
  setEngine(`${during === "run" ? "계산" : "도면 읽기"} 중에 문제가 생겼어요: ${text}`, "fail");
  if (during === "run") {
    for (const n of state.selected) if (!state.results[n]) state.results[n] = { method: n, status: "error", message: text };
    renderResults();
  } else if (state.inst && !state.restoring) {
    el.instanceNote.textContent = `이 파일은 불러오지 못했어요. 지금 도면(${state.inst.summary.name})은 그대로예요.`;
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

function renderVerdict() {
  const s = state.inst.summary;
  const oks = okResults();
  if (!oks.length) {
    el.verdict.innerHTML =
      state.phase === "computing"
        ? `<p class="v-wait">계산 중이에요. 첫 결과가 나오면 여기에 필요한 원판 길이를 보여 드릴게요.</p>`
        : `<p class="v-wait">보여 드릴 결과가 없어요. 아래 표에서 이유를 확인해 주세요.</p>`;
    return;
  }
  const valid = oks.filter(isValid);
  const pool = valid.length ? valid : oks;
  const eps = 1e-9 * Math.max(1, s.width);
  const best = pool.reduce((a, b) =>
    b.length < a.length - eps || (Math.abs(b.length - a.length) <= eps && b.time_place_ms < a.time_place_ms) ? b : a
  );
  const fastest = oks.reduce((a, b) => (b.time_place_ms < a.time_place_ms ? b : a));
  const k = realScale();

  const big = k ? fmtCm(best.length * k) : `${fmt(best.length, 6)}${s.unit ? ` ${s.unit}` : ""}`;
  const basis = k
    ? `${labelOf(best.method)} 배치, 실제 원판 폭 ${fmt(Number(el.realWidth.value), 6)} ${el.realUnit.value} 기준`
    : `${labelOf(best.method)} 배치, 원판 폭 ${fmt(s.width)}의 ${(best.length / s.width).toFixed(2)}배예요. 실제 원판 폭을 적으면 m 단위로 바꿔 드려요.`;

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
    `<div><dt>${oks.length > 1 ? "가장 빠른 계산" : "계산 시간"}</dt><dd>${labelOf(fastest.method)} ${fmtMs(fastest.time_place_ms)}</dd></div>` +
    `</dl>`;

  let diff = "";
  if (oks.length > 1) {
    const longer = oks.filter((r) => r.length > best.length + eps).sort((a, b) => b.length - a.length);
    if (!longer.length) {
      diff = `<p class="v-diff">계산한 방법의 길이가 모두 같아요. 차이는 계산 속도뿐이에요.</p>`;
    } else {
      const parts = longer.map((r) => {
        const d = r.length - best.length;
        return k ? `${labelOf(r.method)}보다 ${fmtCm(d * k)}` : `${labelOf(r.method)}보다 ${fmt(d, 4)} (${((d / r.length) * 100).toFixed(1)}%)`;
      });
      const worst = longer[0].length - best.length;
      const times100 = k ? ` 같은 작업을 100번 하면 ${fmtCm(worst * k * 100)}나 차이 나요.` : "";
      diff = `<p class="v-diff">${parts.join(", ")} 짧아요.${times100}</p>`;
    }
  }

  const bad = oks.filter((r) => !isValid(r));
  const check = bad.length
    ? `<p class="v-check bad">${bad.map((r) => labelOf(r.method)).join(", ")} 배치가 검사를 통과하지 못했어요: ` +
      `${escapeHtml([...bad[0].valid_errors, ...bad[0].rule_errors][0] || "")}</p>`
    : `<p class="v-check ok">겹친 조각도, 원판 밖으로 나간 조각도 없어요. ` +
      `${oks.length > 1 ? `${oks.length}개 방법 모두 개수와 순서까지 확인했어요.` : "개수와 순서도 맞아요."}</p>`;

  const pending = state.phase === "computing" ? `<p class="v-note">아직 계산 중인 방법이 있어서 결론이 바뀔 수 있어요.</p>` : "";
  const actions =
    `<div class="v-actions"><span>이 배치 내려받기${k ? " (실제 크기, mm)" : " (도면 단위)"}</span>` +
    `<button type="button" class="quiet" data-act="svg" data-m="${best.method}">커터용 SVG</button>` +
    `<button type="button" class="quiet" data-act="dxf" data-m="${best.method}">DXF</button></div>`;

  el.verdict.innerHTML =
    `<div class="v-head"><p class="v-label">필요한 원판 길이</p><p class="v-big">${big}</p><p class="v-basis">${basis}</p></div>` +
    `<div class="v-body">${tape}${stats}${diff}${check}${pending}${actions}</div>`;
}

function renderHead(k) {
  const cols = ["방법", "원판 길이", ...(k ? ["실제 길이"] : []), "원판 사용률", "이론상 최소보다", "전체 시간", "가능 위치 계산이 차지한 시간"];
  el.theadRow.innerHTML = cols
    .map((c, i) => `<th scope="col"${i === cols.length - 1 ? ' class="bar-col"' : ""}>${c}</th>`)
    .join("");
  return cols.length;
}

function statusText(name, r) {
  if (!r) return state.running === name ? "계산 중" : state.phase === "computing" ? "기다리는 중" : "";
  if (r.status === "stopped") return "멈춰서 계산하지 않았어요";
  if (r.status === "not_implemented") return "아직 만드는 중인 방법이에요";
  return `문제가 생겼어요: ${escapeHtml(r.message)}`;
}

function renderTable() {
  const k = realScale();
  const ncol = renderHead(k);
  const oks = okResults();
  const bestLen = Math.min(...oks.map((r) => r.length));
  const distinctLen = oks.some((r) => r.length !== bestLen); // 길이가 서로 다를 때만 가장 짧은 값을 굵게
  const maxTime = Math.max(...oks.map((r) => r.time_place_ms), 1e-9);
  const unit = state.inst.summary.unit ? ` ${state.inst.summary.unit}` : "";
  el.tbody.innerHTML = state.selected
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
      const best = distinctLen && r.length === bestLen ? "best" : "";
      return (
        `<tr><td class="name">${label}${flag}</td>` +
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
  for (const name of state.selected) {
    const r = state.results[name];
    const label = labelOf(name);
    const card = document.createElement("article");
    card.className = "strip";
    if (!r) {
      const txt = state.running === name ? "계산 중이에요." : state.phase === "computing" ? "앞 방법이 끝나기를 기다리고 있어요." : "";
      card.innerHTML = `<header><h4>${label}</h4></header><p class="msg">${txt}</p>`;
    } else if (r.status === "stopped") {
      card.innerHTML = `<header><h4>${label}</h4></header><p class="msg">멈춰서 계산하지 않았어요.</p>`;
    } else if (r.status === "not_implemented") {
      card.innerHTML = `<header><h4>${label}</h4></header><p class="msg">아직 만드는 중인 방법이에요. 코드가 합쳐지면 이 자리에 결과가 나와요.</p>`;
    } else if (r.status !== "ok") {
      card.innerHTML = `<header><h4>${label}</h4></header><p class="msg err">${escapeHtml(r.message)}\n${escapeHtml(r.trace || "")}</p>`;
    } else {
      card.innerHTML =
        `<header><h4>${label}</h4>` +
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
