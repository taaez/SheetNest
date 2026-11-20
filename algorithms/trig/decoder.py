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
공통 실행 틀(nesting.runner)의 Placer를 상속한다. 시간 기록은 틀이 처리한다.
계산량: overlap_checks(정밀 겹침 판정 횟수), bbox_rejects(박스 단계에서 걸러진 횟수)
"""

from __future__ import annotations

from nesting import collision as c
from nesting import geometry as g
from nesting.runner import Placer


class TrigPlacer(Placer):
    name = "trig"
    REQUIRED_COUNTERS = ("overlap_checks", "bbox_rejects")

    def __init__(self, inst, slide: bool = True, slide_iters: int = 4, resolution: float | None = None, **params):
        super().__init__(inst, slide=slide, slide_iters=slide_iters, resolution=resolution, **params)
        self.eps = c.tolerance_for(self.W)
        self.slide = slide
        self.slide_iters = slide_iters
        # 미끄러뜨리기 이진 탐색의 최소 이동 단위 (기본: 원판 폭의 1/1000)
        self.res = resolution if resolution is not None else self.W * 1e-3
        self.placed: list[c.Shape] = []
        self._box: dict[tuple[int, float], tuple[float, float, float, float]] = {}
        c.reset_stats()

    def counters(self):
        return c.get_stats()

    def place(self, item: int, rotation: float) -> tuple[float, float]:
        poly = self.rotated(item, rotation)
        key = (item, rotation)
        if key not in self._box:
            minx, miny, maxx, maxy = g.bbox(poly)
            self._box[key] = (minx, miny, maxx - minx, maxy - miny)
        minx, miny, w, h = self._box[key]
        if h > self.W + self.eps:
            raise ValueError(f"item {item} 회전 {rotation}: 원판 폭보다 높음")
        X, Y = self._first_feasible(poly, minx, miny, w, h, self.placed)
        if self.slide:
            X, Y = self._slide(poly, minx, miny, w, h, X, Y, self.placed)
        x, y = X - minx, Y - miny
        self.placed.append(c.Shape(g.translate(poly, x, y)))
        return x, y

    # ------------------------------------------------------------ 가능 위치 계산 (겹침 직접 판정)
    def _feasible(self, poly, minx, miny, w, h, X, Y, placed) -> bool:
        """바운딩 박스 왼쪽 아래가 (X, Y)일 때 원판 안이고 겹치지 않는가."""
        with self.feasible_timer():
            return self._feasible_inner(poly, minx, miny, w, h, X, Y, placed)

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
