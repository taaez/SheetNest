"""래스터의 경계 누락, 좌표 보정, Bottom-Left 순서를 확인하는 회귀 테스트."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from algorithms.raster import RasterPlacer, _rasterize, nest
from nesting import geometry as g
from nesting.model import Instance, Item
from nesting.validate import validate


def test_bottom_left_and_touching():
    square = [[0, 0], [1, 0], [1, 1], [0, 1]]
    inst = Instance("squares", 2, [Item(0, square, quantity=5)])
    sol = nest(inst, rows=2)
    assert [(p.x, p.y) for p in sol.placements] == [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0)]
    # 첫 사본 1회, 다음 사본은 직전 사본 칸(이제 막힘)과 새 칸을 보므로 2회씩: 1 + 2 × 4
    assert sol.stats["grid_checks"] == 9
    assert validate(inst, sol).ok


def test_concave_notch_stays_available():
    l_shape = [[0, 0], [3, 0], [3, 1], [1, 1], [1, 3], [0, 3]]
    square = [[0, 0], [2, 0], [2, 2], [0, 2]]
    inst = Instance("notch", 3, [Item(0, l_shape), Item(1, square)])
    sol = nest(inst, rows=3)
    assert [(p.x, p.y) for p in sol.placements] == [(0, 0), (1, 1)]
    assert sol.length == 3
    assert sol.utilization == 1
    assert validate(inst, sol).ok


@pytest.mark.parametrize("rotation", [0, 37, 90, 180, 270])
def test_rotated_origin_and_cached_copies(rotation):
    poly = [[0, 0], [2, 0], [2, 1], [0, 1]]
    inst = Instance("rotation", 4, [Item(7, poly, quantity=3, rotations=[rotation])])
    placer = RasterPlacer(inst, rows=16)
    x, y = placer.place(7, rotation)
    assert g.bbox(g.translate(g.rotate(poly, rotation), x, y))[:2] == pytest.approx((0, 0))
    cached = placer._bitmap_cache[(7, rotation)]
    placer.place(7, rotation)
    assert placer._bitmap_cache[(7, rotation)] is cached
    assert len(placer._bitmap_cache) == 1
    assert validate(inst, nest(inst, rows=16)).ok


def test_thin_diagonal_crosses_cells_without_centers():
    # 중심 샘플로는 놓칠 수 있는 폭 0.02의 가느다란 대각선 조각.
    poly = [[0, 0], [3, 2.9], [3, 2.92], [0, 0.02]]
    bitmap = _rasterize(poly, 1, 4)
    assert bitmap.rows == (0b011, 0b110, 0b100)


def test_short_horizontal_protrusion_not_lost():
    poly = [[0, 0], [1, 0], [1, 0.1], [4, 0.1], [4, 0.2], [1, 0.2], [1, 3], [0, 3]]
    assert _rasterize(poly, 1, 3).rows == (0b1111, 0b0001, 0b0001)


def test_piece_smaller_than_one_cell():
    poly = [[0, 0], [0.1, 0], [0, 0.1]]
    inst = Instance("tiny", 1, [Item(0, poly, quantity=2)])
    sol = nest(inst, rows=1)
    assert [(p.x, p.y) for p in sol.placements] == [(0, 0), (1, 0)]
    assert validate(inst, sol).ok


def test_width_roundoff_and_oversize():
    poly = [[0, 0], [1, 0], [1, 2 + 1e-10], [0, 2 + 1e-10]]
    inst = Instance("roundoff", 2, [Item(0, poly)])
    assert validate(inst, nest(inst, rows=10)).ok
    inst.items[0].polygon = [[0, 0], [1, 0], [1, 2.01], [0, 2.01]]
    with pytest.raises(ValueError, match="원판 폭보다 높음"):
        RasterPlacer(inst).place(0, 0)


@pytest.mark.parametrize("rows", [0, -1, 2.5, True, "200", None])
def test_bad_resolution_rejected(rows):
    with pytest.raises(ValueError, match="rows"):
        RasterPlacer(Instance("empty", 4, []), rows=rows)


@pytest.mark.parametrize("width", [0, -1, float("inf"), float("nan")])
def test_bad_sheet_width_rejected(width):
    with pytest.raises(ValueError, match="원판 폭"):
        RasterPlacer(Instance("empty", width, []))


def _clipped_area(poly, x, y):
    """테스트 전용 독립 기준: 다각형을 단위 정사각형의 네 반평면으로 자른 면적."""
    points = [tuple(p) for p in poly]
    for axis, bound, lower in [(0, x, True), (0, x + 1, False), (1, y, True), (1, y + 1, False)]:
        if not points:
            return 0.0
        clipped = []
        for a, b in zip(points, points[1:] + points[:1]):
            a_in = a[axis] >= bound if lower else a[axis] <= bound
            b_in = b[axis] >= bound if lower else b[axis] <= bound
            if a_in != b_in:
                t = (bound - a[axis]) / (b[axis] - a[axis])
                clipped.append(tuple(a[k] + t * (b[k] - a[k]) for k in range(2)))
            if b_in:
                clipped.append(b)
        points = clipped
    return g.area(points)


@pytest.mark.parametrize("rotation", [0, 13, 37, 90, 173])
@pytest.mark.parametrize(
    "poly",
    [
        [[0, 0], [4, 0], [0.03, 0.02]],
        [[0, 0], [3, 0], [3, 1], [1, 1], [1, 3], [0, 3]],
        [[0, 0], [4, 0], [4, 4], [3, 4], [3, 1], [1, 1], [1, 4], [0, 4]],
        [[0, 0], [1, 0], [1, 0.1], [4, 0.1], [4, 0.2], [1, 0.2], [1, 3], [0, 3]],
    ],
)
def test_all_positive_area_cells_are_covered(poly, rotation):
    # 래스터화와 다른 방식인 클리핑으로 각 칸의 실제 교차 면적을 확인한다.
    rotated = g.rotate(poly, rotation)
    bitmap = _rasterize(rotated, 0.4, 30)
    normalized = [[(x - bitmap.minx) / 0.4, (y - bitmap.miny) / 0.4] for x, y in rotated]
    for row in range(len(bitmap.rows)):
        for col in range(bitmap.width):
            if _clipped_area(normalized, col, row) > 1e-10:
                assert bitmap.rows[row] & (1 << col), (rotation, col, row)


def test_copy_start_does_not_change_placements():
    """같은 부품 사본을 직전 사본 위치부터 찾는 가속은 배치를 바꾸지 않는다 (shirts 수량 2배)."""
    import json

    from nesting.runner import run

    d = json.loads((ROOT / "data/instances/sparrow/shirts.json").read_text(encoding="utf-8"))
    for it in d["items"]:
        it["quantity"] *= 2
    inst = Instance.from_dict(d)

    class NoStart(RasterPlacer):
        def _first_feasible(self, bitmap, col0=0, row0=0):
            return super()._first_feasible(bitmap)

    assert run(inst, RasterPlacer).placements == run(inst, NoStart).placements
