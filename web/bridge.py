"""웹(브라우저)과 팀 Python 코드를 잇는 연결 모듈.

브라우저에서는 Pyodide(WebAssembly Python)가 이 파일을 불러 쓴다. 웹 화면(JavaScript)은
이 모듈의 함수를 부르고, 결과를 JSON 문자열로 받는다. 알고리즘 코드는 고치지 않고
algorithms.get(이름)으로 그대로 실행하므로, NFP와 래스터가 main에 합쳐지면 웹에 자동으로 붙는다.

일반 Python에서도 그대로 동작한다(tests/test_web_bridge.py가 같은 함수를 검사한다).

    import bridge
    bridge.load_path("data/instances/sparrow/fu.json")   # 현재 인스턴스 설정
    bridge.run_method("trig", "{}")                     # 실행 결과 JSON 문자열
"""

from __future__ import annotations

import json
import math
import tempfile
import time
import traceback
from pathlib import Path
from typing import Any

import algorithms
from nesting import constraints
from nesting import geometry as g
from nesting.io import load_any
from nesting.model import Instance, Item, check_instance
from nesting.validate import validate

LABELS = {"trig": "삼각법", "nfp": "NFP", "raster": "래스터"}

# 화면에서 바꿀 수 있는 방법별 매개변수 (값을 비우면 각 방법의 기본값을 쓴다)
PARAMS = {
    "trig": [
        {"key": "rows", "label": "x 간격 (폭 ÷ 값)", "type": "int", "min": 10, "max": 2000, "step": 10},
    ],
    "raster": [
        {"key": "rows", "label": "폭 방향 칸 수", "type": "int", "min": 10, "max": 2000, "step": 10},
    ],
}

_state: dict[str, Any] = {"inst": None}


# ---------------------------------------------------------------- 방법 목록
def _tiny_instance() -> Instance:
    """구현 여부 확인용 1칸짜리 인스턴스 (정사각형 1개)."""
    sq = Item(id=0, polygon=[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], quantity=1, rotations=[0.0])
    return Instance(name="probe", sheet_width=2.0, items=[sq])


def methods() -> str:
    """비교 대상 방법 목록과 구현 여부."""
    out = []
    probe = _tiny_instance()
    for name in algorithms.COMPARED:
        implemented, note = True, ""
        try:
            algorithms.get(name)(probe)
        except NotImplementedError as e:
            implemented, note = False, str(e)
        except Exception as e:  # 구현은 되었지만 오류가 나는 경우도 화면에 보여 준다
            note = f"{type(e).__name__}: {e}"
        out.append(
            {
                "name": name,
                "label": LABELS.get(name, name),
                "implemented": implemented,
                "note": note,
                "params": PARAMS.get(name, []),
            }
        )
    return json.dumps(out, ensure_ascii=False)


# ---------------------------------------------------------------- 인스턴스 읽기
def _set(inst: Instance) -> str:
    errs = check_instance(inst)
    if errs:
        raise ValueError("형식 검사 실패: " + "; ".join(errs[:5]))
    _state["inst"] = inst
    return json.dumps({"summary": summary(inst), "items": item_shapes(inst)}, ensure_ascii=False)


def load_path(path: str) -> str:
    """팀 공통 instance JSON 또는 sparrow JSON 파일을 읽어 현재 인스턴스로 둔다."""
    return _set(load_any(path))


def load_upload(filename: str, data: bytes, options_json: str = "{}") -> str:
    """사용자가 올린 파일 내용을 임시 폴더에 쓰고 읽는다 (테스트와 일반 Python용)."""
    tmp = Path(tempfile.gettempdir()) / "sheetnest_upload"
    tmp.mkdir(parents=True, exist_ok=True)
    path = tmp / Path(filename).name
    path.write_bytes(bytes(data))
    return load_upload_path(str(path), options_json)


def load_upload_path(path: str, options_json: str = "{}") -> str:
    """올린 파일(JSON, DXF, SVG, ESICUP XML)을 읽어 현재 인스턴스로 둔다.

    options: width(원판 폭), rotations(허용 회전 목록), unit(SVG 단위), sheet_layer(DXF 원판 레이어, 기본 SHEET)
    """
    opts = json.loads(options_json or "{}")
    p = Path(path)
    ext = p.suffix.lower()
    if ext not in (".json", ".dxf", ".svg", ".xml"):
        raise ValueError(f"지원하지 않는 파일 형식: {ext} (JSON, DXF, SVG, XML만 가능)")
    kw: dict[str, Any] = {}
    if ext in (".dxf", ".svg"):
        if opts.get("width"):
            kw["width"] = float(opts["width"])
        if opts.get("rotations"):
            kw["rotations"] = [float(r) for r in opts["rotations"]]
        if ext == ".svg" and opts.get("unit"):
            kw["unit"] = opts["unit"]
        if ext == ".dxf":
            # SHEET 레이어의 사각형은 조각이 아니라 원판으로 본다(폭을 안 적었으면 그 높이를 폭으로 쓴다)
            kw["sheet_layer"] = opts.get("sheet_layer") or "SHEET"
    try:
        inst = load_any(p, **kw)
    except json.JSONDecodeError as e:
        raise ValueError("JSON 형식이 아닙니다. 팀 공통 instance JSON이나 sparrow JSON 파일인지 확인하세요.") from e
    except ValueError as e:
        if "원판 폭을 알 수 없음" in str(e):
            raise ValueError("원판 폭을 알 수 없습니다. 원판 폭 칸에 값을 적고 다시 불러오세요.") from e
        raise
    if not inst.name:
        inst.name = p.stem
    return _set(inst)


def current_instance_json() -> str:
    inst = _require()
    return json.dumps(inst.to_dict(), ensure_ascii=False)


def summary(inst: Instance) -> dict[str, Any]:
    nonconvex = sum(1 for it in inst.items if not g.is_convex(it.polygon))
    return {
        "name": inst.name,
        "source": inst.source,
        "unit": inst.unit,
        "width": inst.sheet_width,
        "types": len(inst.items),
        "pieces": inst.total_quantity,
        "nonconvex_types": nonconvex,
        "max_vertices": max(len(it.polygon) for it in inst.items),
        "total_area": inst.total_area,
        "lower_bound": inst.length_lower_bound,
        "rotations": sorted({r for it in inst.items for r in it.rotations}),
    }


def item_shapes(inst: Instance) -> list[dict[str, Any]]:
    """부품 종류별 모양 (화면의 부품 미리보기용)."""
    return [{"id": it.id, "quantity": it.quantity, "polygon": it.polygon} for it in inst.items]


def _require() -> Instance:
    inst = _state["inst"]
    if inst is None:
        raise RuntimeError("먼저 인스턴스를 불러와야 합니다")
    return inst


# ---------------------------------------------------------------- 실행
def _clean_params(name: str, params: dict[str, Any]) -> dict[str, Any]:
    allowed = {p["key"]: p for p in PARAMS.get(name, [])}
    out: dict[str, Any] = {}
    for k, v in params.items():
        if k not in allowed or v in (None, ""):
            continue
        out[k] = int(v) if allowed[k]["type"] == "int" else float(v)
    return out


def run_method(name: str, params_json: str = "{}") -> str:
    """현재 인스턴스에 방법 하나를 실행하고, 화면에 필요한 값을 JSON으로 돌려준다."""
    inst = _require()
    params = _clean_params(name, json.loads(params_json or "{}"))
    base = {"method": name, "label": LABELS.get(name, name), "params": params}
    try:
        nest = algorithms.get(name)
        t0 = time.perf_counter()
        sol = nest(inst, **params)
        wall_ms = (time.perf_counter() - t0) * 1000
    except NotImplementedError as e:
        return json.dumps({**base, "status": "not_implemented", "message": str(e)}, ensure_ascii=False)
    except Exception as e:
        tb = traceback.format_exc(limit=4)
        return json.dumps({**base, "status": "error", "message": f"{type(e).__name__}: {e}", "trace": tb})

    rep = validate(inst, sol)
    try:
        req = algorithms.get_placer(name).REQUIRED_COUNTERS
    except KeyError:
        req = ()
    rule_errs = constraints.check(inst, sol, name, req)
    by_id = {it.id: it for it in inst.items}
    placed = [
        {
            "item": p.item,
            "copy": p.copy,
            "rotation": p.rotation,
            "x": p.x,
            "y": p.y,
            "pts": [[round(x, 6), round(y, 6)] for x, y in g.transform(by_id[p.item].polygon, p.rotation, p.x, p.y)],
        }
        for p in sol.placements
    ]
    st = sol.stats
    t_all = st.get("time_place_ms", sol.time_ms)
    t_feas = st.get("time_feasible_ms", 0.0)
    lb = inst.length_lower_bound
    result = {
        **base,
        "status": "ok",
        "length": sol.length,
        "utilization": sol.utilization,
        "lower_bound": lb,
        "over_lower_bound": (sol.length / lb - 1) if lb > 0 else None,
        "time_place_ms": t_all,
        "time_feasible_ms": t_feas,
        "feasible_ratio": (t_feas / t_all) if t_all > 0 else None,
        "wall_ms": wall_ms,
        "counters": {k: st[k] for k in req if k in st},
        "valid": rep.ok,
        "valid_errors": rep.errors[:5],
        "rule_errors": rule_errs[:5],
        "placements": placed,
        "solution": sol.to_dict(),
    }
    return json.dumps(result, ensure_ascii=False, default=_json_default)


def _json_default(o):
    if isinstance(o, float) and not math.isfinite(o):
        return None
    if isinstance(o, (set, tuple)):
        return list(o)
    return str(o)
