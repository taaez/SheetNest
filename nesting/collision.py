"""팀 공통 겹침 판정 모듈. 모든 알고리즘은 반드시 이 모듈의 함수만 사용한다.

규칙 (docs/SPEC.md 4절)
- 두 부품의 '내부'가 겹치면 겹침이다. 변이나 꼭짓점끼리 맞닿는 것은 허용한다.
- 허용 오차 eps는 원판 폭에 비례한다: eps = REL_TOL * sheet_width (tolerance_for 참고).
- spacing(kerf)이 0보다 크면 두 부품 사이 거리가 spacing 미만일 때도 겹침으로 본다.

판정 순서
1) 바운딩 박스 사전 필터: 박스가 떨어져 있으면 즉시 False (대부분 여기서 끝난다)
2) 변끼리 '제대로' 교차(서로를 관통)하면 True
3) 관통이 없으면, 한쪽 경계 바로 안쪽 점이 다른 쪽 내부에 있는지 검사
   (포함 관계, 같은 위치에 겹친 경우 등을 잡는다)

계산량 측정: overlap()을 부를 때마다 STATS["overlap_checks"]가 1 늘어난다.
알고리즘은 시작할 때 reset_stats()를 부르고, 끝날 때 get_stats()를 Solution.stats에 넣는다.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from . import geometry as g

REL_TOL = 1e-6  # 원판 폭 대비 상대 허용 오차

STATS: dict[str, int] = {"overlap_checks": 0, "bbox_rejects": 0}


def reset_stats() -> None:
    for k in STATS:
        STATS[k] = 0


def get_stats() -> dict[str, int]:
    return dict(STATS)


def tolerance_for(sheet_width: float) -> float:
    return REL_TOL * sheet_width


class Shape:
    """원판 위에 놓인 부품 하나. 변환된 꼭짓점과 바운딩 박스를 미리 계산해 둔다."""

    __slots__ = ("pts", "minx", "miny", "maxx", "maxy")

    def __init__(self, pts: Sequence[Sequence[float]]):
        self.pts = [(float(p[0]), float(p[1])) for p in pts]
        xs = [p[0] for p in self.pts]
        ys = [p[1] for p in self.pts]
        self.minx, self.miny, self.maxx, self.maxy = min(xs), min(ys), max(xs), max(ys)

    @classmethod
    def placed(cls, polygon, rotation: float, x: float, y: float) -> Shape:
        return cls(g.transform(polygon, rotation, x, y))


# ---------------------------------------------------------------- 공개 함수
def overlap(a: Shape, b: Shape, eps: float, spacing: float = 0.0) -> bool:
    """알고리즘용 겹침 판정. 호출 횟수가 집계된다."""
    STATS["overlap_checks"] += 1
    return _overlap(a, b, eps, spacing)


def inside_sheet(s: Shape, sheet_width: float, eps: float) -> bool:
    """부품이 원판(0 ≤ x, 0 ≤ y ≤ W) 안에 있는지."""
    return s.minx >= -eps and s.miny >= -eps and s.maxy <= sheet_width + eps


def distance(a: Shape, b: Shape) -> float:
    """겹치지 않는 두 부품 사이 최소 거리 (꼭짓점-변 거리의 최솟값)."""
    return min(_min_vertex_edge_dist(a.pts, b.pts), _min_vertex_edge_dist(b.pts, a.pts))


# ---------------------------------------------------------------- 내부 구현
def _overlap(a: Shape, b: Shape, eps: float, spacing: float = 0.0) -> bool:
    gap = spacing - eps if spacing > 0 else -eps
    # 1) 바운딩 박스 필터: 박스 사이가 gap보다 멀면 겹칠 수 없음
    if a.maxx <= b.minx - gap or b.maxx <= a.minx - gap or a.maxy <= b.miny - gap or b.maxy <= a.miny - gap:
        STATS["bbox_rejects"] += 1
        return False
    if _interiors_overlap(a.pts, b.pts, eps):
        return True
    if spacing > 0:
        return distance(a, b) < spacing - eps
    return False


def _orient(o, a, b, eps) -> int:
    """점 b가 직선 oa의 왼쪽(+1)/오른쪽(-1)/위(0). 거리 기준 허용 오차."""
    dx, dy = a[0] - o[0], a[1] - o[1]
    cr = dx * (b[1] - o[1]) - dy * (b[0] - o[0])
    length = math.hypot(dx, dy)
    if length == 0:
        return 0
    d = cr / length
    return 1 if d > eps else (-1 if d < -eps else 0)


def _proper_cross(p1, p2, q1, q2, eps) -> bool:
    """두 선분이 서로를 관통하는지(끝점 접촉·일직선 겹침은 제외)."""
    o1 = _orient(p1, p2, q1, eps)
    o2 = _orient(p1, p2, q2, eps)
    o3 = _orient(q1, q2, p1, eps)
    o4 = _orient(q1, q2, p2, eps)
    return o1 * o2 < 0 and o3 * o4 < 0


def _point_in(p, poly, eps) -> int:
    """1=내부, 0=경계(eps 이내), -1=외부."""
    x, y = p
    n = len(poly)
    inside = False
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if _seg_dist(p, a, b) <= eps:
            return 0
        if (a[1] > y) != (b[1] > y):
            xi = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if xi > x:
                inside = not inside
    return 1 if inside else -1


def _seg_dist(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def _min_vertex_edge_dist(P, Q) -> float:
    best = math.inf
    n = len(Q)
    for p in P:
        for j in range(n):
            d = _seg_dist(p, Q[j], Q[(j + 1) % n])
            if d < best:
                best = d
    return best


def _inward_probes(P, Q, eps) -> list[tuple[float, float]]:
    """P의 각 변을 Q의 꼭짓점 위치에서 잘라, 조각마다 중점에서 P 안쪽으로 살짝 들어간 점.
    (P는 반시계 방향이므로 안쪽 = 진행 방향의 왼쪽)"""
    probes = []
    n = len(P)
    for i in range(n):
        a, b = P[i], P[(i + 1) % n]
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        if L <= eps:
            continue
        ts = [0.0, 1.0]
        for q in Q:
            if _seg_dist(q, a, b) <= eps:
                t = ((q[0] - a[0]) * dx + (q[1] - a[1]) * dy) / (L * L)
                if 0.0 < t < 1.0:
                    ts.append(t)
        ts.sort()
        nx, ny = -dy / L, dx / L
        for t0, t1 in zip(ts, ts[1:]):
            seg = (t1 - t0) * L
            if seg <= 2 * eps:
                continue
            tm = (t0 + t1) / 2
            delta = max(4 * eps, min(seg * 1e-3, L * 1e-3))
            probes.append((a[0] + dx * tm + nx * delta, a[1] + dy * tm + ny * delta))
    return probes


def _interiors_overlap(P, Q, eps) -> bool:
    n, m = len(P), len(Q)
    # 2) 변 관통 검사 (변의 박스가 겹칠 때만 정밀 계산)
    for i in range(n):
        p1, p2 = P[i], P[(i + 1) % n]
        pminx, pmaxx = (p1[0], p2[0]) if p1[0] < p2[0] else (p2[0], p1[0])
        pminy, pmaxy = (p1[1], p2[1]) if p1[1] < p2[1] else (p2[1], p1[1])
        for j in range(m):
            q1, q2 = Q[j], Q[(j + 1) % m]
            if (
                max(q1[0], q2[0]) < pminx
                or min(q1[0], q2[0]) > pmaxx
                or max(q1[1], q2[1]) < pminy
                or min(q1[1], q2[1]) > pmaxy
            ):
                continue
            if _proper_cross(p1, p2, q1, q2, eps):
                return True
    # 3) 관통이 없을 때: 꼭짓점·안쪽 점 포함 검사
    for p in P:
        if _point_in(p, Q, eps) == 1:
            return True
    for q in Q:
        if _point_in(q, P, eps) == 1:
            return True
    for pr in _inward_probes(P, Q, eps):
        if _point_in(pr, Q, eps) == 1:
            return True
    for pr in _inward_probes(Q, P, eps):
        if _point_in(pr, P, eps) == 1:
            return True
    return False
