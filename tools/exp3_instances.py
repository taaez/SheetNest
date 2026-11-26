"""실험 3. 실제 인스턴스 전체 (experiments/README.md의 실험 규칙).

python tools/exp3_instances.py                 # 23개 전부, 실행 한 번에 10분 제한
python tools/exp3_instances.py --jobs 2        # 두 개씩 동시에 (코어가 2개 이상일 때)
python tools/exp3_instances.py --only fu swim  # 일부만
python tools/exp3_instances.py --summary       # 이미 잰 CSV로 요약만 다시 만든다

인스턴스마다 세 방법을 rows 200으로 돌린다. 실행 하나는 별도 프로세스에서 돌리고 제한 시간을 넘기면 끝낸다(시간 초과).
중간에 끊겨도 다시 실행하면 CSV에 이미 있는 줄은 건너뛴다.

출력
  results/exp3_instances.csv   한 줄에 인스턴스, 방법 하나. status는 ok 또는 timeout
  results/exp3_recommend.csv   제한 시간 T(1초, 10초, 1분, 10분, 없음)별 추천 방법: T 안에 끝난 방법 중 사용 길이가 가장 짧은 방법
  results/exp3_summary.md      NFP가 가장 짧은 비율, 순서 규칙(NFP, 삼각법, 래스터)의 적중, 특징과 시간의 순위 상관
시간은 위치 계산 전체(B, time_place_ms)이고 10초 미만이면 5회 평균과 표준편차, 10초 이상이면 1회다.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data/instances/sparrow"
METHODS = ("trig", "nfp", "raster")
LABEL = {"trig": "삼각법", "nfp": "NFP", "raster": "래스터"}
LIMIT_S = 600.0
REPEAT_UNDER_S = 10.0
REPEAT = 5
T_LIST = [("1초", 1.0), ("10초", 10.0), ("1분", 60.0), ("10분", 600.0), ("없음", float("inf"))]
ORDER = ("nfp", "trig", "raster")  # 웹의 계산 전 추천 순서
COLS = [
    "instance", "pieces", "types", "convex_sum", "metric", "vertices", "max_vertices", "method", "rows", "status",
    "length", "utilization_pct", "over_lb_pct", "t_place_ms_mean", "t_place_ms_sd", "repeats", "valid",
]  # fmt: skip


def instance_names() -> list[str]:
    """sparrow 인스턴스 23개. 이름이 _c로 끝나는 변형은 뺀다(웹의 도면 목록과 같다)."""
    return sorted(p.stem for p in DATA.glob("*.json") if not p.stem.endswith("_c"))


def child(name: str, method: str, rows: int) -> None:
    """실행 하나. 결과를 JSON 한 줄로 찍는다."""
    import algorithms
    from algorithms.nfp.geometry_nfp import convex_decompose
    from nesting.model import Instance
    from nesting.runner import run
    from nesting.sequence import fixed_sequence
    from nesting.validate import validate

    inst = Instance.load(DATA / f"{name}.json")
    params = {} if method == "nfp" else {"rows": rows}
    times, sol, ok = [], None, True
    while len(times) < REPEAT:
        sol = run(inst, algorithms.get_placer(method), sequence=fixed_sequence(inst), **params)
        ok = ok and validate(inst, sol).ok
        times.append(sol.stats["time_place_ms"])
        if times[0] >= REPEAT_UNDER_S * 1000:
            break
    s = sum(len(convex_decompose([(p[0], p[1]) for p in it.polygon])) for it in inst.items)
    lb = inst.length_lower_bound
    print(json.dumps({
        "instance": name, "pieces": inst.total_quantity, "types": len(inst.items), "convex_sum": s,
        "metric": f"{s * s / inst.total_quantity:.4g}", "vertices": sum(len(it.polygon) for it in inst.items),
        "max_vertices": max(len(it.polygon) for it in inst.items), "method": method,
        "rows": "" if method == "nfp" else rows, "status": "ok", "length": f"{sol.length:.6g}",
        "utilization_pct": f"{sol.utilization * 100:.2f}", "over_lb_pct": f"{(sol.length / lb - 1) * 100:.1f}",
        "t_place_ms_mean": f"{statistics.mean(times):.2f}",
        "t_place_ms_sd": f"{statistics.stdev(times):.2f}" if len(times) > 1 else "", "repeats": len(times), "valid": ok,
    }))  # fmt: skip


def features(name: str) -> dict:
    """시간 초과로 끝난 실행의 줄에도 모양 특징을 채운다."""
    from algorithms.nfp.geometry_nfp import convex_decompose
    from nesting.model import Instance

    inst = Instance.load(DATA / f"{name}.json")
    s = sum(len(convex_decompose([(p[0], p[1]) for p in it.polygon])) for it in inst.items)
    return {
        "instance": name, "pieces": inst.total_quantity, "types": len(inst.items), "convex_sum": s,
        "metric": f"{s * s / inst.total_quantity:.4g}", "vertices": sum(len(it.polygon) for it in inst.items),
        "max_vertices": max(len(it.polygon) for it in inst.items),
    }  # fmt: skip


def run_one(name: str, method: str, rows: int, limit: float) -> dict:
    cmd = [sys.executable, str(Path(__file__).resolve()), "--child", name, method, "--rows", str(rows)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=limit)
    except subprocess.TimeoutExpired:
        return {**features(name), "method": method, "rows": "" if method == "nfp" else rows, "status": "timeout"}
    if out.returncode != 0:
        raise RuntimeError(f"{name} {method}: {out.stderr[-500:]}")
    return json.loads(out.stdout.strip().splitlines()[-1])


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def spearman(xs: list[float], ys: list[float]) -> float:
    """순위 상관. 같은 값은 평균 순위를 준다."""

    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r

    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else float("nan")


def summarize(rows: list[dict], out_dir: Path, env: str) -> None:
    by: dict[str, dict[str, dict]] = {}
    for r in rows:
        by.setdefault(r["instance"], {})[r["method"]] = r
    names = sorted(by, key=lambda n: float(by[n][next(iter(by[n]))]["metric"]))
    sec = lambda r: float(r["t_place_ms_mean"]) / 1000 if r["status"] == "ok" else float("inf")  # noqa: E731

    def best(done: list[dict]) -> dict | None:
        """끝난 방법 중 사용 길이가 가장 짧은 것. 길이가 같으면 빠른 쪽."""
        return min(done, key=lambda r: (float(r["length"]), sec(r))) if done else None

    # T별 추천 표
    rec_rows, hit = [], {t: [0, 0, 0.0] for t, _ in T_LIST}
    for n in names:
        row = {"instance": n, "metric": by[n][next(iter(by[n]))]["metric"]}
        for label, t in T_LIST:
            done = [r for r in by[n].values() if sec(r) <= min(t, LIMIT_S)]
            b = best(done)
            row[label] = LABEL[b["method"]] if b else "없음"
            if b:  # 계산 전 추천 순서(NFP, 삼각법, 래스터)가 실제로 가장 짧은 방법과 같은가
                guess = next(r for m in ORDER for r in done if r["method"] == m)
                hit[label][0] += 1
                same = float(guess["length"]) <= float(b["length"]) * (1 + 1e-9)
                hit[label][1] += same
                hit[label][2] = max(hit[label][2], (float(guess["length"]) / float(b["length"]) - 1) * 100)
        rec_rows.append(row)
    with (out_dir / "exp3_recommend.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["instance", "metric", *[t for t, _ in T_LIST]])
        w.writeheader()
        w.writerows(rec_rows)

    full = [n for n in names if all(m in by[n] and by[n][m]["status"] == "ok" for m in METHODS)]
    winner = {n: best(list(by[n].values()))["method"] for n in full}
    nfp_best = [n for n in full if winner[n] == "nfp"]
    timeouts = ", ".join(
        "{} {}개".format(LABEL[m], sum(1 for n in names if m in by[n] and by[n][m]["status"] == "timeout"))
        for m in METHODS
    )
    others = ", ".join(f"{n}({LABEL[winner[n]]})" for n in full if n not in nfp_best)
    lines = [
        "# 실험 3 요약",
        "",
        f"- 환경: {env}",
        f"- 인스턴스 {len(names)}개, 방법 3개, rows 200, 실행 한 번에 {LIMIT_S / 60:.0f}분 제한",
        f"- 시간 초과: {timeouts}",
        f"- 세 방법이 모두 끝난 인스턴스 {len(full)}개 중 NFP가 가장 짧은 것 {len(nfp_best)}개"
        + (f" (예외: {others})" if others else ""),
        "",
        "## 제한 시간 T별 추천 방법 (T 안에 끝난 방법 중 사용 길이가 가장 짧은 방법)",
        "",
        "| 인스턴스 | 지표 | " + " | ".join(t for t, _ in T_LIST) + " |",
        "|---|---|" + "---|" * len(T_LIST),
        *[f"| {r['instance']} | {r['metric']} | " + " | ".join(r[t] for t, _ in T_LIST) + " |" for r in rec_rows],
        "",
        "T = 없음은 10분 상한과 같다. 10분 안에 끝나지 않은 방법은 후보에서 빠진다.",
        "",
        "## 계산 전 추천 순서(NFP, 삼각법, 래스터)의 적중",
        "",
        "T 안에 끝난 방법 중 이 순서로 처음 나오는 방법이 실제로 가장 짧은 방법과 같은지 센다(웹의 계산 전 추천 규칙).",
        "",
        "| T | 끝난 방법이 있는 인스턴스 | 적중 | 빗나갔을 때 가장 큰 길이 손해 |",
        "|---|---|---|---|",
        *[f"| {t} | {hit[t][0]} | {hit[t][1]} | {hit[t][2]:.1f}% |" for t, _ in T_LIST],
        "",
        "## 모양 특징과 계산 시간의 순위 상관 (Spearman)",
        "",
        "시간 초과는 제한 시간(10분)으로 놓고 센다.",
        "",
        "| 특징 | " + " | ".join(LABEL[m] for m in METHODS) + " |",
        "|---|---|---|---|",
    ]
    feats = [("지표 (볼록 조각 수의 합)² ÷ N", "metric"), ("볼록 조각 수의 합", "convex_sum"), ("조각 수 N", "pieces"),
             ("종류 수", "types"), ("꼭짓점 수 합", "vertices"), ("가장 많은 꼭짓점 수", "max_vertices")]  # fmt: skip
    for title, key in feats:
        cells = []
        for m in METHODS:
            ns = [n for n in names if m in by[n]]
            cells.append(
                f"{spearman([float(by[n][m][key]) for n in ns], [min(sec(by[n][m]), LIMIT_S) for n in ns]):.2f}"
            )
        lines.append(f"| {title} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## 인스턴스별 사용 길이와 시간",
        "",
        "| 인스턴스 | N | 지표 | 삼각법 길이 | NFP 길이 | 래스터 길이 | 삼각법 시간 | NFP 시간 | 래스터 시간 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    fmt_t = lambda r: "시간 초과" if r["status"] != "ok" else f"{sec(r):.3g}초"  # noqa: E731
    for n in names:
        rs = [by[n].get(m) for m in METHODS]
        any_row = next(r for r in rs if r)
        lens = [r["length"] if r and r["status"] == "ok" else "" for r in rs]
        times = [fmt_t(r) if r else "" for r in rs]
        lines.append(f"| {n} | {any_row['pieces']} | {any_row['metric']} | " + " | ".join(lens + times) + " |")
    (out_dir / "exp3_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:8]))
    print(f"saved {out_dir / 'exp3_recommend.csv'}, {out_dir / 'exp3_summary.md'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", help="이 인스턴스만 (기본: 23개 전부)")
    ap.add_argument("--rows", type=int, default=200)
    ap.add_argument("--limit", type=float, default=LIMIT_S, help="실행 한 번의 제한 시간(초)")
    ap.add_argument("--jobs", type=int, default=1, help="동시에 돌릴 실행 수")
    ap.add_argument("--summary", action="store_true", help="측정 없이 요약만 다시 만든다")
    ap.add_argument("--child", nargs=2, metavar=("INSTANCE", "METHOD"), help=argparse.SUPPRESS)
    ap.add_argument("-o", "--output", type=Path, default=ROOT / "results/exp3_instances.csv")
    args = ap.parse_args()
    if args.child:
        return child(args.child[0], args.child[1], args.rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    env = f"{platform.platform()} / Python {platform.python_version()} / 동시 실행 {args.jobs}개"
    if not args.summary:
        done = {(r["instance"], r["method"]) for r in read_rows(args.output)}
        names = [n for n in instance_names() if not args.only or n in args.only]
        # 빨리 끝나는 래스터를 먼저, 오래 걸리는 NFP를 마지막에 돌린다
        todo = [(n, m) for m in ("raster", "trig", "nfp") for n in names if (n, m) not in done]
        print(f"# {env} / 남은 실행 {len(todo)}개", flush=True)
        new = not args.output.exists()
        with args.output.open("a", newline="", encoding="utf-8") as f, ThreadPoolExecutor(args.jobs) as pool:
            w = csv.DictWriter(f, fieldnames=COLS)
            if new:
                w.writeheader()
            for row in pool.map(lambda j: run_one(j[0], j[1], args.rows, args.limit), todo):
                w.writerow(row)
                f.flush()
                print(
                    f"{row['instance']:9s} {row['method']:6s} {row['status']:7s} L={row.get('length', ''):<9s} "
                    f"B={row.get('t_place_ms_mean', '')}ms x{row.get('repeats', '')}",
                    flush=True,
                )
    summarize(read_rows(args.output), args.output.parent, env)


if __name__ == "__main__":
    main()
