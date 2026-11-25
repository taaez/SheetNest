"""실험 1. 격자 간격 rows에 따른 삼각법과 래스터의 품질과 시간.

python tools/exp1_rows.py                       # 선정 7개, rows 100 200 400
python tools/exp1_rows.py --rows 100 200 --skip-gap gardeyn1

출력 results/exp1_rows.csv (한 줄에 방법 하나, rows 하나, 인스턴스 하나)
  NFP는 격자를 쓰지 않으므로 기준선으로 인스턴스마다 한 번만 돌린다(rows 열은 비움).
  시간: 1회가 10초 미만이면 5회 평균과 표준편차, 10초 이상이면 1회.
  bl_gap_mean_pct_w: 같은 상태에서 NFP가 구한 정확한 Bottom-Left 위치보다 x가 평균 몇 % W 뒤에 놓였는가.
  bl_gap_max_pct_w: 그 최댓값. bl_match: 정확한 Bottom-Left 위치와 같은 배치 수.
  NFP 재현이 매우 오래 걸리는 인스턴스는 --skip-gap으로 이 세 열을 비운다(기본 gardeyn1).
"""

from __future__ import annotations

import argparse
import csv
import platform
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import algorithms  # noqa: E402
from algorithms.nfp.placer import NFPCore  # noqa: E402
from nesting.collision import tolerance_for  # noqa: E402
from nesting.model import Instance  # noqa: E402
from nesting.validate import validate  # noqa: E402

REPEAT_UNDER_S = 10.0
REPEAT = 5


def selected() -> list[Path]:
    text = (ROOT / "experiments/selected.txt").read_text(encoding="utf-8")
    return [ROOT / ln.split("#")[0].strip() for ln in text.splitlines() if ln.split("#")[0].strip()]


def timed(name: str, inst: Instance, params: dict):
    """첫 실행의 결과와 시간 목록(밀리초). 10초 미만이면 REPEAT회까지 더 잰다."""
    sol = algorithms.get(name)(inst, **params)
    times = [sol.stats["time_place_ms"]]
    if times[0] < REPEAT_UNDER_S * 1000:
        for _ in range(REPEAT - 1):
            times.append(algorithms.get(name)(inst, **params).stats["time_place_ms"])
    return sol, times


def bl_gap(inst: Instance, sol) -> tuple[float, float, int]:
    """sol의 배치 순서를 그대로 따라가며 매 단계 NFP의 정확한 Bottom-Left 위치와 비교한다."""
    W = inst.sheet_width
    tol = tolerance_for(W) * 10
    core = NFPCore(inst)
    gaps, same = [], 0
    for p in sol.placements:
        bx, by = core._best_position(p.item, p.rotation, core.placed, None)
        if abs(bx - p.x) <= tol and abs(by - p.y) <= tol:
            same += 1
        gaps.append(max(0.0, p.x - bx) / W * 100)
        core.record(p.item, p.rotation, p.x, p.y)
    return statistics.mean(gaps), max(gaps), same


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rows", type=int, nargs="+", default=[100, 200, 400])
    ap.add_argument("--skip-gap", nargs="*", default=["gardeyn1"], help="BL 차이를 재지 않을 인스턴스 이름")
    ap.add_argument("-o", "--output", type=Path, default=ROOT / "results/exp1_rows.csv")
    args = ap.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "instance", "pieces", "method", "rows", "cell_size", "length", "utilization_pct",
        "time_ms_mean", "time_ms_sd", "repeats", "bl_gap_mean_pct_w", "bl_gap_max_pct_w", "bl_match", "valid",
    ]  # fmt: skip
    print(f"# {platform.platform()} / {platform.processor()} / Python {platform.python_version()}", flush=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for path in selected():
            inst = Instance.load(path)
            runs = [("nfp", None)] + [(m, r) for m in ("trig", "raster") for r in args.rows]
            for name, rows in runs:
                params = {} if rows is None else {"rows": rows}
                sol, times = timed(name, inst, params)
                rep = validate(inst, sol)
                row = {
                    "instance": inst.name,
                    "pieces": inst.total_quantity,
                    "method": name,
                    "rows": rows if rows is not None else "",
                    "cell_size": f"{inst.sheet_width / rows:.6g}" if rows else "",
                    "length": f"{sol.length:.6g}",
                    "utilization_pct": f"{sol.utilization * 100:.2f}",
                    "time_ms_mean": f"{statistics.mean(times):.1f}",
                    "time_ms_sd": f"{statistics.stdev(times):.1f}" if len(times) > 1 else "",
                    "repeats": len(times),
                    "valid": rep.ok,
                }
                if name != "nfp" and inst.name not in args.skip_gap:
                    mean, mx, same = bl_gap(inst, sol)
                    row.update(
                        bl_gap_mean_pct_w=f"{mean:.2f}",
                        bl_gap_max_pct_w=f"{mx:.2f}",
                        bl_match=f"{same}/{len(sol.placements)}",
                    )
                w.writerow(row)
                f.flush()
                print(
                    f"{inst.name:9s} {name:6s} rows={row['rows']!s:4s} L={row['length']:<9s} U={row['utilization_pct']}% "
                    f"{row['time_ms_mean']}ms x{len(times)} gap={row.get('bl_gap_mean_pct_w', '-')}/{row.get('bl_gap_max_pct_w', '-')} "
                    f"BL={row.get('bl_match', '-')} valid={rep.ok}",
                    flush=True,
                )
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
