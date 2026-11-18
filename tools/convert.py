"""도면/데이터 파일 → 팀 공통 instance JSON 변환 CLI.

예)
  python tools/convert.py data/raw/fu.json -o data/instances/fu.json            # sparrow JSON
  python tools/convert.py esicup/2d_irregular/shirts/shirts.xml -o out.json      # ESICUP XML
  python tools/convert.py parts.dxf --width 1200 -o parts.json                  # DXF
  python tools/convert.py parts.svg --unit mm --width 600 -o parts.json         # SVG
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nesting.io import load_any  # noqa: E402
from nesting.model import check_instance  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("-o", "--output", help="출력 JSON 경로 (생략 시 화면 출력)")
    ap.add_argument("--width", type=float, help="원판 폭 (DXF/SVG에서 필요)")
    ap.add_argument("--rotations", default=None, help="허용 회전, 예: 0,90,180,270 (DXF/SVG)")
    ap.add_argument("--unit", default="mm", help="SVG 길이 단위 px|mm|cm|in")
    ap.add_argument("--sheet-layer", help="DXF에서 원판 사각형이 그려진 레이어 이름")
    ap.add_argument("--no-merge", action="store_true", help="같은 모양 부품을 quantity로 합치지 않음")
    ap.add_argument("--flatten-tol", type=float, help="곡선 근사 허용 오차 (도면 단위)")
    ap.add_argument("--continuous-step", type=float, default=90.0, help="sparrow 자유 회전 → 이산 각도 간격")
    ap.add_argument("--name", help="인스턴스 이름 지정")
    a = ap.parse_args()

    ext = Path(a.input).suffix.lower()
    kw = {}
    if ext in (".dxf", ".svg"):
        kw["width"] = a.width
        kw["merge_identical"] = not a.no_merge
        if a.rotations:
            kw["rotations"] = [float(x) for x in a.rotations.split(",")]
        if a.flatten_tol:
            kw["flatten_tol"] = a.flatten_tol
        if ext == ".dxf" and a.sheet_layer:
            kw["sheet_layer"] = a.sheet_layer
        if ext == ".svg":
            kw["unit"] = a.unit
    elif ext == ".json":
        kw["continuous_step"] = a.continuous_step

    inst = load_any(a.input, **kw)
    if a.name:
        inst.name = a.name
    errs = check_instance(inst)
    if errs:
        print("[경고] 형식 검사 실패:", *errs, sep="\n  ", file=sys.stderr)
    print(f"{inst.name}: 부품 {len(inst.items)}종 / 총 {inst.total_quantity}개, 폭 {inst.sheet_width:g}, "
          f"면적합 {inst.total_area:.4g}, 길이 하한 {inst.length_lower_bound:.4g}", file=sys.stderr)
    if a.output:
        inst.save(a.output)
    else:
        print(json.dumps(inst.to_dict(), ensure_ascii=False, indent=1))
    sys.exit(1 if errs else 0)


if __name__ == "__main__":
    main()
