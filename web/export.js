// 배치 결과를 그림과 파일로 바꾸는 함수 모음 (화면 표시용 SVG, 커터용 SVG, DXF).
// 좌표계: x는 원판 길이 방향, y는 폭 방향이고 위쪽이 +. SVG는 y가 아래로 +라서 뒤집어 그린다.

export const COLORS = ["#9DC3E6", "#F4B183", "#A9D18E", "#FFD966", "#C9A0DC", "#8FD3C7", "#F8A5A5", "#BFBFBF"];

const num = (v) => Number(v.toPrecision(7)).toString();

export function fmt(v, digits = 4) {
  if (v === null || v === undefined || Number.isNaN(v)) return "";
  const a = Math.abs(v);
  if (a >= 1000) return Math.round(v).toLocaleString("ko-KR");
  return Number(v.toPrecision(digits)).toString();
}

function points(pts, W) {
  return pts.map(([x, y]) => `${num(x)},${num(W - y)}`).join(" ");
}

/**
 * 화면 표시용 배치 그림. 여러 방법을 같은 축척으로 보이도록 viewBox 길이를 scaleLength로 맞춘다.
 * upto: 앞에서부터 몇 개까지 그릴지 (재생용). 마지막으로 놓은 조각은 강조한다.
 */
export function stripSvg(result, width, { scaleLength, upto, lowerBound }) {
  const W = width;
  const L = Math.max(scaleLength, result.length);
  const pad = 0.012 * Math.max(L, W);
  const fs = 0.045 * Math.max(W, L * 0.12);
  const grid = W / 8;
  const n = upto === undefined ? result.placements.length : upto;
  const shown = result.placements.slice(0, n);
  const used = shown.reduce((m, p) => Math.max(m, ...p.pts.map((q) => q[0])), 0);
  const id = `g-${result.method}`;
  const out = [
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${num(-pad)} ${num(-pad - fs * 1.5)} ${num(L + 2 * pad)} ${num(W + 2 * pad + fs * 1.5)}" preserveAspectRatio="xMinYMin meet" role="img" aria-label="${result.label} 배치 그림">`,
    `<defs><pattern id="${id}" width="${num(grid)}" height="${num(grid)}" patternUnits="userSpaceOnUse">`,
    `<path d="M ${num(grid)} 0 L 0 0 0 ${num(grid)}" fill="none" stroke="#2b7570" stroke-width="1" vector-effect="non-scaling-stroke"/></pattern></defs>`,
    `<rect x="0" y="0" width="${num(L)}" height="${num(W)}" fill="url(#${id})" stroke="#3d8a84" stroke-width="1" vector-effect="non-scaling-stroke"/>`,
  ];
  shown.forEach((p, i) => {
    const last = i === n - 1 && n < result.placements.length;
    out.push(
      `<polygon points="${points(p.pts, W)}" fill="${COLORS[p.item % COLORS.length]}" ` +
        `stroke="${last ? "#ffffff" : "#14252b"}" stroke-width="${last ? 3 : 1}" vector-effect="non-scaling-stroke"/>`
    );
  });
  if (lowerBound) {
    out.push(
      `<line x1="${num(lowerBound)}" y1="${num(-fs * 0.3)}" x2="${num(lowerBound)}" y2="${num(W)}" stroke="#ffffff" stroke-width="1.5" stroke-dasharray="5 4" vector-effect="non-scaling-stroke"/>`,
      `<text x="${num(lowerBound)}" y="${num(-fs * 0.5)}" font-size="${num(fs)}" fill="#ffffff" text-anchor="middle">하한 ${fmt(lowerBound)}</text>`
    );
  }
  if (used > 0) {
    // 글자가 그림 밖으로 잘리지 않게: 오른쪽 끝에 가까우면 선 왼쪽에, 하한 글자와 가까우면 선 오른쪽에 쓴다
    let anchor = "middle";
    if (used > L - fs * 4) anchor = "end";
    else if (lowerBound && Math.abs(used - lowerBound) < fs * 7) anchor = "start";
    const tx = anchor === "start" ? used + fs * 0.3 : anchor === "end" ? used - fs * 0.3 : used;
    out.push(
      `<line x1="${num(used)}" y1="${num(-fs * 0.3)}" x2="${num(used)}" y2="${num(W)}" stroke="#f2c94c" stroke-width="2" vector-effect="non-scaling-stroke"/>`,
      `<text x="${num(tx)}" y="${num(-fs * 0.5)}" font-size="${num(fs)}" fill="#f2c94c" font-weight="600" text-anchor="${anchor}">길이 ${fmt(used)}</text>`
    );
  }
  out.push("</svg>");
  return out.join("");
}

/** 조각 하나의 작은 미리보기 그림. */
export function partSvg(item) {
  const xs = item.polygon.map((p) => p[0]);
  const ys = item.polygon.map((p) => p[1]);
  const w = Math.max(...xs) || 1;
  const h = Math.max(...ys) || 1;
  const pad = 0.06 * Math.max(w, h);
  return (
    `<svg viewBox="${num(-pad)} ${num(-pad)} ${num(w + 2 * pad)} ${num(h + 2 * pad)}" aria-hidden="true">` +
    `<polygon points="${points(item.polygon, h)}" fill="${COLORS[item.id % COLORS.length]}" stroke="#14252b" stroke-width="1" vector-effect="non-scaling-stroke"/></svg>`
  );
}

/** 커터용 SVG: 채우지 않은 빨간 선, 실제 치수(단위가 있으면 width/height에 단위를 붙인다). */
export function cutSvg(result, width, unit) {
  const W = width;
  const L = result.length;
  const u = unit || "";
  const sw = num(Math.max(L, W) * 0.0005);
  const out = [
    `<?xml version="1.0" encoding="UTF-8"?>`,
    `<svg xmlns="http://www.w3.org/2000/svg" width="${num(L)}${u}" height="${num(W)}${u}" viewBox="0 0 ${num(L)} ${num(W)}">`,
    `<!-- SheetNest ${result.method}: length ${num(L)}, utilization ${(result.utilization * 100).toFixed(2)}% -->`,
    `<rect id="sheet" x="0" y="0" width="${num(L)}" height="${num(W)}" fill="none" stroke="#0000ff" stroke-width="${sw}"/>`,
    `<g id="parts" fill="none" stroke="#ff0000" stroke-width="${sw}">`,
  ];
  for (const p of result.placements) {
    out.push(`<polygon id="item${p.item}_${p.copy}" points="${points(p.pts, W)}"/>`);
  }
  out.push("</g>", "</svg>");
  return out.join("\n");
}

/** DXF(R12 ASCII): PARTS 레이어에 닫힌 폴리라인, SHEET 레이어에 사용한 원판 사각형. y축은 도면 그대로 위쪽이 +. */
export function dxf(result, width) {
  const lines = ["0", "SECTION", "2", "ENTITIES"];
  const poly = (layer, pts) => {
    lines.push("0", "POLYLINE", "8", layer, "66", "1", "70", "1");
    for (const [x, y] of pts) lines.push("0", "VERTEX", "8", layer, "10", num(x), "20", num(y), "30", "0");
    lines.push("0", "SEQEND", "8", layer);
  };
  const L = result.length;
  poly("SHEET", [[0, 0], [L, 0], [L, width], [0, width]]);
  for (const p of result.placements) poly("PARTS", p.pts);
  lines.push("0", "ENDSEC", "0", "EOF");
  return lines.join("\r\n") + "\r\n";
}

export function download(filename, text, mime) {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
