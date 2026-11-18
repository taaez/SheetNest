"""겹침 판정·검증기 테스트. pytest -q"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import algorithms  # noqa: E402
from nesting import collision as c  # noqa: E402
from nesting.model import Instance, Placement, Solution, make_solution  # noqa: E402
from nesting.validate import validate  # noqa: E402

EPS = 1e-6
SQ = [[0, 0], [2, 0], [2, 2], [0, 2]]
L = [[0, 0], [3, 0], [3, 1], [1, 1], [1, 3], [0, 3]]  # L자형 (오목)
TRI = [[0, 0], [4, 0], [2, 3]]


def S(poly, rot=0, x=0, y=0):
    return c.Shape.placed(poly, rot, x, y)


@pytest.mark.parametrize(
    "a,b,expect,case",
    [
        (S(SQ), S(SQ, x=3), False, "떨어진 사각형"),
        (S(SQ), S(SQ, x=2), False, "변이 맞닿음(허용)"),
        (S(SQ), S(SQ, x=2, y=2), False, "꼭짓점만 맞닿음(허용)"),
        (S(SQ), S(SQ, x=2, y=1), False, "변의 일부가 맞닿음(허용)"),
        (S(SQ), S(SQ, x=1), True, "일부 겹침"),
        (S(SQ), S(SQ), True, "완전히 같은 위치"),
        (S([[0, 0], [4, 0], [4, 4], [0, 4]]), S(SQ, x=1, y=1), True, "큰 사각형 안에 포함"),
        (S([[0, 0], [4, 0], [4, 4], [0, 4]]), S(SQ), True, "모서리를 공유하며 포함"),
        (S(L), S(SQ, x=1, y=1), False, "L자 안쪽 홈에 맞물림(접촉만)"),
        (S(L), S(SQ, x=0.5, y=0.5), True, "L자 홈에 끼워 겹침"),
        (S(TRI), S(TRI, rot=180, x=6, y=3), False, "삼각형 두 개 맞물림"),
        (S(TRI), S(TRI, rot=180, x=5.9, y=3), True, "삼각형이 조금 파고듦"),
        (S(SQ), S(SQ, x=2 + 1e-9), False, "허용 오차 이내 틈"),
        (S(SQ), S(SQ, x=2 - 1e-3), True, "허용 오차보다 큰 파고듦"),
    ],
)
def test_overlap_cases(a, b, expect, case):
    assert c.overlap(a, b, EPS) is expect, case
    assert c.overlap(b, a, EPS) is expect, case + " (순서 바꿈)"


def test_spacing():
    a, b = S(SQ), S(SQ, x=2.3)
    assert not c.overlap(a, b, EPS)
    assert c.distance(a, b) == pytest.approx(0.3)
    assert c.overlap(a, b, EPS, spacing=0.5)
    assert not c.overlap(a, b, EPS, spacing=0.2)


def test_counter():
    c.reset_stats()
    c.overlap(S(SQ), S(SQ, x=10), EPS)
    c.overlap(S(SQ), S(SQ, x=1), EPS)
    st = c.get_stats()
    assert st["overlap_checks"] == 2 and st["bbox_rejects"] == 1


def _inst():
    return Instance.from_dict(
        {
            "format": "nesting-instance/1",
            "name": "t",
            "sheet": {"width": 4},
            "items": [{"id": 0, "quantity": 2, "rotations": [0, 90], "polygon": SQ}],
        }
    )


def test_validator_detects_errors():
    inst = _inst()
    good = make_solution(inst, "m", [Placement(0, 0, 0, 0, 0), Placement(0, 1, 0, 2, 0)], 0)
    assert validate(inst, good).ok
    bad = make_solution(inst, "m", [Placement(0, 0, 0, 0, 0), Placement(0, 1, 0, 1, 0)], 0)
    assert any("겹침" in e for e in validate(inst, bad).errors)
    out = make_solution(inst, "m", [Placement(0, 0, 0, 0, 0), Placement(0, 1, 0, 0, 3)], 0)
    assert any("원판 밖" in e for e in validate(inst, out).errors)
    miss = make_solution(inst, "m", [Placement(0, 0, 0, 0, 0)], 0)
    assert any("미배치" in e for e in validate(inst, miss).errors)
    rot = make_solution(inst, "m", [Placement(0, 0, 45, 5, 0), Placement(0, 1, 0, 0, 0)], 0)
    assert any("회전" in e for e in validate(inst, rot).errors)
    lie = Solution("t", "m", good.placements, length=3.0, utilization=good.utilization, time_ms=0)
    assert any("length" in e for e in validate(inst, lie).errors)
    assert not validate(inst, good, spacing=0.5).ok  # 맞닿아 있으므로 간격 조건 위반


def test_validator_does_not_touch_counter():
    inst = _inst()
    sol = make_solution(inst, "m", [Placement(0, 0, 0, 0, 0), Placement(0, 1, 0, 2, 0)], 0)
    c.reset_stats()
    validate(inst, sol)
    assert c.get_stats()["overlap_checks"] == 0


@pytest.mark.parametrize(
    "line",
    [
        ln.split("#")[0].strip()
        for ln in (ROOT / "experiments" / "selected.txt").read_text(encoding="utf-8").splitlines()
        if ln.split("#")[0].strip()
    ],
)
def test_baseline_valid_on_selected(line):
    inst = Instance.load(ROOT / line)
    sol = algorithms.get("baseline")(inst)
    rep = validate(inst, sol)
    assert rep.ok, str(rep)
    assert sol.length >= inst.length_lower_bound - 1e-6
