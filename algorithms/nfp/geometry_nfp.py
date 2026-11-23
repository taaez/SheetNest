"""NFP 계산에 필요한 기하 연산: 볼록 분할과 볼록 다각형의 민코프스키 합.

1) 볼록 분할
   오목 다각형은 NFP를 바로 구하기 어렵다. 그래서 먼저 귀 자르기(ear clipping)로
   삼각형으로 나누고, 이웃한 두 조각을 합쳐도 볼록이면 합친다(Hertel-Mehlhorn 방식).
   조각 수가 줄수록 NFP 개수(조각 수 x 조각 수)가 줄어 빨라진다.

2) 볼록 다각형 NFP
   고정 조각 P와 움직이는 조각 Q에 대해, Q의 기준점이 들어가면 겹치게 되는 영역은
   P ⊕ (−Q) (민코프스키 합)이다. 두 볼록 다각형의 변을 각도순으로 이어 붙여 O(n + m)에 구한다.

입력 다각형은 nesting.geometry.normalize를 거친 반시계(CCW) 단순 다각형이라고 가정한다.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

Pt = tuple[float, float]


def _cross(o: Pt, a: Pt, b: Pt) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _scale(poly: Sequence[Pt]) -> float:
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return max(max(xs) - min(xs), max(ys) - min(ys), 1e-12)


def drop_collinear(poly: list[Pt], tol: float) -> list[Pt]:
    """연속 중복점과 일직선 위 중간점을 지운다 (tol은 길이 단위)."""
    out = list(poly)
    changed = True
    while changed and len(out) > 3:
        changed = False
        n = len(out)
        for i in range(n):
            a, b, c = out[i - 1], out[i], out[(i + 1) % n]
            if math.dist(a, b) <= tol or abs(_cross(a, b, c)) <= tol * max(math.dist(a, c), 1e-12):
                out.pop(i)
                changed = True
                break
    return out


# ---------------------------------------------------------------- 1) 볼록 분할
def _triangulate(poly: Sequence[Pt]) -> list[tuple[int, int, int]]:
    """귀 자르기. CCW 단순 다각형 → 꼭짓점 번호 삼각형 목록 (n − 2개)."""
    n = len(poly)
    idx = list(range(n))
    tris: list[tuple[int, int, int]] = []
    tol = 1e-12 * _scale(poly) ** 2

    def is_ear(k: int) -> bool:
        m = len(idx)
        i0, i1, i2 = idx[(k - 1) % m], idx[k], idx[(k + 1) % m]
        a, b, c = poly[i0], poly[i1], poly[i2]
        if _cross(a, b, c) <= tol:  # 오목하거나 일직선인 꼭짓점은 귀가 아님
            return False
        for j in idx:
            if j in (i0, i1, i2):
                continue
            p = poly[j]
            # 삼각형 안(경계 포함)에 다른 꼭짓점이 있으면 귀가 아님
            if _cross(a, b, p) >= -tol and _cross(b, c, p) >= -tol and _cross(c, a, p) >= -tol:
                return False
        return True

    guard = 0
    while len(idx) > 3:
        m = len(idx)
        for k in range(m):
            if is_ear(k):
                tris.append((idx[(k - 1) % m], idx[k], idx[(k + 1) % m]))
                idx.pop(k)
                break
        else:
            # 수치 오차로 귀를 못 찾으면 가장 덜 오목한 꼭짓점을 자른다 (실제 데이터에서는 드묾)
            k = max(range(m), key=lambda k: _cross(poly[idx[(k - 1) % m]], poly[idx[k]], poly[idx[(k + 1) % m]]))
            tris.append((idx[(k - 1) % m], idx[k], idx[(k + 1) % m]))
            idx.pop(k)
        guard += 1
        if guard > 4 * n:
            break
    if len(idx) == 3:
        tris.append((idx[0], idx[1], idx[2]))
    return tris


def _is_convex_idx(poly: Sequence[Pt], piece: list[int], tol: float) -> bool:
    m = len(piece)
    for i in range(m):
        if _cross(poly[piece[i - 1]], poly[piece[i]], poly[piece[(i + 1) % m]]) < -tol:
            return False
    return True


def convex_decompose(poly: Sequence[Pt]) -> list[list[Pt]]:
    """CCW 단순 다각형을 볼록 조각(CCW) 목록으로 나눈다. 볼록이면 그대로 1개."""
    poly = [(float(x), float(y)) for x, y in poly]
    tol = 1e-12 * _scale(poly) ** 2
    if _is_convex_idx(poly, list(range(len(poly))), tol):
        return [poly]
    pieces: list[list[int] | None] = [list(t) for t in _triangulate(poly)]
    # 대각선(조각끼리 공유하는 변)을 하나씩 지워 보고, 합친 조각이 볼록이면 합친다
    merged = True
    while merged:
        merged = False
        owner: dict[tuple[int, int], int] = {}
        for pi, pc in enumerate(pieces):
            if pc is None:
                continue
            m = len(pc)
            for i in range(m):
                owner[(pc[i], pc[(i + 1) % m])] = pi
        for (u, v), pi in owner.items():
            pj = owner.get((v, u))
            if pj is None or pj == pi or pieces[pi] is None or pieces[pj] is None:
                continue
            a, b = pieces[pi], pieces[pj]
            # a에는 u→v, b에는 v→u가 있다. a를 v에서 시작해 u로 끝나게, b를 u에서 시작해 v로 끝나게 돌린다
            ia, ib = a.index(v), b.index(u)
            ra = a[ia:] + a[:ia]
            rb = b[ib:] + b[:ib]
            union = ra + rb[1:-1]
            if _is_convex_idx(poly, union, tol):
                pieces[pi] = union
                pieces[pj] = None
                merged = True
                break
    out = []
    for pc in pieces:
        if pc is None:
            continue
        pts = drop_collinear([poly[i] for i in pc], 1e-9 * _scale(poly))
        out.append(pts)
    return out


# ---------------------------------------------------------------- 2) 볼록 NFP (민코프스키 합)
def _start_index(poly: Sequence[Pt]) -> int:
    """y가 가장 작고, 같으면 x가 가장 작은 꼭짓점."""
    return min(range(len(poly)), key=lambda i: (poly[i][1], poly[i][0]))


def minkowski_convex(P: Sequence[Pt], Q: Sequence[Pt]) -> list[Pt]:
    """볼록 CCW 다각형 P ⊕ Q. 두 다각형의 변을 각도순으로 병합한다."""
    i0, j0 = _start_index(P), _start_index(Q)
    P = list(P[i0:]) + list(P[:i0])
    Q = list(Q[j0:]) + list(Q[:j0])
    n, m = len(P), len(Q)
    out: list[Pt] = []
    i = j = 0
    while i < n or j < m:
        out.append((P[i % n][0] + Q[j % m][0], P[i % n][1] + Q[j % m][1]))
        ep = (P[(i + 1) % n][0] - P[i % n][0], P[(i + 1) % n][1] - P[i % n][1])
        eq = (Q[(j + 1) % m][0] - Q[j % m][0], Q[(j + 1) % m][1] - Q[j % m][1])
        cr = ep[0] * eq[1] - ep[1] * eq[0]
        if j >= m or (i < n and cr > 0):
            i += 1
        elif i >= n or cr < 0:
            j += 1
        else:  # 평행한 변: 둘 다 전진
            i += 1
            j += 1
    return out


def nfp_convex(fixed: Sequence[Pt], moving: Sequence[Pt]) -> list[Pt]:
    """고정 조각 fixed(원점 기준)와 움직이는 조각 moving에 대한 NFP = fixed ⊕ (−moving).

    moving을 (x, y)만큼 옮겼을 때 두 조각의 내부가 겹친다 ⇔ (x, y)가 NFP의 '내부'에 있다.
    NFP 경계 위는 맞닿음(허용)이다.
    """
    neg = [(-x, -y) for x, y in moving]
    nfp = minkowski_convex(fixed, neg)
    return drop_collinear(nfp, 1e-9 * max(_scale(fixed), _scale(moving)))
