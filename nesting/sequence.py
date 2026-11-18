"""고정 층: 배치 순서와 회전.

세 알고리즘(삼각법, NFP, 래스터)은 모두 이 순서를 그대로 쓴다. 순서가 같아야
배치 결과의 차이가 가능 위치 계산 방법의 차이에서만 나온다.

규칙: 부품을 면적이 큰 순으로 정렬하고(같으면 id 순), 회전은 허용 회전 중
원판 폭에 들어가는 첫 번째 것을 쓴다. 같은 부품의 사본은 연속해서 놓는다.
"""

from __future__ import annotations

from . import collision as c
from . import geometry as g
from .model import Instance

Sequence = list[tuple[int, float]]


def first_feasible_rotation(polygon, rotations, sheet_width: float) -> float:
    eps = c.tolerance_for(sheet_width)
    for r in rotations:
        _, miny, _, maxy = g.bbox(g.rotate(polygon, r))
        if maxy - miny <= sheet_width + eps:
            return r
    raise ValueError("원판 폭에 들어가는 회전이 없음")


def fixed_sequence(inst: Instance) -> Sequence:
    """[(item_id, rotation), ...] 부품 사본마다 1개, 총 inst.total_quantity개."""
    seq: Sequence = []
    for it in sorted(inst.items, key=lambda it: (-it.area, it.id)):
        r = first_feasible_rotation(it.polygon, it.rotations, inst.sheet_width)
        seq.extend([(it.id, r)] * it.quantity)
    return seq
