"""제약 검사 테스트. 비교 대상 세 방법(삼각법, NFP, 래스터)이 모두 지켜야 하는 입출력 규칙.

pytest -q tests/test_constraints.py
아직 구현되지 않은 방법(place가 NotImplementedError)은 건너뛴다. 구현하면 자동으로 검사된다.

검사 항목 (1번은 test_placer_registered, 7번은 test_deterministic, 나머지는 nesting/constraints.py)
  1. 공통 실행 틀의 Placer를 상속하고 이름이 등록 이름과 같다
  2. 부품 사본마다 배치가 정확히 하나 있다 (개수, 사본 번호 0..수량-1)
  3. 배치 순서와 회전이 fixed_sequence와 같다 (순서 고정 규칙)
  4. 검증기를 통과한다 (원판 안, 겹침 없음, 길이와 활용률 일치)
  5. 필수 stats 키가 있다 (공통 키와 방법별 계산량 키)
  6. 가능 위치 계산 시간이 0보다 크고 전체 시간 이하다
  7. 결정적이다 (두 번 돌리면 같은 배치)
"""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import algorithms  # noqa: E402
from nesting import constraints  # noqa: E402
from nesting.model import Instance  # noqa: E402
from nesting.runner import Placer  # noqa: E402


def _squares():
    return Instance.from_dict(
        {
            "format": "nesting-instance/1",
            "name": "squares",
            "sheet": {"width": 2},
            "items": [{"id": 0, "quantity": 5, "rotations": [0], "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]}],
        }
    )


def _concave():
    """오목한 L자와 작은 사각형. 회전 4방향, 사각형은 L자의 홈에 들어갈 수 있다."""
    return Instance.from_dict(
        {
            "format": "nesting-instance/1",
            "name": "concave",
            "sheet": {"width": 4},
            "items": [
                {
                    "id": 0,
                    "quantity": 3,
                    "rotations": [0, 90, 180, 270],
                    "polygon": [[0, 0], [3, 0], [3, 1], [1, 1], [1, 3], [0, 3]],
                },
                {"id": 1, "quantity": 4, "rotations": [0, 90], "polygon": [[0, 0], [1.5, 0], [1.5, 0.8], [0, 0.8]]},
            ],
        }
    )


CASES = {
    "squares": _squares,
    "concave": _concave,
    "fu": lambda: Instance.load(ROOT / "data/instances/sparrow/fu.json"),
    "jakobs1": lambda: Instance.load(ROOT / "data/instances/sparrow/jakobs1.json"),
}


def _solve(name, inst):
    try:
        return algorithms.get(name)(inst)
    except NotImplementedError:
        pytest.skip(f"{name} 미구현")


@pytest.mark.parametrize("name", algorithms.COMPARED)
def test_placer_registered(name):
    cls = algorithms.get_placer(name)
    assert issubclass(cls, Placer)
    assert cls.name == name


@pytest.mark.parametrize("case", list(CASES))
@pytest.mark.parametrize("name", algorithms.COMPARED)
def test_constraints(name, case):
    inst = CASES[case]()
    sol = _solve(name, inst)
    errs = constraints.check(inst, sol, name, algorithms.get_placer(name).REQUIRED_COUNTERS)
    assert not errs, "\n".join(errs)


@pytest.mark.parametrize("name", algorithms.COMPARED)
def test_deterministic(name):
    inst = CASES["jakobs1"]()
    a = _solve(name, inst)
    b = _solve(name, inst)
    assert a.placements == b.placements
