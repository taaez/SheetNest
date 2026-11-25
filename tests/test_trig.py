"""삼각법(직접 판정) 배치 테스트. pytest -q"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import algorithms  # noqa: E402
from algorithms.trig import TrigPlacer  # noqa: E402
from nesting.model import Instance  # noqa: E402
from nesting.runner import run  # noqa: E402
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
    a = run(inst, TrigPlacer, sequence=fixed_sequence(inst))
    b = algorithms.get("trig")(inst)
    assert a.placements == b.placements


def test_fills_notch():
    """ㄷ자 홈 안의 빈자리를 찾는다 (바운딩 박스 경계 후보만 보면 놓치는 자리)."""
    inst = Instance.from_dict(
        {
            "format": "nesting-instance/1",
            "name": "notch",
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
    pl = TrigPlacer(inst).place_all([(0, 0), (1, 0)])
    assert (pl[1].x, pl[1].y) == (0, 1)


def test_lowest_height_exact():
    """기울어진 변 위에 얹을 때 y는 격자가 아니라 접촉 높이로 정확히 정해진다."""
    inst = Instance.from_dict(
        {
            "format": "nesting-instance/1",
            "name": "slope",
            "sheet": {"width": 10},
            "items": [
                {"id": 0, "quantity": 1, "rotations": [0], "polygon": [[0, 0], [10, 0], [10, 3], [0, 1]]},
                {"id": 1, "quantity": 1, "rotations": [0], "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]},
            ],
        }
    )
    pl = TrigPlacer(inst).place_all([(0, 0), (1, 0)])
    # x = 0 열: 정사각형 오른쪽 아래 꼭짓점 (1, y)가 변 y = 1 + 0.2x 위에 얹힌다 → y = 1.2
    assert pl[1].x == 0 and abs(pl[1].y - 1.2) < 1e-9


@pytest.mark.parametrize("rows", [0, -1, 2.5, True])
def test_bad_rows_rejected(rows):
    with pytest.raises(ValueError):
        TrigPlacer(_square_inst(), rows=rows)


def test_copy_start_does_not_change_placements():
    """같은 부품 사본을 직전 사본의 열부터 찾는 가속은 배치를 바꾸지 않는다 (shirts 수량 2배)."""
    import json

    d = json.loads((ROOT / "data/instances/sparrow/shirts.json").read_text(encoding="utf-8"))
    for it in d["items"]:
        it["quantity"] *= 2
    inst = Instance.from_dict(d)

    class NoStart(TrigPlacer):
        def _bottom_left_fill(self, poly, minx, miny, w, h, k):
            return super()._bottom_left_fill(poly, minx, miny, w, h, 0)

    assert run(inst, TrigPlacer).placements == run(inst, NoStart).placements
