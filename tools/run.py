"""알고리즘 하나를 인스턴스 하나에 실행하고, 검증한 뒤 결과를 저장한다.

python tools/run.py baseline data/instances/sparrow/fu.json -o results/fu_baseline.json
python tools/run.py ga data/instances/sparrow/shirts.json --seed 3 --time-limit 60 -o results/x.json
python tools/run.py baseline experiments/selected.txt -o results/   # 선정 인스턴스 전체
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import algorithms  # noqa: E402
from nesting.model import Instance  # noqa: E402
from nesting.validate import validate  # noqa: E402


def targets(arg: str):
    p = Path(arg)
    if p.suffix == ".txt":
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.split("#")[0].strip()
            if line:
                yield ROOT / line
    else:
        yield p


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("algorithm", choices=list(algorithms.REGISTRY))
    ap.add_argument("instance", help="instance JSON 또는 목록 .txt")
    ap.add_argument("-o", "--output", help="결과 JSON 경로(인스턴스 1개) 또는 폴더(목록)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--time-limit", type=float)
    ap.add_argument("--spacing", type=float, default=0.0, help="검증 시 부품 간 최소 간격(kerf)")
    a = ap.parse_args()
    nest = algorithms.get(a.algorithm)
    failed = 0
    for path in targets(a.instance):
        inst = Instance.load(path)
        sol = nest(inst, seed=a.seed, time_limit_s=a.time_limit)
        rep = validate(inst, sol, spacing=a.spacing)
        failed += not rep.ok
        lb = inst.length_lower_bound
        print(
            f"{inst.name:10s} {a.algorithm}: L={sol.length:.6g} (하한 대비 +{(sol.length / lb - 1) * 100:.1f}%), "
            f"U={sol.utilization * 100:.2f}%, {sol.time_ms:.1f}ms, "
            f"overlap_checks={sol.stats.get('overlap_checks', 0)}  {'OK' if rep.ok else 'INVALID'}"
        )
        if not rep.ok:
            print(rep)
        if a.output:
            out = Path(a.output)
            if out.suffix != ".json":
                out = out / f"{inst.name}_{a.algorithm}_s{a.seed}.json"
            sol.save(out)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
