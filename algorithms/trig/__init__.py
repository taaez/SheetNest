"""가능 위치 계산 방법 1. 삼각법(직접 판정). 구현 완료.

부품을 다각형 그대로 두고 후보 위치마다 선분 교차와 점 포함 검사로 겹침을 직접 판정한다.
자세한 동작은 decoder.py 참고.
"""

from nesting.model import Instance, Solution
from nesting.sequence import fixed_sequence

from .decoder import TrigPlacer, run


def nest(inst: Instance, *, seed: int = 0, time_limit_s: float | None = None, **params) -> Solution:
    return run(inst, fixed_sequence(inst), **params)


__all__ = ["nest", "TrigPlacer", "run"]
