"""기본 기하 연산 (팀 공통 기하 코어의 출발점).

알고리즘 비교의 공정성을 위해 겹침 판정 등 핵심 기하 연산은
외부 라이브러리 없이 이 모듈에서 직접 구현해 모두가 공유한다.
좌표계: x는 원판 길이 방향(최소화 대상), y는 폭 방향, y축은 위쪽이 +.
다각형: [[x, y], ...] 꼭짓점 목록, 마지막 점이 첫 점과 같지 않음(닫지 않음).
"""
from __future__ import annotations

import math
from typing import List, Sequence, Tuple

Point = Tuple[float, float]
Polygon = List[List[float]]

EPS = 1e-9


def signed_area(poly: Sequence[Sequence[float]]) -> float:
    """신발끈 공식. 반시계(CCW)이면 양수."""
    s = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def area(poly: Sequence[Sequence[float]]) -> float:
    return abs(signed_area(poly))


def bbox(poly: Sequence[Sequence[float]]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return min(xs), min(ys), max(xs), max(ys)


def rotate(poly: Sequence[Sequence[float]], deg: float) -> Polygon:
    """원점 기준 반시계 방향 회전. 90도 배수는 부동소수 오차 없이 처리."""
    d = deg % 360
    if d == 0:
        return [[float(x), float(y)] for x, y in poly]
    if d == 90:
        return [[-y, x] for x, y in poly]
    if d == 180:
        return [[-x, -y] for x, y in poly]
    if d == 270:
        return [[y, -x] for x, y in poly]
    r = math.radians(d)
    c, s = math.cos(r), math.sin(r)
    return [[x * c - y * s, x * s + y * c] for x, y in poly]


def translate(poly: Sequence[Sequence[float]], dx: float, dy: float) -> Polygon:
    return [[x + dx, y + dy] for x, y in poly]


def transform(poly: Sequence[Sequence[float]], rotation: float, x: float, y: float) -> Polygon:
    """SPEC.md의 배치 변환: p' = R(rotation) * p + (x, y)."""
    return translate(rotate(poly, rotation), x, y)


def strip_closing_point(poly: Sequence[Sequence[float]], tol: float = 1e-9) -> Polygon:
    pts = [[float(p[0]), float(p[1])] for p in poly]
    if len(pts) > 1 and abs(pts[0][0] - pts[-1][0]) <= tol and abs(pts[0][1] - pts[-1][1]) <= tol:
        pts.pop()
    return pts


def _cross(o: Sequence[float], a: Sequence[float], b: Sequence[float]) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def simplify(poly: Sequence[Sequence[float]], tol: float = 1e-9) -> Polygon:
    """연속 중복점과 일직선 위 중간점을 제거한다."""
    pts = strip_closing_point(poly, tol)
    # 연속 중복점 제거
    out: Polygon = []
    for p in pts:
        if not out or abs(out[-1][0] - p[0]) > tol or abs(out[-1][1] - p[1]) > tol:
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) <= tol and abs(out[0][1] - out[-1][1]) <= tol:
        out.pop()
    # 일직선 점 제거 (반복)
    changed = True
    while changed and len(out) > 3:
        changed = False
        n = len(out)
        for i in range(n):
            a, b, c = out[i - 1], out[i], out[(i + 1) % n]
            scale = max(1.0, math.dist(a, c))
            if abs(_cross(a, b, c)) <= tol * scale:
                out.pop(i)
                changed = True
                break
    return out


def normalize(poly: Sequence[Sequence[float]], tol: float = 1e-9) -> Polygon:
    """정규화: 단순화 → 반시계 방향 → bbox 최솟값을 (0, 0)으로 이동 → 시작 꼭짓점 고정."""
    pts = simplify(poly, tol)
    if signed_area(pts) < 0:
        pts.reverse()
    minx, miny, _, _ = bbox(pts)
    out = [[round(x - minx, 9) + 0.0, round(y - miny, 9) + 0.0] for x, y in pts]
    # 시작 꼭짓점 고정: y가 가장 작고, 같으면 x가 가장 작은 점 (결과를 결정적으로 만들기 위함)
    k = min(range(len(out)), key=lambda i: (out[i][1], out[i][0]))
    return out[k:] + out[:k]


def on_segment(p: Sequence[float], a: Sequence[float], b: Sequence[float], eps: float = EPS) -> bool:
    return (abs(_cross(a, b, p)) <= eps
            and min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps
            and min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps)


def segments_intersect(a: Sequence[float], b: Sequence[float],
                       c: Sequence[float], d: Sequence[float], eps: float = EPS) -> bool:
    """선분 ab와 cd가 만나는지(접촉 포함). 교안 06-01 '두 선분의 상대위치'."""
    d1 = _cross(c, d, a)
    d2 = _cross(c, d, b)
    d3 = _cross(a, b, c)
    d4 = _cross(a, b, d)
    if ((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) and \
       ((d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps)):
        return True
    return (on_segment(a, c, d, eps) or on_segment(b, c, d, eps)
            or on_segment(c, a, b, eps) or on_segment(d, a, b, eps))


def is_simple(poly: Sequence[Sequence[float]]) -> bool:
    """자기 교차가 없는 단순 다각형인지 검사 (O(n^2))."""
    n = len(poly)
    if n < 3:
        return False
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or j == (i + 1) % n:
                continue  # 이웃 변은 꼭짓점을 공유하므로 제외
            c, d = poly[j], poly[(j + 1) % n]
            if segments_intersect(a, b, c, d):
                return False
    return True


def point_in_polygon(p: Sequence[float], poly: Sequence[Sequence[float]]) -> int:
    """점과 다각형의 상대위치 (교안 06-03). 1=내부, 0=경계, -1=외부. 반직선 교차법."""
    x, y = p
    n = len(poly)
    inside = False
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if on_segment(p, a, b):
            return 0
        if (a[1] > y) != (b[1] > y):
            xi = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if xi > x:
                inside = not inside
    return 1 if inside else -1


def is_convex(poly: Sequence[Sequence[float]]) -> bool:
    n = len(poly)
    sign = 0
    for i in range(n):
        c = _cross(poly[i], poly[(i + 1) % n], poly[(i + 2) % n])
        if abs(c) > EPS:
            s = 1 if c > 0 else -1
            if sign == 0:
                sign = s
            elif s != sign:
                return False
    return True


def same_shape(p: Sequence[Sequence[float]], q: Sequence[Sequence[float]], tol: float = 1e-6) -> bool:
    """정규화된 두 다각형이 (회전 없이) 같은 모양인지. 시작 꼭짓점이 달라도 인정."""
    if len(p) != len(q):
        return False
    n = len(p)
    for shift in range(n):
        if all(abs(p[i][0] - q[(i + shift) % n][0]) <= tol and abs(p[i][1] - q[(i + shift) % n][1]) <= tol
               for i in range(n)):
            return True
    return False
