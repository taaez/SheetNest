"""계약 검사. 비교 대상 방법의 결과가 공통 입출력 규칙을 지키는지 확인한다.

tests/test_contract.py와 tools/report.py가 함께 쓴다. 위반 사항을 문장 목록으로 돌려주며,
빈 목록이면 통과다.
"""

from __future__ import annotations

import math

from .model import Instance, Solution
from .runner import COMMON_STATS
from .sequence import fixed_sequence
from .validate import validate


def check(inst: Instance, sol: Solution, name: str, required_counters=()) -> list[str]:
    errs: list[str] = []
    if sol.algorithm != name:
        errs.append(f"algorithm 이름 {sol.algorithm} != {name}")
    if len(sol.placements) != inst.total_quantity:
        errs.append(f"배치 개수 {len(sol.placements)} != 전체 수량 {inst.total_quantity}")
    for it in inst.items:
        copies = sorted(p.copy for p in sol.placements if p.item == it.id)
        if copies != list(range(it.quantity)):
            errs.append(f"부품 {it.id} 사본 번호 {copies}")
    if [(p.item, p.rotation) for p in sol.placements] != fixed_sequence(inst):
        errs.append("배치 순서나 회전이 fixed_sequence와 다름")
    if not all(math.isfinite(p.x) and math.isfinite(p.y) for p in sol.placements):
        errs.append("좌표에 inf 또는 nan")
    rep = validate(inst, sol)
    if not rep.ok:
        errs.append("검증기 실패: " + str(rep).replace("\n", " "))
    missing = (set(COMMON_STATS) | set(required_counters)) - set(sol.stats)
    if missing:
        errs.append(f"stats에 없는 키 {sorted(missing)}")
    else:
        st = sol.stats
        if not 0 < st["time_feasible_ms"] <= st["time_place_ms"]:
            errs.append("time_feasible_ms가 0 이하이거나 전체 시간보다 큼")
        if not math.isclose(sol.time_ms, st["time_place_ms"]):
            errs.append("time_ms와 time_place_ms가 다름")
    return errs
