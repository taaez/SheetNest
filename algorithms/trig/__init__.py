"""가능 위치 계산 방법 1. 삼각법(직접 판정). 구현 완료.

부품을 다각형 그대로 두고 후보 위치마다 선분 교차와 점 포함 검사로 겹침을 직접 판정한다.
자세한 동작은 decoder.py 참고. 공통 실행 틀(nesting.runner) 위에서 돈다.
"""

from nesting.model import Instance, Solution
from nesting.runner import run

from .decoder import TrigPlacer


def nest(inst: Instance, *, seed: int = 0, time_limit_s: float | None = None, **params) -> Solution:
    return run(inst, TrigPlacer, **params)


__all__ = ["nest", "TrigPlacer"]
