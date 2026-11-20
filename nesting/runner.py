"""공통 실행 틀. 세 가지 가능 위치 계산 방법(삼각법, NFP, 래스터)이 모두 이 틀 위에서 돈다.

알고리즘 담당자가 할 일은 Placer를 상속해 place() 하나를 구현하는 것뿐이다.
순서 고정, 사본 번호, 시간 측정, 결과(Solution) 생성은 이 틀이 모든 방법에 똑같이 처리한다.
그래서 세 방법의 차이는 가능 위치 계산에서만 나온다.

    class MyPlacer(Placer):
        name = "my"
        REQUIRED_COUNTERS = ("my_checks",)

        def place(self, item, rotation):
            poly = self.rotated(item, rotation)       # 회전한 다각형 (bbox 최솟값 0,0)
            with self.feasible_timer():               # 가능 위치 계산 시간은 반드시 이 안에서
                x, y = ...                            # Bottom-Left 규칙으로 고른 위치
            ...                                       # 내부 상태에 이 부품을 놓았다고 기록
            return x, y                               # rotated(item, rotation)을 (x, y)만큼 옮긴 위치

        def counters(self):
            return {"my_checks": self.checks}

    def nest(inst, *, seed=0, time_limit_s=None, **params):
        return run(inst, MyPlacer, **params)

place()가 돌려주는 (x, y)는 Placement의 x, y와 같은 의미다. 원래 다각형을 원점 기준으로
rotation도 반시계 회전한 뒤 (x, y)만큼 평행이동한 것이 최종 위치다.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from . import geometry as g
from .model import Instance, Placement, Solution, make_solution
from .sequence import fixed_sequence


class _FeasibleTimer:
    """with 문으로 감싼 구간의 시간을 Placer.t_feasible에 더한다.

    contextlib.contextmanager는 호출마다 생성기를 만들어 수 마이크로초가 들고, 그 일부가
    측정 구간 밖에 남아 비율을 왜곡한다(삼각법 shirts에서 97.8%가 91%로 측정됨).
    객체 하나를 재사용하는 이 방식은 오버헤드가 그보다 훨씬 작다.
    """

    __slots__ = ("owner", "t0")

    def __init__(self, owner: Placer):
        self.owner = owner
        self.t0 = 0.0

    def __enter__(self) -> None:
        self.t0 = time.perf_counter()

    def __exit__(self, *exc) -> None:
        self.owner.t_feasible += time.perf_counter() - self.t0


# 모든 방법이 stats에 반드시 남겨야 하는 키 (방법별 키는 Placer.REQUIRED_COUNTERS)
COMMON_STATS = ("time_place_ms", "time_feasible_ms", "params")


class Placer(ABC):
    """가능 위치 계산 방법 하나. 부품을 주어진 순서대로 하나씩 놓는다."""

    name: str = ""
    REQUIRED_COUNTERS: tuple[str, ...] = ()

    def __init__(self, inst: Instance, **params: Any):
        self.inst = inst
        self.W = inst.sheet_width
        self.params = params
        self.t_feasible = 0.0  # 초 단위 누적, feasible_timer()가 더한다
        self._rot_cache: dict[tuple[int, float], list[list[float]]] = {}
        self._items = {it.id: it for it in inst.items}
        self._timer = _FeasibleTimer(self)

    # ---------------------------------------------------------------- 구현할 것
    @abstractmethod
    def place(self, item: int, rotation: float) -> tuple[float, float]:
        """부품 item을 rotation으로 놓을 위치 (x, y)를 정하고 내부 상태에 반영한다."""

    def counters(self) -> dict[str, Any]:
        """방법별 계산량. REQUIRED_COUNTERS의 키를 모두 담아야 한다."""
        return {}

    # ---------------------------------------------------------------- 공용 도구
    def rotated(self, item: int, rotation: float) -> list[list[float]]:
        """회전한 다각형. 바운딩 박스 최솟값이 (0, 0)이 되도록 옮기지는 않는다(원점 기준 회전 그대로)."""
        key = (item, rotation)
        if key not in self._rot_cache:
            self._rot_cache[key] = g.rotate(self._items[item].polygon, rotation)
        return self._rot_cache[key]

    def feasible_timer(self) -> _FeasibleTimer:
        """가능 위치 계산 구간을 with 문으로 감싼다. 감싼 시간이 stats의 time_feasible_ms가 된다.
        중첩해서 쓰지 않는다(바깥 구간 하나만 감쌀 것)."""
        return self._timer

    def place_all(self, sequence: Sequence[tuple[int, float]]) -> list[Placement]:
        placements: list[Placement] = []
        copies: dict[int, int] = {}
        for item, rot in sequence:
            x, y = self.place(item, rot)
            k = copies.get(item, 0)
            copies[item] = k + 1
            placements.append(Placement(item=item, copy=k, rotation=rot, x=x, y=y))
        return placements


def run(inst: Instance, placer_cls: type[Placer], sequence=None, **params: Any) -> Solution:
    """고정 순서로 배치하고 시간과 계산량을 기록한 Solution을 만든다(모든 방법 공용)."""
    seq = fixed_sequence(inst) if sequence is None else sequence
    t0 = time.perf_counter()
    placer = placer_cls(inst, **params)
    placements = placer.place_all(seq)
    total_ms = (time.perf_counter() - t0) * 1000
    stats = {
        **placer.counters(),
        "time_place_ms": total_ms,
        "time_feasible_ms": placer.t_feasible * 1000,
        "params": params,
    }
    return make_solution(inst, placer.name, placements, total_ms, stats)
