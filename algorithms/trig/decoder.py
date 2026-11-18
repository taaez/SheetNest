"""삼각법(직접 판정) 기반 Bottom-Left 배치.

가능 위치 계산 방법 1. 부품을 다각형 그대로 두고, 후보 위치마다 이미 놓인 부품과
선분 교차·점 포함 검사(nesting.collision.overlap)로 겹침을 직접 판정한다.

부품 하나를 놓는 과정 (순서와 회전은 nesting.sequence.fixed_sequence로 고정)
1) 후보점 생성: 이미 놓인 부품들의 바운딩 박스 경계에 맞닿는 위치
   x 후보는 0과 각 부품의 오른쪽 끝, y 후보는 0, 각 부품의 위쪽 끝,
   각 부품의 아래쪽 끝에서 높이를 뺀 값, 원판 폭에서 높이를 뺀 값
2) Bottom-Left 선택: 후보를 x, y 오름차순으로 검사해 원판 안이고 겹치지 않는 첫 위치
3) 미끄러뜨리기(slide=True 기본): 아래로, 왼쪽으로 겹치기 직전까지 반복해서 민다(이진 탐색)

결정적 알고리즘이다. 같은 순서면 항상 같은 결과가 나온다.
시간 기록: time_feasible_ms(겹침 판정에 쓴 시간), time_place_ms(배치 전체 시간)
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from nesting import collision as c
from nesting import geometry as g
from nesting.model import Instance, Placement, Solution, make_solution


class TrigPlacer:
    def __init__(self, inst: Instance, slide: bool = True, slide_iters: int = 4, resolution: float | None = None):
        self.inst = inst
        self.W = inst.sheet_width
        self.eps = c.tolerance_for(self.W)
        self.slide = slide
        self.slide_iters = slide_iters
        # 미끄러뜨리기 이진 탐색의 최소 이동 단위 (기본: 원판 폭의 1/1000)
        self.res = resolution if resolution is not None else self.W * 1e-3
        self.t_feasible = 0.0
        self._rot: dict[tuple[int, float], tuple[list[list[float]], float, float, float, float]] = {}
        for it in inst.items:
            for r in it.rotations:
                poly = g.rotate(it.polygon, r)
                minx, miny, maxx, maxy = g.bbox(poly)
                self._rot[(it.id, r)] = (poly, minx, miny, maxx - minx, maxy - miny)

    def place_all(self, sequence: Sequence[tuple[int, float]]) -> list[Placement]:
        placed: list[c.Shape] = []
        placements: list[Placement] = []
        copies: dict[int, int] = {}
        for item, rot in sequence:
            poly, minx, miny, w, h = self._rot[(item, rot)]
            if h > self.W + self.eps:
                raise ValueError(f"item {item} 회전 {rot}: 원판 폭보다 높음")
            X, Y = self._first_feasible(poly, minx, miny, w, h, placed)
            if self.slide:
                X, Y = self._slide(poly, minx, miny, w, h, X, Y, placed)
            x, y = X - minx, Y - miny
            placed.append(c.Shape(g.translate(poly, x, y)))
            k = copies.get(item, 0)
            copies[item] = k + 1
            placements.append(Placement(item=item, copy=k, rotation=rot, x=x, y=y))
        return placements

    # ------------------------------------------------------------ 가능 위치 계산 (겹침 직접 판정)
    def _feasible(self, poly, minx, miny, w, h, X, Y, placed) -> bool:
        """바운딩 박스 왼쪽 아래가 (X, Y)일 때 원판 안이고 겹치지 않는가."""
        t0 = time.perf_counter()
        ok = self._feasible_inner(poly, minx, miny, w, h, X, Y, placed)
        self.t_feasible += time.perf_counter() - t0
        return ok

    def _feasible_inner(self, poly, minx, miny, w, h, X, Y, placed) -> bool:
        eps = self.eps
        if X < -eps or Y < -eps or Y + h > self.W + eps:
            return False
        cand = None
        bx0, by0, bx1, by1 = X, Y, X + w, Y + h
        for s in placed:
            # 박스가 떨어져 있으면 정밀 판정 생략 (집계하지 않는 가벼운 사전 필터)
            if s.maxx <= bx0 + eps or s.minx >= bx1 - eps or s.maxy <= by0 + eps or s.miny >= by1 - eps:
                continue
            if cand is None:
                cand = c.Shape(g.translate(poly, X - minx, Y - miny))
            if c.overlap(cand, s, eps):
                return False
        return True

    # ------------------------------------------------------------ 위치 선택 (Bottom-Left)
    def _first_feasible(self, poly, minx, miny, w, h, placed) -> tuple[float, float]:
        W, eps = self.W, self.eps
        xs = {0.0}
        ys = {0.0, W - h}
        for s in placed:
            xs.add(s.maxx)
            ys.add(s.maxy)
            ys.add(s.miny - h)
        ys = sorted(y for y in ys if -eps <= y <= W - h + eps)
        for X in sorted(xs):
            # 이 x 위치에서 가로로 겹칠 수 있는 부품만 남겨 두고 y 후보를 검사한다
            col = [s for s in placed if s.maxx > X + eps and s.minx < X + w - eps]
            if not col:
                return X, 0.0
            for Y in ys:
                if self._feasible(poly, minx, miny, w, h, X, Y, col):
                    return X, max(0.0, Y)
        # 이론상 도달하지 않음: 모든 부품 오른쪽에는 항상 놓을 수 있다
        return max(xs), 0.0

    def _slide_axis(self, poly, minx, miny, w, h, X, Y, placed, axis: int) -> float:
        """axis=1이면 아래로, 0이면 왼쪽으로 최대한 민 새 좌표 (이진 탐색)."""
        cur = Y if axis else X
        hi = cur
        if hi <= self.res:
            return cur

        def ok(d):
            return (
                self._feasible(poly, minx, miny, w, h, X, Y - d, placed)
                if axis
                else self._feasible(poly, minx, miny, w, h, X - d, Y, placed)
            )

        if ok(hi):  # 끝까지 밀 수 있음 (벽에 닿음)
            return 0.0
        step = max(self.res, h if axis else w)
        d = 0.0
        while d + step <= hi and ok(d + step):
            d += step
        lo, hi = d, min(d + step, hi)
        while hi - lo > self.res:
            mid = (lo + hi) / 2
            if ok(mid):
                lo = mid
            else:
                hi = mid
        return cur - lo

    def _slide(self, poly, minx, miny, w, h, X, Y, placed) -> tuple[float, float]:
        for _ in range(self.slide_iters):
            nY = self._slide_axis(poly, minx, miny, w, h, X, Y, placed, axis=1)
            nX = self._slide_axis(poly, minx, miny, w, h, X, nY, placed, axis=0)
            moved = abs(nY - Y) + abs(nX - X)
            X, Y = nX, nY
            if moved <= self.res:
                break
        return X, Y


def run(inst: Instance, sequence, *, slide: bool = True, **params) -> Solution:
    """고정 순서로 배치하고 Solution을 만든다. 시간과 계산량을 stats에 남긴다."""
    c.reset_stats()
    t0 = time.perf_counter()
    placer = TrigPlacer(inst, slide=slide, **params)
    placements = placer.place_all(sequence)
    total = time.perf_counter() - t0
    stats = {
        **c.get_stats(),
        "time_place_ms": total * 1000,
        "time_feasible_ms": placer.t_feasible * 1000,
        "slide": slide,
        "params": params,
    }
    return make_solution(inst, "trig", placements, total * 1000, stats)
