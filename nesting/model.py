"""팀 공통 입력(Instance)·출력(Solution) 형식. 자세한 규칙은 docs/SPEC.md 참고."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import geometry as g

INSTANCE_FORMAT = "nesting-instance/1"
SOLUTION_FORMAT = "nesting-solution/1"


@dataclass
class Item:
    id: int
    polygon: List[List[float]]          # 정규화됨: 반시계, 닫지 않음, bbox 최솟값 (0,0)
    quantity: int = 1
    rotations: List[float] = field(default_factory=lambda: [0.0])
    name: Optional[str] = None

    @property
    def area(self) -> float:
        return g.area(self.polygon)


@dataclass
class Instance:
    name: str
    sheet_width: float
    items: List[Item]
    unit: Optional[str] = None
    source: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_quantity(self) -> int:
        return sum(it.quantity for it in self.items)

    @property
    def total_area(self) -> float:
        return sum(it.area * it.quantity for it in self.items)

    @property
    def length_lower_bound(self) -> float:
        """면적 합 / 폭. 어떤 배치도 이보다 짧을 수 없다."""
        return self.total_area / self.sheet_width

    # ---------- 직렬화 ----------
    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "format": INSTANCE_FORMAT,
            "name": self.name,
            "unit": self.unit,
            "source": self.source,
            "sheet": {"width": self.sheet_width},
            "items": [],
            "meta": self.meta,
        }
        for it in self.items:
            e = {"id": it.id, "quantity": it.quantity, "rotations": it.rotations, "polygon": it.polygon}
            if it.name is not None:
                e["name"] = it.name
            d["items"].append(e)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Instance":
        if d.get("format") != INSTANCE_FORMAT:
            raise ValueError(f"format이 {INSTANCE_FORMAT}가 아님: {d.get('format')}")
        items = [Item(id=e["id"], polygon=e["polygon"], quantity=e.get("quantity", 1),
                      rotations=e.get("rotations", [0.0]), name=e.get("name")) for e in d["items"]]
        return cls(name=d["name"], sheet_width=float(d["sheet"]["width"]), items=items,
                   unit=d.get("unit"), source=d.get("source"), meta=d.get("meta", {}))

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(_dump(self.to_dict()), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Instance":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass
class Placement:
    item: int          # Item.id
    copy: int          # 0 .. quantity-1
    rotation: float    # 반시계 각도(도)
    x: float
    y: float


@dataclass
class Solution:
    instance: str
    algorithm: str
    placements: List[Placement]
    length: float
    utilization: float
    time_ms: float
    stats: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": SOLUTION_FORMAT,
            "instance": self.instance,
            "algorithm": self.algorithm,
            "length": self.length,
            "utilization": self.utilization,
            "time_ms": self.time_ms,
            "stats": self.stats,
            "placements": [asdict(p) for p in self.placements],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Solution":
        if d.get("format") != SOLUTION_FORMAT:
            raise ValueError(f"format이 {SOLUTION_FORMAT}가 아님: {d.get('format')}")
        return cls(instance=d["instance"], algorithm=d["algorithm"],
                   placements=[Placement(**p) for p in d["placements"]],
                   length=d["length"], utilization=d["utilization"], time_ms=d["time_ms"],
                   stats=d.get("stats", {}))

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(_dump(self.to_dict()), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "Solution":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def make_solution(inst: Instance, algorithm: str, placements: List[Placement],
                  time_ms: float, stats: Optional[Dict[str, Any]] = None) -> Solution:
    """배치 목록으로부터 length·utilization을 계산해 Solution을 만든다(모든 알고리즘 공용)."""
    by_id = {it.id: it for it in inst.items}
    max_x = 0.0
    for p in placements:
        poly = g.transform(by_id[p.item].polygon, p.rotation, p.x, p.y)
        max_x = max(max_x, max(q[0] for q in poly))
    length = max_x
    util = inst.total_area / (inst.sheet_width * length) if length > 0 else 0.0
    return Solution(inst.name, algorithm, placements, length, util, time_ms, stats or {})


# ---------- 구조 검증 (기하적 겹침 검증은 별도 validator에서) ----------
def check_instance(inst: Instance) -> List[str]:
    """형식 오류 목록을 돌려준다. 빈 목록이면 통과."""
    errs: List[str] = []
    if inst.sheet_width <= 0:
        errs.append("sheet.width는 양수여야 함")
    ids = set()
    for it in inst.items:
        tag = f"item {it.id}"
        if it.id in ids:
            errs.append(f"{tag}: id 중복")
        ids.add(it.id)
        if it.quantity < 1:
            errs.append(f"{tag}: quantity는 1 이상")
        if not it.rotations:
            errs.append(f"{tag}: rotations가 비어 있음")
        if len(it.polygon) < 3:
            errs.append(f"{tag}: 꼭짓점 3개 미만")
            continue
        if g.signed_area(it.polygon) <= 0:
            errs.append(f"{tag}: 반시계 방향이 아니거나 면적 0")
        minx, miny, _, _ = g.bbox(it.polygon)
        if abs(minx) > 1e-6 or abs(miny) > 1e-6:
            errs.append(f"{tag}: bbox 최솟값이 (0,0)이 아님")
        if not g.is_simple(it.polygon):
            errs.append(f"{tag}: 자기 교차 다각형")
        fits = any(_fits_width(it.polygon, r, inst.sheet_width) for r in it.rotations)
        if not fits:
            errs.append(f"{tag}: 어떤 허용 회전에서도 원판 폭에 들어가지 않음")
    return errs


def _fits_width(poly, rot, width) -> bool:
    _, miny, _, maxy = g.bbox(g.rotate(poly, rot))
    return maxy - miny <= width + 1e-6


def _dump(d: Dict[str, Any]) -> str:
    """사람이 읽기 쉽게: 꼭짓점 좌표 쌍은 한 줄로."""
    s = json.dumps(d, ensure_ascii=False, indent=2)
    import re
    return re.sub(r"\[\s+(-?[\d.eE+-]+),\s+(-?[\d.eE+-]+)\s+\]", r"[\1, \2]", s)
