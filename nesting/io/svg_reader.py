"""SVG 도면 → 팀 공통 Instance (svgelements 사용, 파싱만 라이브러리에 맡긴다).

- rect/circle/ellipse/polygon/polyline/path 모두 경로로 바꾼 뒤 transform을 적용한다.
- 곡선(베지어, 호)은 flatten_tol(px) 오차 수준으로 꺾은선 근사.
- SVG는 y축이 아래로 +이므로 y를 뒤집는다.
- svgelements는 길이를 px(96dpi)로 계산한다. unit="mm"이면 mm로 환산한다.
- id 또는 class가 sheet_id인 요소(사각형)가 있으면 그 높이를 원판 폭으로 쓴다.
"""

from __future__ import annotations

import math
from pathlib import Path

from svgelements import SVG, Close, Line, Move, Shape
from svgelements import Path as SPath

from .. import geometry as g
from ..model import Instance
from .common import chain_segments, loops_to_items

PX_PER = {"px": 1.0, "mm": 96 / 25.4, "cm": 96 / 2.54, "in": 96.0}


def _sample(seg, tol: float) -> list[list[float]]:
    """세그먼트 끝점까지의 점들(시작점 제외)."""
    if isinstance(seg, (Line, Close)):
        return [[seg.end.x, seg.end.y]]
    try:
        length = seg.length(error=1e-3)
    except Exception:
        length = math.dist((seg.start.x, seg.start.y), (seg.end.x, seg.end.y))
    n = max(2, min(200, int(math.ceil(math.sqrt(max(length, 1e-9) / max(tol, 1e-9)) * 2))))
    pts = []
    for i in range(1, n + 1):
        q = seg.point(i / n)
        pts.append([q.x, q.y])
    return pts


def _subpath_loops(shape_path: SPath, tol: float, join_tol: float):
    loops, segments = [], []
    for sub in shape_path.as_subpaths():
        pts: list[list[float]] = []
        closed = False
        for seg in sub:
            if isinstance(seg, Move):
                pts = [[seg.end.x, seg.end.y]]
                continue
            if isinstance(seg, Close):
                closed = True
            pts.extend(_sample(seg, tol))
        if len(pts) < 2:
            continue
        if closed or (len(pts) > 2 and math.dist(pts[0], pts[-1]) <= join_tol):
            loops.append(g.strip_closing_point(pts, join_tol))
        else:
            segments.extend(zip(pts[:-1], pts[1:]))
    return loops, segments


def load_svg(
    path: str | Path,
    width: float | None = None,
    unit: str = "mm",
    sheet_id: str = "sheet",
    rotations: list[float] | None = None,
    merge_identical: bool = True,
    flatten_tol: float = 0.25,
    join_tol: float = 1e-3,
) -> Instance:
    path = Path(path)
    scale = 1.0 / PX_PER[unit]
    svg = SVG.parse(str(path), reify=True)
    loops, segments, sheet_loops = [], [], []
    for el in svg.elements():
        if not isinstance(el, Shape):
            continue
        is_sheet = el.id == sheet_id or sheet_id in str(el.values.get("class", "")).split()
        p = SPath(el)
        p.reify()
        ls, ss = _subpath_loops(p, flatten_tol, join_tol)
        if is_sheet:
            sheet_loops.extend(ls)
        else:
            loops.extend(ls)
            segments.extend(ss)
    chained, open_chains = chain_segments(segments, join_tol)
    loops += chained

    def conv(lp):  # px → unit, y 뒤집기
        return [[x * scale, -y * scale] for x, y in lp]

    loops = [conv(lp) for lp in loops]
    if width is None:
        if not sheet_loops:
            raise ValueError(f"원판 폭을 알 수 없음: width 인자를 주거나 id='{sheet_id}'인 사각형을 그려 두세요")
        _, miny, _, maxy = g.bbox(conv(max(sheet_loops, key=g.area)))
        width = maxy - miny
    items, report = loops_to_items(
        loops,
        rotations or [0.0, 90.0, 180.0, 270.0],
        merge_identical,
        tol=join_tol * scale if join_tol * scale > 1e-9 else 1e-6,
    )
    meta = {"converted_from": "svg", "flatten_tol_px": flatten_tol, "open_chains_dropped": open_chains, **report}
    return Instance(
        name=path.stem, sheet_width=float(width), items=items, unit=unit, source=f"svg:{path.name}", meta=meta
    )
