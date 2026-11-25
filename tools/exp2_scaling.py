"""실험 2. 복제 실험 (실험 0의 단계별 시간도 함께 기록).

python tools/exp2_scaling.py                    # SPEC 5.6절의 기본 구성
python tools/exp2_scaling.py --only shirts      # 한 인스턴스만

부품마다 수량을 1, 2, 4, 8(, 16)배로 늘리고 원판 폭은 그대로 둔다. 세 방법을 rows 200으로 돌리고,
shirts 계열은 삼각법과 래스터를 rows 400으로도 돌린다(rows 민감도).

출력 results/exp2_scaling.csv (한 줄에 인스턴스, 배수, 방법, rows 하나)
  t_load_ms   입력: JSON 읽기와 Instance 만들기
  t_seq_ms    A: 배치 순서와 회전 정하기 (fixed_sequence)
  t_place_ms  B: 위치 계산 전체 (Placer 생성과 place_all, 공통 실행 틀의 time_place_ms)
  t_make_ms   C: 결과 생성 (make_solution, 사용 길이와 활용률)
  t_valid_ms  출력 검증 (validate)
  시간은 B가 10초 미만이면 5회 평균과 표준편차, 10초 이상이면 1회다. 다른 단계도 같은 횟수의 평균이다.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import algorithms  # noqa: E402
from algorithms.nfp.geometry_nfp import convex_decompose  # noqa: E402
from nesting.model import Instance, make_solution  # noqa: E402
from nesting.runner import run  # noqa: E402
from nesting.sequence import fixed_sequence  # noqa: E402
from nesting.validate import validate  # noqa: E402

REPEAT_UNDER_S = 10.0
REPEAT = 5
PLAN = {"shirts": [1, 2, 4, 8, 16], "jakobs1": [1, 2, 4, 8, 16], "swim": [1, 2, 4, 8]}
ROWS_SENSITIVITY = {"shirts": 400}


def load_scaled(name: str, mult: int) -> tuple[Instance, float]:
    t0 = time.perf_counter()
    d = json.loads((ROOT / f"data/instances/sparrow/{name}.json").read_text(encoding="utf-8"))
    for it in d["items"]:
        it["quantity"] *= mult
    d["name"] = f"{name}_x{mult}"
    inst = Instance.from_dict(d)
    return inst, (time.perf_counter() - t0) * 1000


def metric(inst: Instance) -> float:
    """(종류별 볼록 조각 수의 합)² ÷ N"""
    s = sum(len(convex_decompose([(p[0], p[1]) for p in it.polygon])) for it in inst.items)
    return s * s / inst.total_quantity


def once(name: str, mult: int, method: str, params: dict) -> dict:
    inst, t_load = load_scaled(name, mult)
    t0 = time.perf_counter()
    seq = fixed_sequence(inst)
    t_seq = (time.perf_counter() - t0) * 1000
    sol = run(inst, algorithms.get_placer(method), sequence=seq, **params)
    t0 = time.perf_counter()
    make_solution(inst, sol.algorithm, sol.placements, sol.time_ms, sol.stats)
    t_make = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    rep = validate(inst, sol)
    t_valid = (time.perf_counter() - t0) * 1000
    return {"inst": inst, "sol": sol, "ok": rep.ok, "t_load": t_load, "t_seq": t_seq,
            "t_place": sol.stats["time_place_ms"], "t_make": t_make, "t_valid": t_valid}  # fmt: skip


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", help="이 인스턴스만 (기본: shirts jakobs1 swim)")
    ap.add_argument("--rows", type=int, default=200)
    ap.add_argument("-o", "--output", type=Path, default=ROOT / "results/exp2_scaling.csv")
    args = ap.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "instance", "mult", "pieces", "metric", "method", "rows", "length", "utilization_pct",
        "t_place_ms_mean", "t_place_ms_sd", "repeats", "t_load_ms", "t_seq_ms", "t_make_ms", "t_valid_ms",
        "valid", "counters",
    ]  # fmt: skip
    print(f"# {platform.platform()} / {platform.processor()} / Python {platform.python_version()}", flush=True)
    with args.output.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for name, mults in PLAN.items():
            if args.only and name not in args.only:
                continue
            for mult in mults:
                runs = [(m, args.rows) for m in ("trig", "nfp", "raster")]
                if name in ROWS_SENSITIVITY:
                    runs += [(m, ROWS_SENSITIVITY[name]) for m in ("trig", "raster")]
                for method, rows in runs:
                    params = {} if method == "nfp" else {"rows": rows}
                    rs = [once(name, mult, method, params)]
                    if rs[0]["t_place"] < REPEAT_UNDER_S * 1000:
                        rs += [once(name, mult, method, params) for _ in range(REPEAT - 1)]
                    first, sol = rs[0], rs[0]["sol"]
                    tp = [r["t_place"] for r in rs]
                    counters = {
                        k: v for k, v in sol.stats.items() if k not in ("time_place_ms", "time_feasible_ms", "params")
                    }
                    row = {
                        "instance": name,
                        "mult": mult,
                        "pieces": first["inst"].total_quantity,
                        "metric": f"{metric(first['inst']):.3g}",
                        "method": method,
                        "rows": "" if method == "nfp" else rows,
                        "length": f"{sol.length:.6g}",
                        "utilization_pct": f"{sol.utilization * 100:.2f}",
                        "t_place_ms_mean": f"{statistics.mean(tp):.2f}",
                        "t_place_ms_sd": f"{statistics.stdev(tp):.2f}" if len(tp) > 1 else "",
                        "repeats": len(rs),
                        "valid": all(r["ok"] for r in rs),
                        "counters": json.dumps(counters, ensure_ascii=False),
                    }
                    for k in ("t_load", "t_seq", "t_make", "t_valid"):
                        row[f"{k}_ms"] = f"{statistics.mean(r[k] for r in rs):.3f}"
                    w.writerow(row)
                    f.flush()
                    print(
                        f"{name:8s} x{mult:<2d} N={row['pieces']:<5d} {method:6s} rows={row['rows']!s:4s} "
                        f"L={row['length']:<9s} U={row['utilization_pct']}% B={row['t_place_ms_mean']}ms x{len(rs)} "
                        f"A={row['t_seq_ms']} C={row['t_make_ms']} 검증={row['t_valid_ms']} valid={row['valid']}",
                        flush=True,
                    )
    print(f"saved {args.output}")


if __name__ == "__main__":
    main()
