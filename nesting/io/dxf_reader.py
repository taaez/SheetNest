"""DXF 도면 → 팀 공통 Instance (ezdxf 사용, 파싱만 라이브러리에 맡긴다).

- 블록(INSERT)은 분해해서 읽는다.
- LWPOLYLINE/POLYLINE/CIRCLE/ELLIPSE/SPLINE 등 닫힌 도형은 그대로 루프로,
  LINE/ARC 등 열린 조각은 끝점을 이어 루프로 만든다.
- 곡선은 flatten_tol(도면 단위) 오차로 꺾은선 근사.
- 다른 루프 안의 루프는 구멍으로 보고 제외(v1 미지원, meta에 개수 기록).
- 원판 폭은 도면에 없으므로 인자로 받거나, sheet_layer 레이어의 사각형 높이로 정한다.
"""

from __future__ import annotations

from pathlib import Path

import ezdxf
from ezdxf import path as ezpath
from ezdxf.disassemble import recursive_decompose

from .. import geometry as g
from ..model import Instance
from .common import chain_segments, loops_to_items

_INSUNITS = {0: None, 1: "in", 2: "ft", 4: "mm", 5: "cm", 6: "m"}
_SUPPORTED = {"LWPOLYLINE", "POLYLINE", "LINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE"}


def load_dxf(
    path: str | Path,
    width: float | None = None,
    sheet_layer: str | None = None,
    rotations: list[float] | None = None,
    merge_identical: bool = True,
    flatten_tol: float = 0.1,
    join_tol: float = 1e-3,
    layers: list[str] | None = None,
) -> Instance:
    path = Path(path)
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    closed_loops, segments, sheet_loops, skipped = [], [], [], {}

    for e in recursive_decompose(msp):
        t = e.dxftype()
        if t not in _SUPPORTED:
            skipped[t] = skipped.get(t, 0) + 1
            continue
        layer = e.dxf.get("layer", "0")
        if layers and layer not in layers and layer != sheet_layer:
            continue
        try:
            p = ezpath.make_path(e)
        except (TypeError, ValueError):
            skipped[t] = skipped.get(t, 0) + 1
            continue
        pts = [[v.x, v.y] for v in p.flattening(flatten_tol)]
        if len(pts) < 2:
            continue
        is_closed = p.is_closed or (len(pts) > 2 and _close(pts[0], pts[-1], join_tol))
        target = sheet_loops if (sheet_layer and layer == sheet_layer) else None
        if is_closed:
            (target if target is not None else closed_loops).append(g.strip_closing_point(pts, join_tol))
        elif target is None:
            segments.extend(zip(pts[:-1], pts[1:]))

    chained, open_chains = chain_segments(segments, join_tol)
    loops = closed_loops + chained

    if width is None:
        if not sheet_loops:
            raise ValueError("원판 폭을 알 수 없음: width 인자를 주거나 sheet_layer에 사각형을 그려 두세요")
        _, miny, _, maxy = g.bbox(max(sheet_loops, key=g.area))
        width = maxy - miny

    items, report = loops_to_items(loops, rotations or [0.0, 90.0, 180.0, 270.0], merge_identical, tol=join_tol)
    unit = _INSUNITS.get(doc.header.get("$INSUNITS", 0))
    meta = {
        "converted_from": "dxf",
        "flatten_tol": flatten_tol,
        "open_chains_dropped": open_chains,
        "skipped_entities": skipped,
        **report,
    }
    return Instance(
        name=path.stem, sheet_width=float(width), items=items, unit=unit, source=f"dxf:{path.name}", meta=meta
    )


def _close(a, b, tol):
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol
