"""BL 디코더(고정 층) 테스트. pytest -q"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nesting import collision as c  # noqa: E402
from nesting.decoder import Decoder  # noqa: E402
from nesting.model import Instance  # noqa: E402
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
    """1x1 정사각형 4개, 폭 2 → (0,0), (0,1), (1,0), (1,1) 순서로 왼쪽 열부터 채움, 길이 2"""
    dec = Decoder(_square_inst())
    pl, L = dec.decode([(0, 0)] * 4)
    assert [(p.x, p.y) for p in pl] == [(0, 0), (0, 1), (1, 0), (1, 1)]
    assert [p.copy for p in pl] == [0, 1, 2, 3]
    assert L == pytest.approx(2)


def test_deterministic_and_counts_calls():
    inst = Instance.load(ROOT / "data/instances/sparrow/jakobs1.json")
    dec = Decoder(inst)
    seq = dec.default_sequence()
    a = dec.decode(seq)
    b = dec.decode(seq)
    assert a == b
    assert dec.calls == 2


def test_rotation_too_tall_rejected():
    inst = Instance.from_dict(
        {
            "format": "nesting-instance/1",
            "name": "tall",
            "sheet": {"width": 2},
            "items": [{"id": 0, "quantity": 1, "rotations": [0, 90], "polygon": [[0, 0], [1, 0], [1, 3], [0, 3]]}],
        }
    )
    dec = Decoder(inst)
    assert dec.feasible_rotations(0) == [90]
    with pytest.raises(ValueError):
        dec.decode([(0, 0)])


@pytest.mark.parametrize("path", SELECTED)
def test_decoder_valid_and_beats_baseline(path):
    import algorithms

    inst = Instance.load(ROOT / path)
    dec = Decoder(inst)
    c.reset_stats()
    import time

    sol = dec.to_solution(dec.default_sequence(), "decoder-check", time.perf_counter())
    rep = validate(inst, sol)
    assert rep.ok, str(rep)
    assert sol.stats["decode_calls"] == 1
    base = algorithms.get("baseline")(inst)
    assert sol.length < base.length
