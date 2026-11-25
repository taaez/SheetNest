"""삼각법(직접 판정) 기반 Bottom-Left-Fill 배치.

가능 위치 계산 방법 1. 부품을 다각형 그대로 두고, 시험하는 위치마다 이미 놓인 부품과
선분 교차, 점 포함 검사(nesting.collision.overlap)로 겹침을 직접 판정한다.
직접 판정은 "이 위치에 놓아도 되는가"에만 답하므로, 시험할 위치를 Bottom-Left 순서로 훑는다.
방식은 Burke 외(2006)의 Bottom-Left-Fill(BLF)을 따른다.

부품 하나를 놓는 과정 (순서와 회전은 nesting.sequence.fixed_sequence로 고정)
1) x = 0, Δ, 2Δ, ... 순서로 열을 본다. Δ = 원판 폭 / rows (기본 rows = 200, 래스터 격자와 같은 간격).
2) 각 열에서 y = 0에 놓아 본다. 겹치는 부품이 있으면 그 부품과의 겹침이 풀리는 가장 낮은 높이로
   올린다. 그 높이는 내 꼭짓점이 상대 변 위에 얹히거나 상대 꼭짓점이 내 변 아래에 닿는 높이
   (꼭짓점-변 접촉 높이) 중 하나이므로, 이 후보를 낮은 순서로 판정해 정확히 구한다.
   올린 뒤 다시 모든 부품과 판정하고, 겹침이 없으면 그 열의 가장 낮은 가능 위치다.
3) 원판 위로 넘치면 다음 열로 넘어간다. 처음으로 들어가는 열의 그 높이를 고른다.
   즉 Δ 간격 열로 제한한 위치 중에서 "x 최소, 같으면 y 최소"인 위치를 정확히 고른다(y는 연속값).
   정확한 Bottom-Left 자리가 폭이 Δ보다 좁은 틈이면 어느 열에도 걸리지 않아 건너뛸 수 있다.

결정적 알고리즘이다. 같은 순서면 항상 같은 결과가 나온다.
결과를 바꾸지 않는 가속
  - 같은 부품, 같은 회전의 다음 사본은 직전 사본의 열부터 본다(놓인 부품이 늘면 가능 영역은 줄기만 한다).
  - 모든 놓인 부품의 오른쪽 끝을 지난 열은 판정 없이 바로 y = 0에 놓는다.
공통 실행 틀(nesting.runner)의 Placer를 상속한다. 위치 계산 전체를 feasible_timer로 잰다.
계산량: overlap_checks(정밀 겹침 판정 횟수), bbox_rejects, columns(본 열 수), lifts(겹침을 풀려고 올린 횟수)
"""

from __future__ import annotations

from nesting import collision as c
from nesting import geometry as g
from nesting.runner import Placer

Pt = tuple[float, float]


def contact_heights(moving: list[Pt], fixed: list[Pt], lo: float, hi: float) -> list[float]:
    """x를 고정한 채 moving(높이 0 기준 좌표)을 위로 Y만큼 올렸을 때 fixed와 위아래로 맞닿는 Y 후보.

    moving의 꼭짓점이 fixed의 변 위에 얹히는 높이와, fixed의 꼭짓점이 moving의 변 아래에 닿는 높이다.
    x를 고정했을 때 두 다각형이 겹치는 높이 구간의 끝은 반드시 이 값 중 하나다. lo < Y ≤ hi인 것만 돌려준다.
    """
    out: list[float] = []

    def scan(verts: list[Pt], poly: list[Pt], sign: float) -> None:
        n = len(poly)
        for i in range(n):
            ax, ay = poly[i]
            bx, by = poly[(i + 1) % n]
            if ax == bx:  # 세로 변은 끝점(꼭짓점)끼리의 접촉으로 처리된다
                continue
            x0, x1 = (ax, bx) if ax < bx else (bx, ax)
            slope = (by - ay) / (bx - ax)
            for px, py in verts:
                if x0 <= px <= x1:
                    Y = (ay + (px - ax) * slope - py) * sign
                    if lo < Y <= hi:
                        out.append(Y)

    scan(moving, fixed, 1.0)  # moving 꼭짓점이 fixed 변 위에 얹힘
    scan(fixed, moving, -1.0)  # fixed 꼭짓점이 moving 변 아래에 닿음
    return out


class TrigPlacer(Placer):
    name = "trig"
    REQUIRED_COUNTERS = ("overlap_checks", "bbox_rejects", "columns", "lifts")

    def __init__(self, inst, **params):
        super().__init__(inst, **params)
        self.rows = self.params.get("rows", 200)
        if isinstance(self.rows, bool) or not isinstance(self.rows, int) or self.rows <= 0:
            raise ValueError("rows는 양의 정수여야 합니다")
        self.eps = c.tolerance_for(self.W)
        self.dx = self.W / self.rows  # 열 간격 Δ
        self.placed: list[c.Shape] = []
        self._box: dict[tuple[int, float], tuple[float, float, float, float]] = {}
        self._start: dict[tuple[int, float], int] = {}  # 부품·회전별 다음 사본이 볼 첫 열 번호
        self.columns = 0
        self.lifts = 0
        c.reset_stats()

    def counters(self):
        out = c.get_stats()
        out["columns"] = self.columns
        out["lifts"] = self.lifts
        return out

    def place(self, item: int, rotation: float) -> tuple[float, float]:
        poly = self.rotated(item, rotation)
        key = (item, rotation)
        if key not in self._box:
            minx, miny, maxx, maxy = g.bbox(poly)
            self._box[key] = (minx, miny, maxx - minx, maxy - miny)
        minx, miny, w, h = self._box[key]
        if h > self.W + self.eps:
            raise ValueError(f"item {item} 회전 {rotation}: 원판 폭보다 높음")
        with self.feasible_timer():
            k, X, Y = self._bottom_left_fill(poly, minx, miny, w, h, self._start.get(key, 0))
        self._start[key] = k
        x, y = X - minx, Y - miny
        self.placed.append(c.Shape(g.translate(poly, x, y)))
        return x, y

    # ------------------------------------------------------------ 위치 선택 (Bottom-Left-Fill)
    def _bottom_left_fill(self, poly, minx, miny, w, h, k: int) -> tuple[int, float, float]:
        """바운딩 박스 왼쪽 아래 (X, Y)와 그 열 번호 k. X = k·Δ."""
        eps = self.eps
        top = max(0.0, self.W - h)
        right = max((s.maxx for s in self.placed), default=0.0)
        while True:
            X = k * self.dx
            self.columns += 1
            if X >= right - eps:  # 놓인 부품 모두의 오른쪽: 항상 빈 곳
                return k, X, 0.0
            col = [s for s in self.placed if s.maxx > X + eps and s.minx < X + w - eps]
            if not col:
                return k, X, 0.0
            Y = self._lowest_in_column(poly, X - minx, -miny, h, top, col)
            if Y is not None:
                return k, X, Y
            k += 1

    def _lowest_in_column(self, poly, dx, dy, h, top, col) -> float | None:
        """열 하나에서 겹치지 않는 가장 낮은 Y (바운딩 박스 아래 변 기준). 없으면 None."""
        eps = self.eps
        base = g.translate(poly, dx, dy)  # Y = 0일 때의 꼭짓점
        Y = 0.0
        while True:
            hit = self._first_overlap(base, Y, h, col)
            if hit is None:
                return Y
            # hit과의 겹침이 풀리는 가장 낮은 높이로 올린다 (그 사이 높이는 모두 hit과 겹친다)
            self.lifts += 1
            for Yc in sorted(set(contact_heights(base, hit.pts, Y + eps, top + eps))):
                if not c.overlap(c.Shape([(px, py + Yc) for px, py in base]), hit, eps):
                    Y = min(Yc, top)
                    break
            else:
                return None

    def _first_overlap(self, base, Y: float, h: float, col) -> c.Shape | None:
        """높이 Y에 놓았을 때 처음 겹치는 놓인 부품 (없으면 None)."""
        eps = self.eps
        cand = None
        for s in col:
            # 높이 방향 박스가 떨어져 있으면 정밀 판정 생략
            if s.maxy <= Y + eps or s.miny >= Y + h - eps:
                continue
            if cand is None:
                cand = c.Shape([(px, py + Y) for px, py in base])
            if c.overlap(cand, s, eps):
                return s
        return None
