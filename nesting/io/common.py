"""도면(DXF/SVG)에서 뽑은 닫힌 루프들을 부품(Item) 목록으로 바꾸는 공통 처리."""

from __future__ import annotations

import math
from collections.abc import Sequence

from .. import geometry as g
from ..model import Item

Loop = list[list[float]]


def chain_segments(segments: list[tuple[Sequence[float], Sequence[float]]], tol: float) -> tuple[list[Loop], int]:
    """끊어진 선분(LINE, ARC 조각 등)을 끝점 일치로 이어 닫힌 루프를 만든다.
    반환: (닫힌 루프 목록, 닫히지 못하고 버려진 체인 수)"""
    segs = [(list(a), list(b)) for a, b in segments if math.dist(a, b) > tol]
    used = [False] * len(segs)
    loops: list[Loop] = []
    open_chains = 0

    def close(p, q):
        return math.dist(p, q) <= tol

    for i in range(len(segs)):
        if used[i]:
            continue
        used[i] = True
        chain = [segs[i][0], segs[i][1]]
        grown = True
        while grown and not close(chain[0], chain[-1]):
            grown = False
            for j in range(len(segs)):
                if used[j]:
                    continue
                a, b = segs[j]
                if close(chain[-1], a):
                    chain.append(b)
                elif close(chain[-1], b):
                    chain.append(a)
                elif close(chain[0], b):
                    chain.insert(0, a)
                elif close(chain[0], a):
                    chain.insert(0, b)
                else:
                    continue
                used[j] = True
                grown = True
                break
        if len(chain) >= 4 and close(chain[0], chain[-1]):
            loops.append(chain[:-1])
        else:
            open_chains += 1
    return loops, open_chains


def loops_to_items(
    loops: list[Loop], default_rotations: list[float], merge_identical: bool, tol: float = 1e-6
) -> tuple[list[Item], dict]:
    """루프 → 부품. 다른 루프 안에 들어 있는 루프는 구멍으로 보고 제외한다(v1은 구멍 미지원).
    merge_identical=True면 (회전 없이) 같은 모양을 quantity로 합친다."""
    report = {"loops": len(loops), "holes_ignored": 0, "degenerate": 0, "merged": 0}
    polys = []
    for lp in loops:
        s = g.simplify(lp, tol)
        if len(s) < 3 or g.area(s) <= tol:
            report["degenerate"] += 1
            continue
        polys.append(s)

    # 바깥 루프 판별: 다른(더 큰) 루프 내부에 있는 루프는 구멍
    order = sorted(range(len(polys)), key=lambda i: -g.area(polys[i]))
    outers: list[Loop] = []
    for idx in order:
        p = polys[idx]
        probe = _interior_probe(p)
        if any(g.area(o) > g.area(p) and g.point_in_polygon(probe, o) == 1 for o in outers):
            report["holes_ignored"] += 1
            continue
        outers.append(p)

    items: list[Item] = []
    for p in outers:
        norm = g.normalize(p, tol)
        if merge_identical:
            hit = next((it for it in items if g.same_shape(it.polygon, norm, tol * 10)), None)
            if hit:
                hit.quantity += 1
                report["merged"] += 1
                continue
        items.append(Item(id=len(items), polygon=norm, quantity=1, rotations=list(default_rotations)))
    return items, report


def _interior_probe(poly: Loop) -> list[float]:
    """다각형 내부의 한 점(구멍 판정용). 꼭짓점 근처를 조금씩 안쪽으로 찔러 본다."""
    n = len(poly)
    for i in range(n):
        a, b, c = poly[i - 1], poly[i], poly[(i + 1) % n]
        mx, my = (a[0] + c[0]) / 2, (a[1] + c[1]) / 2
        for t in (0.01, 0.1, 0.5):
            q = [b[0] + (mx - b[0]) * t, b[1] + (my - b[1]) * t]
            if g.point_in_polygon(q, poly) == 1:
                return q
    return poly[0]
