"""비교 대상 방법을 선정 인스턴스에 돌려 제약 검사, 수치표, 배치 그림을 한 페이지로 만든다.

python tools/report.py                      # 구현된 방법 전부, 시간 5회 반복
python tools/report.py trig --repeat 3      # 삼각법만
python tools/report.py trig nfp -o results/

출력 (기본 results/)
  report.html        제약 검사 결과, 수치표, 인스턴스별 배치 그림
  <방법>.csv          보고서 결과표 열 순서와 같은 수치

세 방법 모두 결정적이므로 사용 길이와 활용률은 첫 실행 값을 쓰고, 시간은 repeat회 평균이다.
"""

import argparse
import csv
import html
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import algorithms  # noqa: E402
from nesting import constraints  # noqa: E402
from nesting import geometry as g  # noqa: E402
from nesting.model import Instance, Solution  # noqa: E402

COLORS = ["#9DC3E6", "#F4B183", "#A9D18E", "#FFD966", "#C9A0DC", "#8FD3C7", "#F8A5A5", "#BFBFBF"]
NAMES = {"trig": "삼각법", "nfp": "NFP", "raster": "래스터"}


def selected():
    for line in (ROOT / "experiments/selected.txt").read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if line:
            yield ROOT / line


def layout_svg(inst: Instance, sol: Solution) -> str:
    L, W = sol.length, inst.sheet_width
    pad = 0.01 * max(L, W)
    by_id = {it.id: it for it in inst.items}
    out = [
        f'<svg viewBox="{-pad:.4g} {-pad:.4g} {L + 2 * pad:.4g} {W + 2 * pad:.4g}" '
        f'preserveAspectRatio="xMinYMin meet" class="lay">',
        f'<rect x="0" y="0" width="{L:.6g}" height="{W:.6g}" class="sheet"/>',
    ]
    sw = 0.0015 * max(L, W)
    for p in sol.placements:
        poly = g.transform(by_id[p.item].polygon, p.rotation, p.x, p.y)
        pts = " ".join(f"{x:.5g},{W - y:.5g}" for x, y in poly)  # y축 뒤집기: 원판 아래쪽이 y=0
        out.append(
            f'<polygon points="{pts}" fill="{COLORS[p.item % len(COLORS)]}" stroke="#1F3864" stroke-width="{sw:.3g}"/>'
        )
    out.append("</svg>")
    return "".join(out)


def run_one(name, inst, repeat):
    nest = algorithms.get(name)
    req = algorithms.get_placer(name).REQUIRED_COUNTERS
    sols = [nest(inst) for _ in range(repeat)]
    sol = sols[0]
    errs = constraints.check(inst, sol, name, req)
    if any(s.placements != sol.placements for s in sols[1:]):
        errs.append("반복 실행 결과가 다름 (결정적이지 않음)")
    t_all = [s.stats["time_place_ms"] for s in sols]
    t_feas = [s.stats["time_feasible_ms"] for s in sols]
    return {
        "instance": inst.name,
        "pieces": inst.total_quantity,
        "length": sol.length,
        "lb_gap": (sol.length / inst.length_lower_bound - 1) * 100,
        "util": sol.utilization * 100,
        "time_ms": statistics.mean(t_all),
        "time_sd": statistics.stdev(t_all) if repeat > 1 else 0.0,
        "feas_ms": statistics.mean(t_feas),
        "feas_pct": statistics.mean(f / a * 100 for f, a in zip(t_feas, t_all, strict=True)),
        "counters": {k: sol.stats[k] for k in req if k in sol.stats},
        "errors": errs,
        "svg": layout_svg(inst, sol),
    }


CSS = """
body{font-family:-apple-system,'Malgun Gothic','Apple SD Gothic Neo',sans-serif;margin:0;padding:16px;color:#222;
background:#fafafa;line-height:1.5}
h1{font-size:20px;margin:0 0 4px}h2{font-size:16px;margin:28px 0 8px}h3{font-size:14px;margin:18px 0 4px}
.sub{color:#666;font-size:13px;margin:0 0 12px}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600}
.ok{background:#E2F0D9;color:#38761D}.ng{background:#FCE4E4;color:#A61C1C}
.wrap{overflow-x:auto}table{border-collapse:collapse;font-size:13px;background:#fff;min-width:100%}
th,td{border:1px solid #ddd;padding:6px 8px;text-align:right;white-space:nowrap}
th{background:#f0f3f7;font-weight:600}td:first-child,th:first-child{text-align:left}
.card{background:#fff;border:1px solid #e3e3e3;border-radius:8px;padding:10px 12px;margin:10px 0}
.meta{font-size:12px;color:#555;margin:2px 0 8px}
svg.lay{width:100%;height:auto;max-height:340px;display:block;background:#fff}
svg.lay .sheet{fill:#fdfdf6;stroke:#888;stroke-dasharray:1 1;vector-effect:non-scaling-stroke}
.err{color:#A61C1C;font-size:12px}
"""


def page(results, repeat):
    out = [
        "<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>SheetNest 실행 리포트</title><style>{CSS}</style></head><body>",
        "<h1>SheetNest 실행 리포트</h1>",
        f"<p class='sub'>{time.strftime('%Y-%m-%d %H:%M')} 생성, 시간은 {repeat}회 평균. "
        "배치 순서는 면적 큰 순으로 고정, 위치 선택은 Bottom-Left.</p>",
    ]
    for name, rows in results.items():
        n_ok = sum(not r["errors"] for r in rows)
        cls = "ok" if n_ok == len(rows) else "ng"
        out.append(
            f"<h2>{NAMES.get(name, name)} ({name}) <span class='badge {cls}'>제약 만족 {n_ok}/{len(rows)}</span></h2>"
        )
        ckeys = list(rows[0]["counters"]) if rows else []
        out.append("<div class='wrap'><table><tr><th>인스턴스</th><th>부품 수</th><th>사용 길이</th>")
        out.append("<th>하한 대비</th><th>활용률(%)</th><th>전체 시간(ms)</th><th>가능 위치 계산(ms)</th><th>비율</th>")
        out.append("".join(f"<th>{k}</th>" for k in ckeys) + "<th>제약 만족</th></tr>")
        for r in rows:
            mark = "<span class='badge ok'>만족</span>" if not r["errors"] else "<span class='badge ng'>위반</span>"
            out.append(
                f"<tr><td>{r['instance']}</td><td>{r['pieces']}</td><td>{r['length']:.6g}</td>"
                f"<td>+{r['lb_gap']:.1f}%</td><td>{r['util']:.1f}</td>"
                f"<td>{r['time_ms']:.1f} ± {r['time_sd']:.1f}</td><td>{r['feas_ms']:.1f}</td><td>{r['feas_pct']:.1f}%</td>"
                + "".join(f"<td>{r['counters'][k]:,}</td>" for k in ckeys)
                + f"<td>{mark}</td></tr>"
            )
        out.append("</table></div>")
        out.append(
            "<p class='sub'>하한 대비는 부품 면적 합을 원판 폭으로 나눈 이론 하한보다 얼마나 긴지를 뜻한다. "
            "비율은 전체 시간 중 가능 위치 계산이 차지한 몫이다.</p>"
        )
        for r in rows:
            out.append(f"<div class='card'><h3>{r['instance']}</h3>")
            out.append(
                f"<p class='meta'>사용 길이 {r['length']:.6g}, 활용률 {r['util']:.1f}%, "
                f"{r['pieces']}개, {r['time_ms']:.0f}ms. 점선 사각형이 사용한 원판, 색은 부품 종류.</p>"
            )
            out.append(r["svg"])
            for e in r["errors"]:
                out.append(f"<p class='err'>{html.escape(e)}</p>")
            out.append("</div>")
    out.append("</body></html>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("algorithms", nargs="*", help="기본: 비교 대상 중 구현된 것 전부")
    ap.add_argument("--repeat", type=int, default=5)
    ap.add_argument("-o", "--output", default=str(ROOT / "results"))
    a = ap.parse_args()
    names = a.algorithms or algorithms.COMPARED
    insts = [Instance.load(p) for p in selected()]
    results = {}
    for name in names:
        rows = []
        for inst in insts:
            try:
                r = run_one(name, inst, a.repeat)
            except NotImplementedError:
                print(f"{name}: 미구현, 건너뜀")
                break
            rows.append(r)
            status = "만족" if not r["errors"] else "위반 " + "; ".join(r["errors"])
            print(
                f"{name:6s} {r['instance']:9s} L={r['length']:<10.6g} U={r['util']:5.1f}% "
                f"{r['time_ms']:8.1f}ms 가능위치 {r['feas_pct']:5.1f}%  제약 {status}"
            )
        if rows:
            results[name] = rows
    out = Path(a.output)
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in results.items():
        with open(out / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["instance", "length", "utilization_pct", "time_ms", "time_feasible_ms", "feasible_pct"])
            for r in rows:
                w.writerow(
                    [
                        r["instance"],
                        f"{r['length']:.6g}",
                        f"{r['util']:.2f}",
                        f"{r['time_ms']:.1f}",
                        f"{r['feas_ms']:.1f}",
                        f"{r['feas_pct']:.1f}",
                    ]
                )
    (out / "report.html").write_text(page(results, a.repeat), encoding="utf-8")
    print("saved", out / "report.html")
    bad = sum(bool(r["errors"]) for rows in results.values() for r in rows)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
