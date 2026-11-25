"""가능 위치 계산 방법 3. 보수적 래스터(격자).

원리
  원판과 부품을 격자로 바꾼다. 부품이 조금이라도 걸치는 칸은 모두 칠한다(보수적 래스터화).
  새 부품을 어떤 위치에 놓을 때 원판에서 이미 칠해진 칸과 부품의 칸이 하나라도 겹치면 불가능하다.
  부품을 넉넉하게 칠했으므로 격자에서 안 겹치면 실제 다각형도 안 겹친다. 결과는 항상 유효하지만
  격자 크기만큼 틈이 생겨 활용률은 손해를 본다.

배치 (순서와 회전은 nesting.sequence.fixed_sequence로 고정, 위치 선택은 Bottom-Left)
  1. 격자 크기 cell = 원판 폭 / params["rows"] (기본값: 폭 방향 200칸)
  2. 부품을 회전한 뒤 칸 단위 비트맵으로 바꾼다. 행마다 정수 하나의 비트로 표현하면
     겹침 검사가 비트 AND 연산이 되어 순수 Python에서도 빠르다.
  3. 원판 비트맵을 열(x) 방향으로 왼쪽부터, 각 열에서 아래(y)부터 훑어 처음 들어가는 칸을 고른다.
  4. 고른 칸의 좌표를 실제 x, y로 바꾼다. 부품 기준점과 격자가 어긋나지 않게 주의한다.

결과를 바꾸지 않는 가속 (삼각법, NFP와 같은 규칙)
  같은 부품, 같은 회전의 다음 사본은 직전 사본이 놓인 (열, 행)부터 훑는다. 놓인 부품이 늘면
  들어갈 수 있는 칸은 줄기만 하므로, 직전 사본 위치보다 앞선 칸은 지금도 들어갈 수 없다.

구현 메모
  래스터화는 다각형 내부 칸(스캔라인 채우기)과 경계가 지나가는 칸을 모두 칠한다.
  부품 비트맵은 (부품, 회전) 조합마다 한 번만 만들어 캐시한다.
  격자 크기를 바꿔 가며 정확도와 속도의 맞교환을 실험하는 것이 분석의 핵심이다.
  결과는 반드시 nesting.validate.validate를 통과해야 한다(보수적 래스터화면 자동으로 통과).

시간 기록 (stats 필수 키, 삼각법과 같은 의미)
  time_place_ms     배치 전체 시간
  time_feasible_ms  가능 위치 계산에 쓴 시간 (래스터화 + 격자 겹침 검사)
  cell_size         격자 한 칸 크기, grid_checks 격자 겹침 검사 횟수
"""

import math
from dataclasses import dataclass

from nesting import geometry as g
from nesting.collision import tolerance_for
from nesting.model import Instance, Solution
from nesting.runner import Placer, run


@dataclass(frozen=True)
class _Bitmap:
    rows: tuple[int, ...]  # 아래에서 위로, bit 0이 가장 왼쪽 칸
    minx: float
    miny: float
    width: int


def _span(left: float, right: float, width: int) -> int:
    """구간이 통과하는 칸을 표시한다. 양 끝에서 닿기만 하는 바깥 칸은 제외."""
    start = max(0, math.floor(left))
    stop = min(width, math.ceil(right))
    return ((1 << (stop - start)) - 1) << start if stop > start else 0


def _rasterize(poly, cell: float, sheet_rows: int) -> _Bitmap:
    """스캔라인 내부 채우기 + 경계의 각 행 내 x 범위 채우기.

    다각형 내부와 교차하는 칸은 경계가 칸 내부를 지나거나, 칸 전체가 내부다.
    전자는 경계 채우기로, 후자는 행 중앙 스캔라인으로 포착한다. 중심점만 찍는
    방식과 달리 얇은 삼각형, 수평 돌출부, 한 행 안에서 끝나는 작은 조각도 놓치지 않는다.
    격자선에 정확히 닿기만 하는 바깥 칸은 칠하지 않아 맞닿음을 허용한다.
    """
    minx, miny, maxx, maxy = g.bbox(poly)
    width = max(1, math.ceil((maxx - minx) / cell))
    height = min(sheet_rows, max(1, math.ceil((maxy - miny) / cell)))
    points = [((x - minx) / cell, (y - miny) / cell) for x, y in poly]
    edges = list(zip(points, points[1:] + points[:1]))
    bitmap = [0] * height

    # 1. 행 중앙과 변의 교점을 정렬해 내부 구간들을 채운다.
    # 꼭짓점 중복 집계를 막기 위해 한쪽 끝만 포함하는 교차 조건을 쓴다.
    for row in range(height):
        scan_y = row + 0.5
        crossings = sorted(
            ax + (scan_y - ay) * (bx - ax) / (by - ay) for (ax, ay), (bx, by) in edges if (ay > scan_y) != (by > scan_y)
        )
        for left, right in zip(crossings[::2], crossings[1::2]):
            bitmap[row] |= _span(left, right, width)

    # 2. 행 중앙에 도달하지 않는 얇은 부분까지 포함하도록 경계를 덧칠한다.
    for (ax, ay), (bx, by) in edges:
        if ay == by:
            # 격자선 위의 수평 변은 바깥 행까지 확장하지 않는다.
            if ay != math.floor(ay) and 0 <= ay < height:
                bitmap[math.floor(ay)] |= _span(min(ax, bx), max(ax, bx), width)
            continue
        if ay > by:
            ax, ay, bx, by = bx, by, ax, ay
        slope = (bx - ax) / (by - ay)
        for row in range(max(0, math.floor(ay)), min(height, math.ceil(by))):
            low_y, high_y = max(ay, row), min(by, row + 1)
            x0 = ax + (low_y - ay) * slope
            x1 = ax + (high_y - ay) * slope
            bitmap[row] |= _span(min(x0, x1), max(x0, x1), width)

    if not any(bitmap):
        raise ValueError("면적이 있는 단순 다각형이 필요합니다")
    return _Bitmap(tuple(bitmap), minx, miny, width)


class RasterPlacer(Placer):
    """격자에서 x 최소, 같은 x에서는 y 최소인 위치를 결정적으로 찾는다.

    place(item, rotation)
        self.rotated(item, rotation)으로 회전한 다각형을 얻고, 가능 위치 계산 부분을
        with self.feasible_timer(): 로 감싼 뒤 Bottom-Left 규칙(x 최소, 같으면 y 최소)으로
        고른 (x, y)를 돌려준다. 놓은 부품은 다음 부품 계산을 위해 self에 기록해 둔다.
    counters()
        REQUIRED_COUNTERS의 키를 모두 담은 dict를 돌려준다.

    tests/test_constraints.py가 이 클래스를 자동으로 검사한다.
    """

    name = "raster"
    REQUIRED_COUNTERS = ("cell_size", "grid_checks")

    def __init__(self, inst, **params):
        super().__init__(inst, **params)
        self.rows = self.params.get("rows", 200)
        if isinstance(self.rows, bool) or not isinstance(self.rows, int) or self.rows <= 0:
            raise ValueError("rows는 양의 정수여야 합니다")
        if not math.isfinite(self.W) or self.W <= 0:
            raise ValueError("원판 폭은 유한한 양수여야 합니다")
        self.cell = self.W / self.rows
        if not math.isfinite(self.cell) or self.cell <= 0:
            raise ValueError("rows에 비해 원판 폭이 너무 작습니다")
        self.eps = tolerance_for(self.W)
        self.grid_checks = 0
        self._board = [0] * self.rows
        self._right = 0  # 사용한 격자 오른쪽의 첫 빈 열 (탐색 상한)
        self._bitmap_cache: dict[tuple[int, float], _Bitmap] = {}
        self._start: dict[tuple[int, float], tuple[int, int]] = {}  # 부품·회전별 다음 사본이 볼 첫 (열, 행)

    def place(self, item: int, rotation: float) -> tuple[float, float]:
        poly = self.rotated(item, rotation)
        with self.feasible_timer():
            key = (item, rotation)
            if key not in self._bitmap_cache:
                _, miny, _, maxy = g.bbox(poly)
                if maxy - miny > self.W + self.eps:
                    raise ValueError(f"item {item} 회전 {rotation}: 원판 폭보다 높음")
                self._bitmap_cache[key] = _rasterize(poly, self.cell, self.rows)
            bitmap = self._bitmap_cache[key]
            col, row = self._first_feasible(bitmap, *self._start.get(key, (0, 0)))
            x = col * self.cell - bitmap.minx
            y = row * self.cell - bitmap.miny

        self._start[key] = (col, row)
        # OR로 새 조각의 점유 칸을 기록한다 (가능 위치 계산 시간에서는 제외).
        for dy, bits in enumerate(bitmap.rows):
            self._board[row + dy] |= bits << col
        self._right = max(self._right, col + bitmap.width)
        return x, y

    def _first_feasible(self, bitmap: _Bitmap, col0: int = 0, row0: int = 0) -> tuple[int, int]:
        """(col0, row0)부터 Bottom-Left 순서(열, 그 안에서 행)로 처음 들어가는 칸."""
        # 촘촘한 행부터 확인하면 겹치는 후보를 빨리 탈락시킬 수 있다.
        # 검사할 행 순서만 바꾸므로 후보 위치의 Bottom-Left 순서는 그대로다.
        active = sorted(
            ((dy, bits) for dy, bits in enumerate(bitmap.rows) if bits),
            key=lambda entry: -entry[1].bit_count(),
        )
        max_row = self.rows - len(bitmap.rows)
        for col in range(col0, self._right + 1):
            shifted = [(dy, bits << col) for dy, bits in active]
            for row in range(row0 if col == col0 else 0, max_row + 1):
                self.grid_checks += 1
                for dy, bits in shifted:
                    if self._board[row + dy] & bits:
                        break
                else:
                    return col, row
        # _right부터는 기존 점유 비트가 없으므로 정상 입력에서는 도달하지 않는다.
        raise RuntimeError("격자 탐색 상한 안에서 빈 위치를 찾지 못했습니다")

    def counters(self):
        # grid_checks는 검사한 후보 위치 수다. 한 후보에서 여러 행을 검사해도 1회다.
        return {"cell_size": self.cell, "grid_checks": self.grid_checks}


def nest(inst: Instance, *, seed: int = 0, time_limit_s: float | None = None, **params) -> Solution:
    return run(inst, RasterPlacer, **params)
