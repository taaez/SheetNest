"""sparrow·ESICUP 저장소를 내려받아 data/instances/ 아래에 공통 JSON으로 일괄 변환한다.

  git clone --depth 1 https://github.com/JeroenGar/sparrow ../sparrow
  git clone --depth 1 https://github.com/ESICUP/datasets ../esicup-datasets
  python tools/build_datasets.py --sparrow ../sparrow --esicup ../esicup-datasets

결과: data/instances/sparrow/*.json, data/instances/esicup/*.json, data/instances/index.csv
두 출처에 같은 인스턴스가 있으면 폭·부품 수·면적합이 일치하는지 교차 검증한다.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nesting import geometry as g  # noqa: E402
from nesting.io import load_esicup, load_sparrow  # noqa: E402
from nesting.model import check_instance  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
# ESICUP 2d_irregular 중 strip packing(원판 1장, 길이 최소화) 형식인 폴더
ESICUP_DIRS = [
    "albano",
    "blaz",
    "dagli",
    "dighe",
    "fu",
    "han",
    "jakobs",
    "mao",
    "marques",
    "poly",
    "shapes",
    "shirts",
    "swim",
    "trousers",
]


def row(inst, origin):
    convex = sum(1 for it in inst.items if g.is_convex(it.polygon))
    vmax = max(len(it.polygon) for it in inst.items)
    rots = sorted({r for it in inst.items for r in it.rotations})
    return {
        "source": origin,
        "name": inst.name,
        "types": len(inst.items),
        "pieces": inst.total_quantity,
        "nonconvex_types": len(inst.items) - convex,
        "max_vertices": vmax,
        "width": round(inst.sheet_width, 4),
        "total_area": round(inst.total_area, 4),
        "length_lower_bound": round(inst.length_lower_bound, 4),
        "rotations": " ".join(f"{r:g}" for r in rots),
        "errors": len(check_instance(inst)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sparrow", type=Path, help="sparrow 저장소 경로")
    ap.add_argument("--esicup", type=Path, help="ESICUP datasets 저장소 경로")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "instances")
    a = ap.parse_args()
    rows, by_name = [], {}

    if a.sparrow:
        for f in sorted((a.sparrow / "data" / "input").glob("*.json")):
            inst = load_sparrow(f)
            inst.save(a.out / "sparrow" / f.name)
            r = row(inst, "sparrow")
            rows.append(r)
            by_name.setdefault(r["name"], {})["sparrow"] = r
    if a.esicup:
        base = a.esicup / "2d_irregular"
        for d in ESICUP_DIRS:
            for f in sorted((base / d).glob("*.xml")):
                inst = load_esicup(f)
                inst.save(a.out / "esicup" / f"{f.stem}.json")
                r = row(inst, "esicup")
                rows.append(r)
                by_name.setdefault(r["name"], {})["esicup"] = r

    a.out.mkdir(parents=True, exist_ok=True)
    with open(a.out / "index.csv", "w", newline="", encoding="utf-8") as fp:
        w = csv.DictWriter(fp, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"변환 {len(rows)}개 → {a.out}")
    bad = [r for r in rows if r["errors"]]
    if bad:
        print("형식 오류가 있는 인스턴스:", ", ".join(f"{r['source']}/{r['name']}" for r in bad))
    print("\n[교차 검증] 두 출처에 모두 있는 인스턴스")
    for name, s in sorted(by_name.items()):
        if "sparrow" in s and "esicup" in s:
            p, e = s["sparrow"], s["esicup"]
            ok = (
                p["pieces"] == e["pieces"]
                and abs(p["width"] - e["width"]) / e["width"] < 1e-3
                and abs(p["total_area"] - e["total_area"]) / e["total_area"] < 1e-3
            )
            print(
                f"  {name:10s} {'일치' if ok else '불일치'}  pieces {p['pieces']}/{e['pieces']}  "
                f"width {p['width']}/{e['width']}  area {p['total_area']}/{e['total_area']}"
            )


if __name__ == "__main__":
    main()
