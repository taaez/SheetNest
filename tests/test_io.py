"""pytest -q 로 실행."""

import math
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nesting import geometry as g  # noqa: E402
from nesting.io import load_any  # noqa: E402
from nesting.model import Instance, Placement, Solution, check_instance, make_solution  # noqa: E402

EX = ROOT / "examples"
DATA = ROOT / "data" / "instances"


@pytest.fixture(scope="module", autouse=True)
def examples():
    subprocess.run([sys.executable, str(EX / "make_examples.py")], check=True)


# ---------- geometry ----------
def test_area_and_orientation():
    sq = [[0, 0], [2, 0], [2, 2], [0, 2]]
    assert g.signed_area(sq) == 4
    assert g.signed_area(list(reversed(sq))) == -4


def test_normalize():
    p = g.normalize([[5, 5], [5, 7], [7, 7], [7, 5], [5, 5], [6, 5]])  # CW, 닫힘, 중복·일직선 점
    assert p == [[0, 0], [2, 0], [2, 2], [0, 2]]


def test_rotate_exact():
    assert g.rotate([[1, 0]], 90) == [[0, 1]]
    assert g.rotate([[1, 2]], 270) == [[2, -1]]


def test_segments_and_pip():
    assert g.segments_intersect([0, 0], [2, 2], [0, 2], [2, 0])
    assert not g.segments_intersect([0, 0], [1, 0], [0, 1], [1, 1])
    assert g.segments_intersect([0, 0], [1, 0], [1, 0], [2, 1])  # 끝점 접촉
    sq = [[0, 0], [2, 0], [2, 2], [0, 2]]
    assert g.point_in_polygon([1, 1], sq) == 1
    assert g.point_in_polygon([2, 1], sq) == 0
    assert g.point_in_polygon([3, 1], sq) == -1


def test_is_simple():
    assert g.is_simple([[0, 0], [2, 0], [2, 2], [0, 2]])
    assert not g.is_simple([[0, 0], [2, 2], [2, 0], [0, 2]])  # 나비 모양


# ---------- readers ----------
def _check_sample(inst: Instance, width):
    assert check_instance(inst) == []
    assert inst.sheet_width == pytest.approx(width)
    assert inst.meta["holes_ignored"] == 1
    assert len(inst.items) == 5
    assert inst.total_quantity == 6
    areas = sorted(round(it.area) for it in inst.items)
    stadium = 80 * 30 + math.pi * 15**2
    circle = math.pi * 25**2
    expect = sorted([100 * 60, 80 * 20 + 20 * 50, round(stadium), round(circle), 120 * 80])
    for a, e in zip(areas, expect):
        assert a == pytest.approx(e, rel=0.01)
    rect = next(it for it in inst.items if round(it.area) == 6000)
    assert rect.quantity == 2


def test_dxf():
    _check_sample(load_any(EX / "sample_parts.dxf", sheet_layer="SHEET"), 500)
    assert load_any(EX / "sample_parts.dxf", sheet_layer="SHEET").unit == "mm"


def test_dxf_width_arg():
    inst = load_any(EX / "sample_parts.dxf", width=300)
    assert inst.sheet_width == 300


def test_svg():
    _check_sample(load_any(EX / "sample_parts.svg", unit="mm"), 500)  # width="1100mm" 문서


# ---------- datasets (data/instances가 만들어져 있을 때만) ----------
@pytest.mark.skipif(not (DATA / "sparrow" / "fu.json").exists(), reason="build_datasets.py 미실행")
def test_fu_instance():
    inst = Instance.load(DATA / "sparrow" / "fu.json")
    assert check_instance(inst) == []
    assert inst.total_quantity == 12
    assert inst.total_area == pytest.approx(1083)


@pytest.mark.skipif(not (DATA / "sparrow").exists(), reason="build_datasets.py 미실행")
def test_all_converted_valid():
    for f in list((DATA / "sparrow").glob("*.json")) + list((DATA / "esicup").glob("*.json")):
        assert check_instance(Instance.load(f)) == [], f.name


# ---------- solution ----------
def test_solution_roundtrip(tmp_path):
    inst = Instance.from_dict(
        {
            "format": "nesting-instance/1",
            "name": "t",
            "sheet": {"width": 10},
            "items": [{"id": 0, "quantity": 2, "rotations": [0, 90], "polygon": [[0, 0], [4, 0], [4, 2], [0, 2]]}],
        }
    )
    sol = make_solution(inst, "manual", [Placement(0, 0, 0, 0, 0), Placement(0, 1, 90, 6, 0)], 1.0)
    assert sol.length == pytest.approx(6)  # 90도 회전 후 x 범위 [4, 6]
    assert sol.utilization == pytest.approx(16 / 60)
    sol.save(tmp_path / "s.json")
    assert Solution.load(tmp_path / "s.json").placements[1].rotation == 90
