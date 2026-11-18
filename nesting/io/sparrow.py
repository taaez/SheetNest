"""sparrow / jagua-rs JSON 형식 → 팀 공통 Instance.

원본 예: {"name": "fu", "strip_height": 38.0038,
          "items": [{"id": 0, "demand": 1,
                     "orientation": {"rotation": {"mode": "discrete", "angles": [0, 90, 180, 270]}},
                     "shape": {"type": "simple_polygon", "data": [[0,0],[10,0],[10,10],[0,10],[0,0]]}}]}
- strip_height(고정 변) → sheet.width
- demand → quantity
- rotation mode "continuous"(자유 회전)는 공통 형식이 이산 각도만 지원하므로
  continuous_step 간격의 각도 목록으로 바꾸고 meta에 기록한다.
- zones(품질 구역) 등 지원하지 않는 필드는 무시하고 meta에 기록한다.
"""

from __future__ import annotations

import json
from pathlib import Path

from .. import geometry as g
from ..model import Instance, Item


def load_sparrow(path: str | Path, continuous_step: float = 90.0) -> Instance:
    path = Path(path)
    d = json.loads(path.read_text(encoding="utf-8"))
    items = []
    continuous = 0
    ignored = set()
    for e in d["items"]:
        shape = e["shape"]
        if shape.get("type") != "simple_polygon":
            raise ValueError(f"item {e['id']}: 지원하지 않는 shape type {shape.get('type')}")
        rot = (e.get("orientation") or {}).get("rotation") or {"mode": "discrete", "angles": [0]}
        if rot.get("mode") == "continuous":
            continuous += 1
            n = int(round(360 / continuous_step))
            angles = [round(i * continuous_step, 6) for i in range(n)]
        else:
            angles = [float(a) for a in rot.get("angles", [0])]
        for k in e:
            if k not in ("id", "demand", "orientation", "shape", "dxf"):
                ignored.add(k)
        items.append(
            Item(
                id=int(e["id"]), polygon=g.normalize(shape["data"]), quantity=int(e.get("demand", 1)), rotations=angles
            )
        )
    meta = {"converted_from": "sparrow-json"}
    if continuous:
        meta["continuous_rotation_items"] = continuous
        meta["continuous_rotation_step"] = continuous_step
    if ignored:
        meta["ignored_fields"] = sorted(ignored)
    return Instance(
        name=d.get("name", path.stem),
        sheet_width=float(d["strip_height"]),
        items=items,
        source=f"sparrow:{path.name}",
        meta=meta,
    )
