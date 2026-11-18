"""해 검증기: solution이 docs/SPEC.md 4절의 유효 조건을 모두 만족하는지 확인한다.
알고리즘의 계산량 집계(collision.STATS)에는 영향을 주지 않는다.

  python tools/validate.py data/instances/sparrow/fu.json results/fu_bl.json
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import collision as c
from .model import Instance, Solution

MAX_ERRORS = 20


@dataclass
class Report:
    ok: bool
    errors: list[str] = field(default_factory=list)
    checked_pairs: int = 0
    length: float = 0.0
    utilization: float = 0.0

    def __str__(self) -> str:
        head = "통과" if self.ok else f"실패 ({len(self.errors)}건)"
        lines = [
            f"[검증 {head}] length={self.length:.6g}, utilization={self.utilization * 100:.2f}%, "
            f"정밀 검사 쌍={self.checked_pairs}"
        ]
        lines += [f"  - {e}" for e in self.errors[:MAX_ERRORS]]
        if len(self.errors) > MAX_ERRORS:
            lines.append(f"  ... 외 {len(self.errors) - MAX_ERRORS}건")
        return "\n".join(lines)


def validate(inst: Instance, sol: Solution, spacing: float = 0.0, rel_tol: float = c.REL_TOL) -> Report:
    W = inst.sheet_width
    eps = rel_tol * W
    errs: list[str] = []
    by_id = {it.id: it for it in inst.items}

    # 1) 모든 사본이 정확히 한 번씩
    need = {(it.id, k) for it in inst.items for k in range(it.quantity)}
    seen = set()
    for p in sol.placements:
        key = (p.item, p.copy)
        if p.item not in by_id:
            errs.append(f"존재하지 않는 item {p.item}")
            continue
        if key in seen:
            errs.append(f"item {p.item} copy {p.copy} 중복 배치")
        seen.add(key)
        if key not in need:
            errs.append(f"item {p.item} copy {p.copy}: 수량 범위 밖")
    for key in sorted(need - seen):
        errs.append(f"item {key[0]} copy {key[1]} 미배치")

    # 2) 허용 회전, 3) 원판 안
    shapes = []
    for p in sol.placements:
        it = by_id.get(p.item)
        if it is None:
            continue
        if not any(
            abs((p.rotation - r) % 360) < 1e-9 or abs((p.rotation - r) % 360 - 360) < 1e-9 for r in it.rotations
        ):
            errs.append(f"item {p.item} copy {p.copy}: 허용되지 않은 회전 {p.rotation}")
        s = c.Shape.placed(it.polygon, p.rotation, p.x, p.y)
        if not c.inside_sheet(s, W, eps):
            errs.append(f"item {p.item} copy {p.copy}: 원판 밖 (y {s.miny:.6g}~{s.maxy:.6g}, x≥{s.minx:.6g})")
        shapes.append((p, s))

    # 4) 겹침: x로 정렬한 뒤 x 범위가 겹치는 쌍만 정밀 검사 (스위프)
    shapes.sort(key=lambda t: t[1].minx)
    pairs = 0
    reach = spacing if spacing > 0 else 0.0
    for i, (pa, sa) in enumerate(shapes):
        for j in range(i + 1, len(shapes)):
            pb, sb = shapes[j]
            if sb.minx >= sa.maxx + reach - eps:
                break
            pairs += 1
            if c._overlap(sa, sb, eps, spacing):  # 집계하지 않는 내부 함수
                what = "간격 부족" if spacing > 0 and not c._interiors_overlap(sa, sb, eps) else "겹침"
                errs.append(f"{what}: item {pa.item}#{pa.copy} ↔ item {pb.item}#{pb.copy}")

    # 5) length, utilization 일치
    length = max((s.maxx for _, s in shapes), default=0.0)
    util = inst.total_area / (W * length) if length > 0 else 0.0
    if abs(sol.length - length) > max(eps, 1e-9 * length):
        errs.append(f"length 불일치: 보고 {sol.length:.9g} / 실제 {length:.9g}")
    if abs(sol.utilization - util) > 1e-6:
        errs.append(f"utilization 불일치: 보고 {sol.utilization:.6f} / 실제 {util:.6f}")
    return Report(ok=not errs, errors=errs, checked_pairs=pairs, length=length, utilization=util)


def assert_valid(inst: Instance, sol: Solution, **kw) -> None:
    rep = validate(inst, sol, **kw)
    if not rep.ok:
        raise AssertionError(str(rep))
