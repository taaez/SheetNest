"""고정 층: Bottom-Left 배치기(디코더). 세 순서 탐색 알고리즘이 모두 이것을 그대로 쓴다.

    순서 탐색 알고리즘 (비교 대상)  →  배치 순서·회전 결정
    BL 디코더 (고정, 이 파일)       →  그 순서대로 하나씩 가장 왼쪽·아래 위치에 배치
    공통 겹침 판정 (고정)            →  후보 위치가 가능한지 판단 (collision.overlap)

입력: 배치 순서 sequence = [(item_id, rotation), ...]  (부품 사본마다 1개, 총 total_quantity개)
출력: Placement 목록과 사용 길이 L  (copy 번호는 같은 item이 나온 순서대로 0, 1, 2 ... 자동 부여)

부품 하나를 놓는 과정
1) 후보점 생성: 이미 놓인 부품들의 바운딩 박스 경계에 맞닿는 위치들
   - x 후보: 0, 각 부품의 오른쪽 끝(maxx)
   - y 후보: 0, 각 부품의 위쪽 끝(maxy), 각 부품의 아래쪽 끝 − 높이(miny − h), 원판 위쪽 끝 − 높이(W − h)
2) 후보를 (x, y) 오름차순으로 정렬 → 원판 안이고 어떤 부품과도 겹치지 않는 첫 후보를 고른다 (Bottom-Left)
3) 미끄러뜨리기: 고른 위치에서 아래로, 왼쪽으로 겹치기 직전까지 반복해서 민다 (이진 탐색)
   → 바운딩 박스로는 못 들어가는 오목한 틈에 부품이 파고들게 한다

결정적 알고리즘: 같은 sequence면 항상 같은 결과.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from . import collision as c
from . import geometry as g
from .model import Instance, Placement


class Decoder:
    """인스턴스별로 회전된 다각형을 캐시해 두고 반복 호출(GA 등)에 대비한다."""

    def __init__(self, inst: Instance, slide: bool = True, slide_iters: int = 4, resolution: float | None = None):
        self.inst = inst
        self.calls = 0  # decode() 호출 횟수 = 탐색 알고리즘이 평가한 해의 개수
        self.W = inst.sheet_width
        self.eps = c.tolerance_for(self.W)
        self.slide = slide
        self.slide_iters = slide_iters
        # 미끄러뜨리기 이진 탐색의 최소 이동 단위 (기본: 원판 폭의 1/1000)
        self.res = resolution if resolution is not None else self.W * 1e-3
        self.items = {it.id: it for it in inst.items}
        self._rot: dict[tuple[int, float], tuple[list[list[float]], float, float, float, float]] = {}
        for it in inst.items:
            for r in it.rotations:
                poly = g.rotate(it.polygon, r)
                minx, miny, maxx, maxy = g.bbox(poly)
                self._rot[(it.id, r)] = (poly, minx, miny, maxx - minx, maxy - miny)

    # ------------------------------------------------------------ 보조
    def fits(self, item: int, rotation: float) -> bool:
        """이 회전에서 부품 높이가 원판 폭 이하인지."""
        return self._rot[(item, rotation)][4] <= self.W + self.eps

    def feasible_rotations(self, item: int) -> list[float]:
        return [r for r in self.items[item].rotations if self.fits(item, r)]

    def default_sequence(self, key=None) -> list[tuple[int, float]]:
        """정렬 기준 key(item) → 값 이 큰 순, 회전은 들어가는 첫 회전. (기본: 면적 큰 순)"""
        key = key or (lambda it: it.area)
        seq = []
        for it in sorted(self.inst.items, key=lambda it: (-key(it), it.id)):
            r = self.feasible_rotations(it.id)[0]
            seq.extend([(it.id, r)] * it.quantity)
        return seq

    # ------------------------------------------------------------ 핵심
    def decode(self, sequence: Sequence[tuple[int, float]]) -> tuple[list[Placement], float]:
        self.calls += 1
        placed: list[c.Shape] = []
        placements: list[Placement] = []
        copies: dict[int, int] = {}
        length = 0.0
        for item, rot in sequence:
            poly, minx, miny, w, h = self._rot[(item, rot)]
            if h > self.W + self.eps:
                raise ValueError(f"item {item} 회전 {rot}: 원판 폭보다 높음")
            X, Y = self._first_feasible(poly, minx, miny, w, h, placed)
            if self.slide:
                X, Y = self._slide(poly, minx, miny, w, h, X, Y, placed)
            x, y = X - minx, Y - miny
            shape = c.Shape(g.translate(poly, x, y))
            placed.append(shape)
            k = copies.get(item, 0)
            copies[item] = k + 1
            placements.append(Placement(item=item, copy=k, rotation=rot, x=x, y=y))
            length = max(length, shape.maxx)
        return placements, length

    def length(self, sequence: Sequence[tuple[int, float]]) -> float:
        """탐색 알고리즘의 평가 함수: 사용 길이만 반환."""
        return self.decode(sequence)[1]

    # ------------------------------------------------------------ 내부
    def _feasible(self, poly, minx, miny, w, h, X, Y, placed) -> bool:
        """바운딩 박스 왼쪽 아래가 (X, Y)일 때 원판 안이고 겹치지 않는가."""
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
        """axis=1: 아래로, axis=0: 왼쪽으로 최대한 민 새 좌표 (이진 탐색)."""
        cur = Y if axis else X
        lo, hi = 0.0, cur  # 이동량 범위
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
        # 이동 경로 중간에 장애물을 뛰어넘지 않도록 res 간격으로 처음 막히는 곳을 찾은 뒤 이진 탐색
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

    def to_solution(self, sequence, algorithm: str, t0: float, extra_stats: dict | None = None):
        """최종 sequence를 배치해 Solution으로 만든다. time_ms는 t0(perf_counter)부터 계산.
        stats에 겹침 판정 집계와 decode_calls(평가한 해 개수)를 함께 기록한다."""
        from .model import make_solution

        placements, _ = self.decode(sequence)
        ms = (time.perf_counter() - t0) * 1000
        stats = {**c.get_stats(), "decode_calls": self.calls, "slide": self.slide, **(extra_stats or {})}
        return make_solution(self.inst, algorithm, placements, ms, stats)
