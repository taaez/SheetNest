"""NFP(No-Fit Polygon) 기반 Bottom-Left 위치 계산 (NFPPlacer.place()가 쓰는 핵심 계산).

가능 위치 계산 방법 2. 겹침을 후보 위치마다 직접 판정하지 않고, '겹치게 되는 기준점 영역'(NFP)을
미리 만들어 두고 후보점이 그 영역 안에 있는지만 본다.

부품 하나를 놓는 과정 (순서와 회전은 nesting.sequence.fixed_sequence로 고정)
1) IFP: 부품이 원판 안에 들어가는 이동량 영역. 원판이 띠 모양이므로 직사각형
   x ≥ xlo, ylo ≤ y ≤ yhi 이다 (오른쪽은 열려 있음).
2) 이미 놓인 부품마다 NFP를 캐시에서 꺼내 그 부품 위치로 옮긴다.
   오목 부품은 볼록 조각으로 나눠 두었으므로 NFP도 '조각 쌍마다 하나'인 볼록 다각형들이다.
   이동량 t가 어느 조각 NFP의 내부에 있으면 겹침, 모든 조각 NFP의 밖(경계 포함)이면 겹치지 않는다.
   그래서 NFP 합집합을 직접 계산할 필요가 없다.
3) 후보점: IFP 꼭짓점, NFP 꼭짓점, NFP 변과 IFP 경계의 교점, NFP 변끼리의 교점.
   Bottom-Left 해는 '가능 영역'의 꼭짓점이므로 이 후보 안에 반드시 있다.
4) 후보를 (x, y) 오름차순으로 판정해 첫 번째 가능한 점을 고른다.
   변끼리의 교점은 개수가 많으므로, 먼저 1)~3)의 다른 후보로 답 (x*, y*)를 구한 뒤
   x*보다 왼쪽에 생길 수 있는 교점만 계산해서 더 좋은 점이 있는지 확인한다.

결정적 알고리즘이다. 같은 순서면 항상 같은 결과가 나온다.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from nesting import collision as c
from nesting import geometry as g
from nesting.model import Instance

from .geometry_nfp import convex_decompose, nfp_convex


class _NFP:
    """원판 위로 옮긴 볼록 NFP 하나. 내부 판정용 변 법선과 바운딩 박스를 미리 계산한다."""

    __slots__ = ("pts", "minx", "miny", "maxx", "maxy", "edges", "segs", "live_v", "live_e", "grp")

    def __init__(self, pts: Sequence[tuple[float, float]], dx: float, dy: float, live_v=None, live_e=None, grp=0):
        self.pts = [(x + dx, y + dy) for x, y in pts]
        # live_v / live_e: 같은 부품 쌍의 다른 조각 NFP 안에 완전히 묻혀 후보가 될 수 없는 꼭짓점·변은 False
        self.live_v = live_v
        self.live_e = live_e
        self.grp = grp  # 어느 놓인 부품에서 나온 NFP인가 (같은 부품의 NFP끼리 교점은 캐시에 있음)
        xs = [p[0] for p in self.pts]
        ys = [p[1] for p in self.pts]
        self.minx, self.miny, self.maxx, self.maxy = min(xs), min(ys), max(xs), max(ys)
        # 반시계 다각형의 변 (a → b)에 대해 안쪽 단위 법선은 (−dy, dx) / 길이
        edges = []
        segs = []
        n = len(self.pts)
        for i in range(n):
            ax, ay = self.pts[i]
            bx, by = self.pts[(i + 1) % n]
            ex, ey = bx - ax, by - ay
            ln = math.hypot(ex, ey) or 1.0
            edges.append((ax, ay, -ey / ln, ex / ln))
            # 교점 계산용: 시작점, 방향, 변의 바운딩 박스 (묻힌 변은 뺀다)
            if live_e is None or live_e[i]:
                segs.append((ax, ay, ex, ey, min(ax, bx), max(ax, bx), min(ay, by), max(ay, by)))
        self.edges = edges
        self.segs = segs

    def strictly_inside(self, x: float, y: float, tol: float) -> bool:
        """점이 내부에 있고 모든 변에서 tol보다 멀리 떨어져 있으면 True (경계 근처는 맞닿음으로 허용)."""
        for ax, ay, nx, ny in self.edges:
            if (x - ax) * nx + (y - ay) * ny <= tol:
                return False
        return True


class NFPCore:
    """놓인 부품 기록, NFP 캐시, Bottom-Left 위치 계산. 시간 측정은 하지 않는다(공통 틀이 한다)."""

    def __init__(self, inst: Instance):
        self.inst = inst
        self.W = inst.sheet_width
        self.eps = c.tolerance_for(self.W)
        # 내부 판정 여유: 검증기 허용 오차의 절반만 써서 안전하게
        self.tol = 0.5 * self.eps
        self.nfp_computed = 0
        self.nfp_cache_hits = 0
        self.candidate_evals = 0
        self._state = None  # 지금 놓는 부품 종류의 NFP 목록 (_moving_state)
        self.placed: list[tuple[int, float, float, float]] = []  # (부품, 회전, x, y)
        self._prev: dict[tuple[int, float], tuple[float, float]] = {}
        self._cache: dict[tuple[int, float, int, float], list] = {}
        # 부품마다 볼록 분할은 한 번만 하고, 회전은 조각을 돌려서 만든다 (회전해도 볼록·반시계 유지)
        self._pieces: dict[tuple[int, float], list[list[tuple[float, float]]]] = {}
        self._bbox: dict[tuple[int, float], tuple[float, float, float, float]] = {}
        self.n_pieces: dict[int, int] = {}
        for it in inst.items:
            base = convex_decompose([(p[0], p[1]) for p in it.polygon])
            self.n_pieces[it.id] = len(base)
            for r in it.rotations:
                self._pieces[(it.id, r)] = [[(q[0], q[1]) for q in g.rotate(pc, r)] for pc in base]
                self._bbox[(it.id, r)] = g.bbox(g.rotate(it.polygon, r))

    # ------------------------------------------------------------ NFP 캐시
    def _nfps(self, a: int, ra: float, b: int, rb: float):
        """(조각 NFP 목록, 같은 부품 쌍의 조각 NFP끼리 교점 중 후보가 될 수 있는 점). 부품 쌍마다 한 번 계산."""
        key = (a, ra, b, rb)
        hit = self._cache.get(key)
        if hit is not None:
            self.nfp_cache_hits += 1
            return hit
        polys = [nfp_convex(pa, pb) for pa in self._pieces[(a, ra)] for pb in self._pieces[(b, rb)]]
        self.nfp_computed += len(polys)
        out = (_prune(polys, self.tol), _inner_points(polys, self.tol, self.W))
        self._cache[key] = out
        return out

    # ------------------------------------------------------------ 배치
    def best_position(self, item: int, rot: float) -> tuple[float, float]:
        """부품 item을 회전 rot으로 놓을 Bottom-Left 위치 (x, y). 회전한 다각형에 (x, y)를 더한 것이 최종 위치."""
        minx, miny, maxx, maxy = self._bbox[(item, rot)]
        if maxy - miny > self.W + self.eps:
            raise ValueError(f"item {item} 회전 {rot}: 원판 폭보다 높음")
        return self._best_position(item, rot, self.placed, self._prev.get((item, rot)))

    def record(self, item: int, rot: float, x: float, y: float) -> None:
        """놓은 부품을 기록한다. 같은 부품·회전의 직전 위치도 기억해 다음 사본의 탐색 하한으로 쓴다.
        (부품이 늘수록 가능 영역은 줄기만 하므로 다음 사본의 Bottom-Left 위치는 이 점보다 앞설 수 없다)"""
        self.placed.append((item, rot, x, y))
        self._prev[(item, rot)] = (x, y)

    def _moving_state(self, item: int, rot: float, placed) -> tuple[list[_NFP], _Grid]:
        """놓을 부품(item, rot)에 대한 NFP 목록과 격자. 같은 부품의 사본이 이어서 놓이므로
        이전 사본 때 만든 것을 그대로 두고 새로 놓인 부품의 NFP만 덧붙인다."""
        key = (item, rot)
        st = self._state if self._state is not None and self._state[0] == key else None
        if st is None:
            st = [key, 0, [], None, []]
            self._state = st
        _, n_done, nfps, grid, inner = st
        new = []
        for g_id, (pi, pr, px, py) in enumerate(placed[n_done:], start=n_done):
            entries, pts_in = self._nfps(pi, pr, item, rot)
            for pts, lv, le in entries:
                new.append(_NFP(pts, px, py, lv, le, g_id))
            inner.extend((x + px, y + py) for x, y in pts_in)
        nfps.extend(new)
        if grid is None:
            grid = _Grid(nfps, self.W)
        else:
            grid.add_all(new)
        st[1], st[3] = len(placed), grid
        return nfps, grid, inner

    def _best_position(self, item: int, rot: float, placed, floor=None) -> tuple[float, float]:
        minx, miny, maxx, maxy = self._bbox[(item, rot)]
        # 1) IFP: 회전된 부품을 (x, y)만큼 옮겼을 때 원판 안에 있는 영역
        xlo, ylo, yhi = -minx, -miny, self.W - maxy
        if yhi < ylo:  # 폭과 거의 같은 부품: 수치 오차 보정
            yhi = ylo
        if not placed:
            return xlo, ylo

        # 2) 놓인 부품마다 NFP를 옮겨 둔다
        nfps, grid, inner = self._moving_state(item, rot, placed)
        eps, tol = self.eps, self.tol
        lo = floor if floor is not None else (-math.inf, -math.inf)  # 이보다 앞선 후보는 볼 필요 없음

        def in_ifp(x, y):
            return x >= xlo - eps and ylo - eps <= y <= yhi + eps

        last = [None]  # 직전 후보를 막은 NFP. 후보를 정렬된 순서로 보므로 다음 후보도 막을 가능성이 크다

        def feasible(x, y) -> bool:
            self.candidate_evals += 1
            f = last[0]
            if f is not None and f.minx < x < f.maxx and f.miny < y < f.maxy and f.strictly_inside(x, y, tol):
                return False
            for f in grid.at(x, y):
                if f.minx < x < f.maxx and f.miny < y < f.maxy and f.strictly_inside(x, y, tol):
                    last[0] = f
                    return False
            return True

        def clamp(x, y):
            return max(x, xlo), min(max(y, ylo), yhi)

        # 3) 교점을 뺀 후보: IFP 꼭짓점, NFP 꼭짓점, NFP 변과 IFP 경계(y = ylo, y = yhi, x = xlo)의 교점
        cands: list[tuple[float, float]] = [(xlo, ylo), (xlo, yhi)]
        cands.extend(q for q in inner if in_ifp(*q))  # 같은 부품의 조각 NFP끼리 교점 (캐시)
        for f in nfps:
            P = f.pts
            n = len(P)
            for i in range(n):
                ax, ay = P[i]
                bx, by = P[(i + 1) % n]
                if (f.live_v is None or f.live_v[i]) and in_ifp(ax, ay):
                    cands.append((ax, ay))
                for yl in (ylo, yhi):
                    if (ay - yl) * (by - yl) < 0:
                        x = ax + (yl - ay) * (bx - ax) / (by - ay)
                        if x >= xlo - eps:
                            cands.append((x, yl))
                if (ax - xlo) * (bx - xlo) < 0:
                    y = ay + (xlo - ax) * (by - ay) / (bx - ax)
                    if ylo - eps <= y <= yhi + eps:
                        cands.append((xlo, y))

        best = None
        for x, y in sorted(set(clamp(x, y) for x, y in cands)):
            if (x, y) > lo and feasible(x, y):
                best = (x, y)
                break
        if best is None:  # 이론상 도달하지 않음: 모든 NFP 오른쪽은 항상 비어 있다
            best = (max(f.maxx for f in nfps), ylo)

        # 4) NFP 변끼리의 교점 중 best보다 앞서는 것만 확인한다 (스위프).
        #    살아 있는 변(다른 조각 NFP에 묻히지 않은 변)을 왼쪽 끝 x 순으로 훑는다. 두 변의 교점 x는
        #    나중에 본 변의 왼쪽 끝 x 이상이므로, 그 값이 best x보다 커지면 멈춘다.
        #    앞서 본 변은 y 칸별 목록에 넣어 두고, 오른쪽 끝이 지금 변의 왼쪽 끝보다 왼쪽이면 지운다.
        #    교점은 모아 두지 않고 바로 판정해 메모리를 쓰지 않는다. 더 좋은 점을 찾을 때마다 best가
        #    당겨지므로 탐색 범위도 함께 줄어든다. 같은 놓인 부품에서 나온 NFP끼리의 교점은 부품 쌍마다
        #    미리 구해 캐시해 두었으므로(_inner_points, 3단계 후보에 포함) 여기서는 다른 부품끼리만 본다.
        segs = [(e, f.grp) for f in nfps for e in f.segs]
        if not segs:
            return best
        cs = max(sum(max(e[5] - e[4], e[7] - e[6]) for e, _ in segs) / len(segs), self.W / 4096)
        segs.sort(key=lambda ek: ek[0][4])
        active: dict[int, list] = {}
        for eb, kb in segs:
            b0, b1, b2, b3 = eb[4], eb[5], eb[6], eb[7]
            if b0 > best[0]:
                break
            iy0, iy1 = math.floor(b2 / cs), math.floor(b3 / cs)
            if b1 >= lo[0]:
                seen = set()
                for iy in range(iy0, iy1 + 1):
                    lst = active.get(iy)
                    if not lst:
                        continue
                    keep = [ak for ak in lst if ak[0][5] >= b0]
                    active[iy] = keep
                    for ea, ka in keep:
                        if ka == kb or ea[7] < b2 or b3 < ea[6] or ea[5] < lo[0] or id(ea) in seen:
                            continue
                        seen.add(id(ea))
                        p = _seg_intersection(ea, eb)
                        if p is None:
                            continue
                        x, y = p
                        if x <= best[0] and in_ifp(x, y):
                            x, y = clamp(x, y)
                            if lo < (x, y) < best and feasible(x, y):
                                best = (x, y)
            for iy in range(iy0, iy1 + 1):
                active.setdefault(iy, []).append((eb, kb))
        return best


def _prune(polys: list[list[tuple[float, float]]], tol: float) -> list:
    """같은 부품 쌍에서 나온 조각 NFP들 사이에서, 다른 조각 NFP 안에 완전히 묻힌 꼭짓점과 변을 표시한다.

    꼭짓점이 어떤 조각 NFP의 내부에 있으면 그 점은 절대 가능 위치가 아니다.
    변의 두 끝점이 같은 볼록 NFP의 내부에 있으면 변 전체가 그 안에 있으므로(볼록성) 교점 후보에서 뺀다.
    부품 쌍마다 한 번만 계산해 캐시하므로, 배치할 때마다 반복되는 교점 계산이 크게 줄어든다.
    """
    objs = [_NFP(p, 0.0, 0.0) for p in polys]
    if len(objs) == 1:
        return [(polys[0], None, None)]
    grid = _Grid(objs, max(max(o.maxx for o in objs) - min(o.minx for o in objs), 1e-12))
    out = []
    for k, o in enumerate(objs):
        P = o.pts
        n = len(P)
        # 꼭짓점마다 그 점을 내부에 품은 다른 NFP를 하나만 찾는다 (없으면 None). 직전에 찾은 것을 먼저 본다
        cover = []
        last = None
        for x, y in P:
            hit = None
            if last is not None and last.minx < x < last.maxx and last.miny < y < last.maxy:
                if last.strictly_inside(x, y, tol):
                    hit = last
            if hit is None:
                for q in grid.at(x, y):
                    if q is not o and q.minx < x < q.maxx and q.miny < y < q.maxy and q.strictly_inside(x, y, tol):
                        hit = q
                        break
            cover.append(hit)
            if hit is not None:
                last = hit
        live_v = [h is None for h in cover]
        live_e = []
        for i in range(n):
            j = (i + 1) % n
            h1, h2 = cover[i], cover[j]
            dead = False
            if h1 is not None and h2 is not None:
                # 한 끝점을 품은 NFP가 다른 끝점도 품으면 변 전체가 그 안에 있다 (볼록)
                dead = h1 is h2 or h1.strictly_inside(*P[j], tol) or h2.strictly_inside(*P[i], tol)
            live_e.append(not dead)
        out.append((polys[k], live_v, live_e))
    return out


def _inner_points(polys: list[list[tuple[float, float]]], tol: float, W: float) -> list[tuple[float, float]]:
    """같은 부품 쌍에서 나온 조각 NFP끼리의 변 교점 중, 다른 조각 NFP 내부에 묻히지 않은 점 (상대 좌표).

    놓인 부품의 위치만큼 옮기면 그대로 후보점이 되므로, 배치할 때마다 다시 계산하지 않고 캐시한다.
    """
    if len(polys) < 2:
        return []
    entries = _prune(polys, tol)
    objs = [_NFP(p, 0.0, 0.0, lv, le, k) for k, (p, lv, le) in enumerate(entries)]
    grid = _Grid(objs, W)
    segs = [(e, o.grp) for o in objs for e in o.segs]
    if not segs:
        return []
    cs = max(sum(max(e[5] - e[4], e[7] - e[6]) for e, _ in segs) / len(segs), W / 4096)
    segs.sort(key=lambda ek: ek[0][4])
    active: dict[int, list] = {}
    out = set()
    last = None
    for eb, kb in segs:
        b0, b2, b3 = eb[4], eb[6], eb[7]
        iy0, iy1 = math.floor(b2 / cs), math.floor(b3 / cs)
        seen = set()
        for iy in range(iy0, iy1 + 1):
            lst = active.get(iy)
            if not lst:
                continue
            keep = [ak for ak in lst if ak[0][5] >= b0]
            active[iy] = keep
            for ea, ka in keep:
                if ka == kb or ea[7] < b2 or b3 < ea[6] or id(ea) in seen:
                    continue
                seen.add(id(ea))
                q = _seg_intersection(ea, eb)
                if q is None:
                    continue
                x, y = q
                if last is not None and last.minx < x < last.maxx and last.miny < y < last.maxy:
                    if last.strictly_inside(x, y, tol):
                        continue
                for f in grid.at(x, y):
                    if f.minx < x < f.maxx and f.miny < y < f.maxy and f.strictly_inside(x, y, tol):
                        last = f
                        break
                else:
                    out.add((x, y))
        for iy in range(iy0, iy1 + 1):
            active.setdefault(iy, []).append((eb, kb))
    return sorted(out)


class _Grid:
    """NFP 바운딩 박스를 격자 칸에 등록해, 점 하나가 들어갈 수 있는 NFP만 빠르게 찾는다."""

    def __init__(self, nfps: list[_NFP], W: float):
        self.nfps = nfps
        if nfps:
            avg = sum(max(f.maxx - f.minx, f.maxy - f.miny) for f in nfps) / len(nfps)
        else:
            avg = W
        # 칸 크기를 NFP 평균 크기로 잡아 NFP 하나가 몇 칸에만 등록되게 한다 (너무 작으면 메모리가 폭증)
        self.cs = max(avg, W / 64)
        self.objs: dict[tuple[int, int], list[_NFP]] = {}
        self.add_all(nfps)

    def add_all(self, nfps: list[_NFP]) -> None:
        cs = self.cs
        for f in nfps:
            for ix in range(math.floor(f.minx / cs), math.floor(f.maxx / cs) + 1):
                for iy in range(math.floor(f.miny / cs), math.floor(f.maxy / cs) + 1):
                    self.objs.setdefault((ix, iy), []).append(f)

    def at(self, x: float, y: float) -> list[_NFP]:
        return self.objs.get((math.floor(x / self.cs), math.floor(y / self.cs)), ())


def _seg_intersection(e1, e2):
    """변 두 개(시작점, 방향, 바운딩 박스 형식)의 교점. 평행하거나 만나지 않으면 None."""
    ax, ay, rx, ry = e1[0], e1[1], e1[2], e1[3]
    cx, cy, sx, sy = e2[0], e2[1], e2[2], e2[3]
    den = rx * sy - ry * sx
    if den == 0:
        return None
    qx, qy = cx - ax, cy - ay
    t = (qx * sy - qy * sx) / den
    if t < 0.0 or t > 1.0:
        return None
    u = (qx * ry - qy * rx) / den
    if u < 0.0 or u > 1.0:
        return None
    return ax + t * rx, ay + t * ry
