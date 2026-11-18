"""instance JSON의 부품들을 SVG 한 장에 격자로 그려 변환 결과를 눈으로 확인한다.
solution JSON을 함께 주면 원판 위 배치 결과를 그린다.

  python tools/preview.py data/instances/sparrow/fu.json -o fu_parts.svg
  python tools/preview.py inst.json --solution sol.json -o layout.svg
"""

import argparse
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nesting import geometry as g  # noqa: E402
from nesting.model import Instance, Solution  # noqa: E402

COLORS = ["#9DC3E6", "#F4B183", "#A9D18E", "#FFD966", "#C9A0DC", "#8FD3C7", "#F8A5A5", "#BFBFBF"]


def _path(poly, sx, sy, ox, oy, H):
    return "M " + " L ".join(f"{ox + x * sx:.2f},{H - (oy + y * sy):.2f}" for x, y in poly) + " Z"


def parts_svg(inst: Instance, cell=140, cols=6):
    n = len(inst.items)
    rows = math.ceil(n / cols)
    W, H = cols * cell, rows * cell + 30
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif">',
        f'<text x="8" y="20" font-size="14">{inst.name}: {n} types / {inst.total_quantity} pieces, '
        f"width {inst.sheet_width:g} (each cell scaled separately)</text>",
    ]
    for k, it in enumerate(inst.items):
        cx, cy = (k % cols) * cell, (k // cols) * cell + 30
        _, _, w, h = g.bbox(it.polygon)
        s = (cell - 40) / max(w, h, 1e-9)
        pts = " ".join(f"{cx + 20 + x * s:.2f},{cy + cell - 20 - y * s:.2f}" for x, y in it.polygon)
        out.append(f'<polygon points="{pts}" fill="{COLORS[k % len(COLORS)]}" stroke="#1F3864" stroke-width="1"/>')
        out.append(f'<text x="{cx + 6}" y="{cy + 14}" font-size="11">id {it.id} x{it.quantity}</text>')
    out.append("</svg>")
    return "\n".join(out)


def layout_svg(inst: Instance, sol: Solution, px=900):
    s = px / max(sol.length, 1e-9)
    W, H = px + 20, inst.sheet_width * s + 50
    by_id = {it.id: it for it in inst.items}
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}" font-family="sans-serif">',
        f'<text x="10" y="18" font-size="13">{sol.algorithm}: length {sol.length:.3f}, '
        f"utilization {sol.utilization * 100:.1f}%</text>",
        f'<rect x="10" y="30" width="{sol.length * s:.2f}" height="{inst.sheet_width * s:.2f}" '
        f'fill="none" stroke="#555" stroke-dasharray="4 3"/>',
    ]
    for p in sol.placements:
        poly = g.transform(by_id[p.item].polygon, p.rotation, p.x, p.y)
        pts = " ".join(f"{10 + x * s:.2f},{30 + (inst.sheet_width - y) * s:.2f}" for x, y in poly)
        out.append(
            f'<polygon points="{pts}" fill="{COLORS[p.item % len(COLORS)]}" stroke="#1F3864" stroke-width="0.8"/>'
        )
    out.append("</svg>")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("instance")
    ap.add_argument("--solution")
    ap.add_argument("-o", "--output", required=True)
    a = ap.parse_args()
    inst = Instance.load(a.instance)
    svg = layout_svg(inst, Solution.load(a.solution)) if a.solution else parts_svg(inst)
    Path(a.output).write_text(svg, encoding="utf-8")
    print("saved", a.output)


if __name__ == "__main__":
    main()
