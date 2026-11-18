"""Bottom-Left 그리디 (구현 예정).

구현 메모
- 부품을 정렬(기본: 면적 큰 순)해 하나씩 배치. 허용 회전마다 후보 위치를 만들고,
  원판 안이면서 기존 부품과 겹치지 않는 위치 중 x 최소 → y 최소인 곳을 선택.
- 겹침 판정은 반드시 nesting.collision.overlap()을 사용 (호출 횟수가 자동 집계됨).
- 시작 시 collision.reset_stats(), 끝날 때 make_solution(..., stats={**collision.get_stats(), ...}).
- GA가 이 함수를 '디코더'로 쓸 수 있게, 순서와 회전을 받아 배치하는 함수를 따로 노출하면 좋다.
  예: place_in_order(inst, order: list[(item, copy)], rotations: list[float]) -> list[Placement]
"""

from nesting.model import Instance, Solution


def nest(inst: Instance, *, seed: int = 0, time_limit_s: float | None = None, **params) -> Solution:
    raise NotImplementedError("Bottom-Left 그리디 미구현")
