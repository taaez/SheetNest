"""삼각법(직접 판정) 배치 테스트. pytest -q"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import algorithms  # noqa: E402
from algorithms.trig import TrigPlacer, run  # noqa: E402
from nesting.model import Instance  # noqa: E402
from nesting.sequence import fixed_sequence  # noqa: E402
from nesting.validate import validate  # noqa: E402

SELECTED = [
    ln.split("#")[0].strip()
    for ln in (ROOT / "experiments" / "selected.txt").read_text(encoding="utf-8").splitlines()
    if ln.split("#")[0].strip()
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


def test_bottom_left_order():
    """1x1 정사각형 4개, 폭 2이면 왼쪽 열부터 아래에서 위로 채우고 길이는 2"""
    pl = TrigPlacer(_square_inst()).place_all([(0, 0)] * 4)
    assert [(p.x, p.y) for p in pl] == [(0, 0), (0, 1), (1, 0), (1, 1)]
    assert [p.copy for p in pl] == [0, 1, 2, 3]


def test_fixed_sequence():
    inst = Instance.load(ROOT / "data/instances/sparrow/jakobs1.json")
    seq = fixed_sequence(inst)
    assert len(seq) == inst.total_quantity
    areas = [next(it.area for it in inst.items if it.id == i) for i, _ in seq]
    assert areas == sorted(areas, reverse=True)


def test_deterministic():
    inst = Instance.load(ROOT / "data/instances/sparrow/jakobs1.json")
    seq = fixed_sequence(inst)
    assert TrigPlacer(inst).place_all(seq) == TrigPlacer(inst).place_all(seq)


def test_rotation_too_tall_rejected():
    inst = Instance.from_dict(
        {
            "format": "nesting-instance/1",
            "name": "tall",
            "sheet": {"width": 2},
            "items": [{"id": 0, "quantity": 1, "rotations": [0, 90], "polygon": [[0, 0], [1, 0], [1, 3], [0, 3]]}],
        }
    )
    assert fixed_sequence(inst) == [(0, 90)]
    with pytest.raises(ValueError):
        TrigPlacer(inst).place_all([(0, 0)])


@pytest.mark.parametrize("path", SELECTED)
def test_trig_valid_and_beats_baseline(path):
    inst = Instance.load(ROOT / path)
    sol = algorithms.get("trig")(inst)
    rep = validate(inst, sol)
    assert rep.ok, str(rep)
    st = sol.stats
    assert 0 < st["time_feasible_ms"] <= st["time_place_ms"]
    assert sol.length < algorithms.get("baseline")(inst).length


def test_run_with_sequence_matches_nest():
    inst = Instance.load(ROOT / "data/instances/sparrow/fu.json")
    a = run(inst, fixed_sequence(inst))
    b = algorithms.get("trig")(inst)
    assert a.placements == b.placements
