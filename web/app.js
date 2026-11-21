// SheetNest 웹 화면 동작. 계산은 worker.js(브라우저 안의 Python)가 하고, 이 파일은 화면만 맡는다.
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
  methods: $("methods"),
  run: $("run"),
  results: $("results"),
  tbody: document.querySelector("#table tbody"),
  strips: $("strips"),
  play: $("play"),
  step: $("step"),
  stepOut: $("step-out"),
};

const COUNTER_LABELS = {
  overlap_checks: ["정밀 겹침 판정", "회"],
  bbox_rejects: ["박스 단계 제외", "회"],
  nfp_computed: ["NFP 계산", "개"],
  nfp_cache_hits: ["NFP 재사용", "회"],
  candidate_evals: ["후보점 판정", "회"],
  grid_checks: ["격자 검사", "회"],
  cell_size: ["격자 한 칸", ""],
};

const state = {
  methods: [],
  instances: [],
  inst: null, // { summary, items }
  selected: [], // 이번 실행에 고른 방법 이름
  results: {}, // 방법 이름 → 결과
  running: null,
  busy: false,
  step: 0,
  timer: null,
};

const worker = new Worker("worker.js");
const query = new URLSearchParams(location.search);
worker.postMessage({ type: "init", pyodide: query.get("pyodide") || undefined });

worker.onmessage = (ev) => {
  const m = ev.data;
  if (m.type === "status") setEngine(m.text);
  else if (m.type === "ready") onReady(m);
  else if (m.type === "instance") onInstance(m.data);
  else if (m.type === "running") {
    state.running = m.method;
    renderStrips();
  } else if (m.type === "result") {
    state.results[m.result.method] = m.result;
    state.running = null;
    renderResults();
  } else if (m.type === "done") onDone();
  else if (m.type === "instanceJson") {
    download(`${state.inst.summary.name}_instance.json`, m.text, "application/json");
  } else if (m.type === "error") onError(m);
};
worker.onerror = (e) => onError({ during: "init", text: e.message || "작업자를 시작하지 못했습니다" });

function setEngine(text, cls = "") {
  el.engine.textContent = text;
  el.engine.className = `engine ${cls}`.trim();
}

function setBusy(busy) {
  state.busy = busy;
  el.run.disabled = busy || !state.inst || !checkedMethods().length;
  el.run.textContent = busy ? "계산 중" : "배치 실행";
  el.instance.disabled = busy;
  el.uploadGo.disabled = busy || !el.file.files.length;
}

// ---------------------------------------------------------------- 준비
function onReady({ methods, instances }) {
  state.methods = methods;
  state.instances = instances;
  setEngine("준비 완료. 계산은 모두 이 브라우저 안에서 합니다.", "ready");

  const groups = new Map();
  for (const it of instances) {
    if (!groups.has(it.group)) groups.set(it.group, []);
    groups.get(it.group).push(it);
  }
  el.instance.innerHTML = "";
  for (const [group, items] of groups) {
    const og = document.createElement("optgroup");
    og.label = group;
    for (const it of items) {
      const o = document.createElement("option");
      o.value = it.file;
      o.textContent = it.pieces ? `${it.name} (조각 ${it.pieces}개)` : it.name;
      og.appendChild(o);
    }
    el.instance.appendChild(og);
  }
  renderMethods();
  el.instance.disabled = false;
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
      `${m.label}<span class="state">${stateText}</span></label>`;
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
  el.methods.addEventListener("change", () => setBusy(state.busy));
}

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

// ---------------------------------------------------------------- 도면
function loadBuiltin(file) {
  const entry = state.instances.find((i) => i.file === file);
  el.instanceNote.textContent = entry && entry.note ? entry.note.replace(/^\d+\.\s*/, "") : "";
  setBusy(true);
  worker.postMessage({ type: "loadBuiltin", file });
}

el.instance.addEventListener("change", () => loadBuiltin(el.instance.value));
el.file.addEventListener("change", () => setBusy(state.busy));
el.uploadGo.addEventListener("click", async () => {
  const f = el.file.files[0];
  if (!f) return;
  const options = {
    width: el.optWidth.value ? Number(el.optWidth.value) : null,
    rotations: el.optRot.value.split(",").map(Number),
    unit: el.optUnit.value,
  };
  const buffer = await f.arrayBuffer();
  el.instanceNote.textContent = `올린 파일: ${f.name}`;
  setBusy(true);
  worker.postMessage({ type: "loadUpload", name: f.name, buffer, options }, [buffer]);
});

function onInstance(data) {
  state.inst = data;
  state.results = {};
  state.selected = [];
  el.results.hidden = true;
  if (state.methods.length) setEngine("준비 완료. 계산은 모두 이 브라우저 안에서 합니다.", "ready");
  const s = data.summary;
  const unit = s.unit ? ` ${s.unit}` : "";
  el.summary.hidden = false;
  el.summary.innerHTML =
    `<div><b>${s.types}종</b>조각 종류</div>` +
    `<div><b>${s.pieces}개</b>놓을 조각</div>` +
    `<div><b>${fmt(s.width)}${unit}</b>원판 폭</div>` +
    `<div><b>${fmt(s.lower_bound)}${unit}</b>길이 하한</div>`;
  el.parts.innerHTML = data.items
    .map((it) => `<figure>${partSvg(it)}<figcaption>${it.quantity}개</figcaption></figure>`)
    .join("");
  setBusy(false);
}

// ---------------------------------------------------------------- 실행
el.run.addEventListener("click", () => {
  const methods = checkedMethods();
  if (!methods.length || !state.inst) return;
  stopPlay();
  state.selected = methods;
  state.results = {};
  state.step = state.inst.summary.pieces;
  el.results.hidden = false;
  setBusy(true);
  renderResults();
  worker.postMessage({ type: "run", methods, params: methodParams() });
});

function onDone() {
  state.running = null;
  setBusy(false);
  renderResults();
  el.results.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "start" });
}

function onError({ during, text }) {
  state.running = null;
  if (during === "init") {
    setEngine(`실행 환경을 불러오지 못했습니다. 인터넷 연결을 확인하고 새로 고치세요. (${text})`, "fail");
    return;
  }
  setEngine(`${during === "run" ? "계산" : "도면 읽기"} 중 오류: ${text}`, "fail");
  if (during !== "run" && state.inst) {
    el.instanceNote.textContent = `불러오지 못했습니다. 지금 도면은 ${state.inst.summary.name} 그대로입니다.`;
  }
  setBusy(false);
}

// ---------------------------------------------------------------- 결과 화면
function okResults() {
  return state.selected.map((n) => state.results[n]).filter((r) => r && r.status === "ok");
}

function renderResults() {
  renderTable();
  const n = state.inst ? state.inst.summary.pieces : 0;
  el.step.max = String(n);
  el.step.value = String(state.step);
  renderStrips();
}

function renderTable() {
  const oks = okResults();
  const bestLen = Math.min(...oks.map((r) => r.length));
  const distinctLen = oks.some((r) => r.length !== bestLen); // 길이가 서로 다를 때만 가장 짧은 값을 굵게
  const maxTime = Math.max(...oks.map((r) => r.time_place_ms), 1e-9);
  const unit = state.inst.summary.unit ? ` ${state.inst.summary.unit}` : "";
  el.tbody.innerHTML = state.selected
    .map((name) => {
      const r = state.results[name];
      const label = (state.methods.find((m) => m.name === name) || {}).label || name;
      if (!r) {
        const txt = state.running === name ? "계산 중" : "기다리는 중";
        return `<tr><td class="name">${label}</td><td colspan="7" class="muted" style="text-align:left">${txt}</td></tr>`;
      }
      if (r.status !== "ok") {
        const txt = r.status === "not_implemented" ? "아직 구현 중인 방법입니다" : `오류: ${escapeHtml(r.message)}`;
        return `<tr><td class="name">${label}</td><td colspan="7" class="muted" style="text-align:left">${txt}</td></tr>`;
      }
      const core = (r.time_feasible_ms / maxTime) * 100;
      const rest = ((r.time_place_ms - r.time_feasible_ms) / maxTime) * 100;
      const valid = r.valid && !r.rule_errors.length;
      const why = [...r.valid_errors, ...r.rule_errors].join("\n");
      return (
        `<tr><td class="name">${label}</td>` +
        `<td class="${distinctLen && r.length === bestLen ? "best" : ""}">${fmt(r.length, 6)}${unit}</td>` +
        `<td>+${(r.over_lower_bound * 100).toFixed(1)}%</td>` +
        `<td>${(r.utilization * 100).toFixed(1)}%</td>` +
        `<td>${fmtMs(r.time_place_ms)}</td>` +
        `<td class="bar-col"><div class="bar"><div class="track"><div class="core" style="width:${core}%"></div>` +
        `<div class="rest" style="width:${rest}%"></div></div>` +
        `<span class="pct">${(r.feasible_ratio * 100).toFixed(1)}%</span></div></td>` +
        `<td class="counters">${counterText(r.counters)}</td>` +
        `<td><span class="badge ${valid ? "ok" : "bad"}" title="${escapeHtml(why)}">${valid ? "통과" : "실패"}</span></td></tr>`
      );
    })
    .join("");
}

function counterText(counters) {
  return Object.entries(counters)
    .filter(([k, v]) => !(k === "bbox_rejects" && v === 0))
    .map(([k, v]) => {
      const [label, suffix] = COUNTER_LABELS[k] || [k, ""];
      const val = typeof v === "number" ? (Number.isInteger(v) ? v.toLocaleString("ko-KR") : fmt(v)) : v;
      return `${label} ${val}${suffix}`;
    })
    .join("<br>");
}

function fmtMs(ms) {
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}초` : `${ms.toFixed(ms < 10 ? 1 : 0)}ms`;
}

function renderStrips() {
  const s = state.inst.summary;
  const oks = okResults();
  const scaleLength = Math.max(...oks.map((r) => r.length), s.lower_bound);
  el.stepOut.textContent = `${state.step} / ${s.pieces}개`;
  el.strips.innerHTML = "";
  for (const name of state.selected) {
    const r = state.results[name];
    const label = (state.methods.find((m) => m.name === name) || {}).label || name;
    const card = document.createElement("article");
    card.className = "strip";
    if (!r) {
      card.innerHTML = `<header><h3>${label}</h3></header><p class="msg">${state.running === name ? "계산 중입니다." : "앞 방법이 끝나기를 기다리는 중입니다."}</p>`;
    } else if (r.status === "not_implemented") {
      card.innerHTML = `<header><h3>${label}</h3></header><p class="msg">아직 구현 중인 방법입니다. 코드가 합쳐지면 이 자리에 결과가 나옵니다.</p>`;
    } else if (r.status !== "ok") {
      card.innerHTML = `<header><h3>${label}</h3></header><p class="msg err">${escapeHtml(r.message)}\n${escapeHtml(r.trace || "")}</p>`;
    } else {
      card.innerHTML =
        `<header><h3>${label}</h3>` +
        `<span class="nums">길이 ${fmt(r.length, 6)}, 활용률 ${(r.utilization * 100).toFixed(1)}%</span>` +
        `<span class="tools">` +
        `<button type="button" class="quiet" data-act="svg" data-m="${name}">커터용 SVG 받기</button>` +
        `<button type="button" class="quiet" data-act="dxf" data-m="${name}">DXF 받기</button>` +
        `<button type="button" class="quiet" data-act="json" data-m="${name}">결과 JSON 받기</button>` +
        `</span></header>` +
        `<div class="canvas">${stripSvg(r, s.width, { scaleLength, upto: state.step, lowerBound: s.lower_bound })}</div>`;
    }
    el.strips.appendChild(card);
  }
}

el.strips.addEventListener("click", (ev) => {
  const b = ev.target.closest("button[data-act]");
  if (!b) return;
  const r = state.results[b.dataset.m];
  const s = state.inst.summary;
  const base = `${s.name}_${r.method}`;
  if (b.dataset.act === "svg") download(`${base}.svg`, cutSvg(r, s.width, s.unit), "image/svg+xml");
  else if (b.dataset.act === "dxf") download(`${base}.dxf`, dxf(r, s.width), "application/dxf");
  else download(`${base}_solution.json`, JSON.stringify(r.solution, null, 1), "application/json");
});

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
