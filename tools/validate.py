"""solution JSON이 유효한지 검사한다 (docs/SPEC.md 4절).

python tools/validate.py data/instances/sparrow/fu.json results/fu_baseline.json
python tools/validate.py inst.json sol.json --spacing 0.5
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nesting.model import Instance, Solution  # noqa: E402
from nesting.validate import validate  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("instance")
    ap.add_argument("solution")
    ap.add_argument("--spacing", type=float, default=0.0, help="부품 간 최소 간격(kerf)")
    a = ap.parse_args()
    rep = validate(Instance.load(a.instance), Solution.load(a.solution), spacing=a.spacing)
    print(rep)
    sys.exit(0 if rep.ok else 1)


if __name__ == "__main__":
    main()
