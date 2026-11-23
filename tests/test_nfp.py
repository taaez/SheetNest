"""NFP(No-Fit Polygon) 배치 테스트. pytest -q tests/test_nfp.py"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import algorithms  # noqa: E402
from algorithms.nfp import NFPPlacer  # noqa: E402
from algorithms.nfp.geometry_nfp import convex_decompose, nfp_convex  # noqa: E402
from nesting import geometry as g  # noqa: E402
from nesting.model import Instance  # noqa: E402
from nesting.runner import run  # noqa: E402
from nesting.sequence import fixed_sequence  # noqa: E402
from nesting.validate import validate  # noqa: E402

# gardeyn1은 NFP 개수가 매우 많아 오래 걸리므로 기본 테스트에서는 뺀다
FAST = [
    "data/instances/sparrow/fu.json",
    "data/instances/sparrow/jakobs1.json",
    "data/instances/sparrow/shapes0.json",
    "data/instances/sparrow/shirts.json",
    "data/instances/sparrow/trousers.json",
]


def _square_inst(q=4, W=2):
    return Instance.from_dict(
        {
            "format": "nesting-instance/1",
            "name": "sq",
            "sheet": {"width": W},
            "items": [{"id": 0, "quantity": q, "rotations": [0, 90], "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]}],
        }
    )


def test_nfp_of_two_unit_squares():
    """1x1 정사각형 두 개의 NFP는 (−1,−1)~(1,1) 정사각형"""
    sq = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]
    nfp = nfp_convex(sq, sq)
    assert sorted(nfp) == [(-1.0, -1.0), (-1.0, 1.0), (1.0, -1.0), (1.0, 1.0)]


def test_convex_decompose_covers_area():
    """볼록 조각 넓이의 합 = 원래 다각형 넓이, 조각은 모두 볼록"""
    L = [(0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3)]
    pieces = convex_decompose(L)
    assert len(pieces) == 2
    assert all(g.is_convex(p) for p in pieces)
    assert abs(sum(g.area(p) for p in pieces) - g.area(L)) < 1e-9


def test_bottom_left_order():
    """1x1 정사각형 4개, 폭 2이면 왼쪽 열부터 아래에서 위로 채우고 길이는 2 (삼각법과 같은 결과)"""
    pl = NFPPlacer(_square_inst()).place_all([(0, 0)] * 4)
    assert [(p.x, p.y) for p in pl] == [(0, 0), (0, 1), (1, 0), (1, 1)]
    assert [p.copy for p in pl] == [0, 1, 2, 3]


def test_concave_pocket_is_used():
    """ㄷ자 부품의 오목한 홈에 작은 정사각형이 들어간다 (NFP 꼭짓점·교점 후보 확인)"""
    inst = Instance.from_dict(
        {
            "format": "nesting-instance/1",
            "name": "pocket",
            "sheet": {"width": 3},
            "items": [
                {
                    "id": 0,
                    "quantity": 1,
                    "rotations": [0],
                    "polygon": [[0, 0], [3, 0], [3, 3], [0, 3], [0, 2], [2, 2], [2, 1], [0, 1]],
                },
                {"id": 1, "quantity": 1, "rotations": [0], "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]},
            ],
        }
    )
    sol = algorithms.get("nfp")(inst)
    assert validate(inst, sol).ok
    assert sol.length == pytest.approx(3.0)
    sq = next(p for p in sol.placements if p.item == 1)
    assert (sq.x, sq.y) == pytest.approx((0.0, 1.0))


def test_deterministic():
    inst = Instance.load(ROOT / "data/instances/sparrow/jakobs1.json")
    seq = fixed_sequence(inst)
    assert NFPPlacer(inst).place_all(seq) == NFPPlacer(inst).place_all(seq)


def test_rotation_too_tall_rejected():
    inst = Instance.from_dict(
        {
            "format": "nesting-instance/1",
            "name": "tall",
            "sheet": {"width": 2},
            "items": [{"id": 0, "quantity": 1, "rotations": [0, 90], "polygon": [[0, 0], [1, 0], [1, 3], [0, 3]]}],
        }
    )
    with pytest.raises(ValueError):
        NFPPlacer(inst).place_all([(0, 0)])


@pytest.mark.parametrize("path", FAST)
def test_nfp_valid_and_beats_baseline(path):
    inst = Instance.load(ROOT / path)
    sol = algorithms.get("nfp")(inst)
    rep = validate(inst, sol)
    assert rep.ok, str(rep)
    st = sol.stats
    assert 0 < st["time_feasible_ms"] <= st["time_place_ms"]
    assert st["nfp_computed"] > 0 and st["candidate_evals"] > 0
    assert sol.length < algorithms.get("baseline")(inst).length


def test_run_with_sequence_matches_nest():
    inst = Instance.load(ROOT / "data/instances/sparrow/fu.json")
    a = run(inst, NFPPlacer, sequence=fixed_sequence(inst))
    b = algorithms.get("nfp")(inst)
    assert a.placements == b.placements
