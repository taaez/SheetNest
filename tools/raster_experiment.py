"""격자 해상도 비교: python tools/raster_experiment.py --rows 100 200 400 --repeat 3."""

import argparse
import csv
import platform
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from algorithms.raster import RasterPlacer, nest
from nesting.constraints import check
from nesting.model import Instance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, nargs="+", default=[100, 200, 400])
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("-o", "--output", type=Path, default=ROOT / "results/raster_resolution.csv")
    args = parser.parse_args()
    if args.repeat <= 0 or any(rows <= 0 for rows in args.rows):
        parser.error("rows와 repeat는 양의 정수여야 합니다")
    paths = [
        ROOT / line.split("#")[0].strip()
        for line in (ROOT / "experiments/selected.txt").read_text(encoding="utf-8").splitlines()
        if line.split("#")[0].strip()
    ]
    results = []
    failed = False
    for path in paths:
        inst = Instance.load(path)
        for rows in args.rows:
            sols = [nest(inst, rows=rows) for _ in range(args.repeat)]
            sol = sols[0]
            errors = check(inst, sol, "raster", RasterPlacer.REQUIRED_COUNTERS)
            if any(s.placements != sol.placements for s in sols[1:]):
                errors.append("반복 실행 결과가 다름")
            failed |= bool(errors)
            times = [s.stats["time_place_ms"] for s in sols]
            result = {
                "instance": inst.name,
                "rows": rows,
                "cell_size": sol.stats["cell_size"],
                "length": sol.length,
                "utilization_pct": sol.utilization * 100,
                "time_ms_mean": statistics.mean(times),
                "time_ms_sd": statistics.stdev(times) if args.repeat > 1 else 0,
                "time_feasible_ms_mean": statistics.mean(s.stats["time_feasible_ms"] for s in sols),
                "grid_checks": sol.stats["grid_checks"],
                "valid": not errors,
                "errors": "; ".join(errors),
                "repeat": args.repeat,
                "python": platform.python_version(),
            }
            results.append(result)
            print(
                f"{inst.name:10s} rows={rows:4d} L={sol.length:.6g} "
                f"U={sol.utilization * 100:.2f}% {statistics.mean(times):.1f}ms "
                f"{'INVALID: ' + '; '.join(errors) if errors else 'OK'}",
                flush=True,
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    print("saved", args.output)
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
