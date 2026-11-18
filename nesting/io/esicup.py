"""ESICUP 원본 XML(globalnest 형식) → 팀 공통 Instance.

구조: <boards>에 원판 다각형 1개, <lot>의 <piece quantity=..>마다
<orientation><enumeration angle=../></orientation>과 <component idPolygon=.. xOffset yOffset>,
<polygons>의 <polygon id=..><lines><segment x0 y0 x1 y1/>...
- 원판 폭 = 원판 다각형의 y 범위 (길이 방향 x는 최소화 대상이라 무시)
- coordinatesOrigin이 up-left(화면 좌표, y 아래로 +)이면 y를 뒤집어 수학 좌표로 바꾼다.
  (모든 부품과 원판을 함께 뒤집으므로 문제 자체는 동일하다)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .. import geometry as g
from ..model import Instance, Item

NS = {"n": "http://globalnest.fe.up.pt/nesting"}  # load 시 파일의 실제 네임스페이스로 교체
# 파일마다 globalnest.fe.up.pt/nesting 또는 www.fe.up.pt/~esicup/nesting.xsd 네임스페이스를 쓴다


def _polygon_points(poly_el, flip_y: bool):
    pts = []
    for seg in poly_el.find("n:lines", NS).findall("n:segment", NS):
        x0, y0 = float(seg.get("x0")), float(seg.get("y0"))
        pts.append([x0, -y0 if flip_y else y0])
    return pts


def load_esicup(path: str | Path) -> Instance:
    path = Path(path)
    root = ET.parse(path).getroot()
    global NS
    NS = {"n": root.tag[1:].split("}")[0]} if root.tag.startswith("{") else {"n": ""}
    origin = (root.findtext("n:coordinatesOrigin", default="", namespaces=NS) or "").strip()
    flip = origin == "up-left"
    polys = {p.get("id"): p for p in root.find("n:polygons", NS).findall("n:polygon", NS)}
    problem = root.find("n:problem", NS)

    board = problem.find("n:boards", NS).find("n:piece", NS)
    bpoly = _polygon_points(polys[board.find("n:component", NS).get("idPolygon")], flip)
    _, bminy, _, bmaxy = g.bbox(bpoly)
    width = bmaxy - bminy

    items = []
    warnings = []
    for idx, piece in enumerate(problem.find("n:lot", NS).findall("n:piece", NS)):
        comps = piece.findall("n:component", NS)
        if len(comps) != 1:
            warnings.append(f"{piece.get('id')}: component {len(comps)}개, 첫 번째만 사용")
        c = comps[0]
        pts = _polygon_points(polys[c.get("idPolygon")], flip)
        ox, oy = float(c.get("xOffset", 0)), float(c.get("yOffset", 0))
        pts = g.translate(pts, ox, -oy if flip else oy)
        orient = piece.find("n:orientation", NS)
        angles = [float(e.get("angle")) for e in orient.findall("n:enumeration", NS)] if orient is not None else [0.0]
        items.append(
            Item(
                id=idx,
                name=piece.get("id"),
                polygon=g.normalize(pts),
                quantity=int(piece.get("quantity", 1)),
                rotations=angles or [0.0],
            )
        )
    meta = {
        "converted_from": "esicup-xml",
        "coordinates_origin": origin,
        "description": (root.findtext("n:description", default="", namespaces=NS) or "").strip(),
    }
    if warnings:
        meta["warnings"] = warnings
    name = (root.findtext("n:name", default="", namespaces=NS) or path.stem).strip()
    return Instance(
        name=path.stem if path.stem.lower() != name.lower() else name.lower(),
        sheet_width=width,
        items=items,
        source=f"esicup:{path.parent.name}/{path.name}",
        meta=meta,
    )
