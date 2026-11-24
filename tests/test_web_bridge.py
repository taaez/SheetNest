"""웹 연결 모듈(web/bridge.py)과 사이트 빌드(tools/build_web.py) 검사.

브라우저에서는 같은 코드가 Pyodide로 돌기 때문에, 여기서 통과하면 웹에서도 같은 값을 낸다.
방법이 아직 미구현이면 not_implemented가 나오는 것까지를 정상으로 본다.
"""

import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "web"))
sys.path.insert(0, str(ROOT / "tools"))

import bridge  # noqa: E402
import build_web  # noqa: E402

import algorithms  # noqa: E402

FU = ROOT / "data/instances/sparrow/fu.json"


def test_methods_lists_compared():
    ms = json.loads(bridge.methods())
    assert [m["name"] for m in ms] == algorithms.COMPARED
    trig = next(m for m in ms if m["name"] == "trig")
    assert trig["implemented"] and trig["label"] == "삼각법"


def test_load_and_summary():
    d = json.loads(bridge.load_path(str(FU)))
    s = d["summary"]
    assert s["name"] == "fu" and s["pieces"] == 12 and s["nonconvex_types"] == 0
    assert s["lower_bound"] == pytest.approx(1083 / s["width"])
    assert len(d["items"]) == 12


def test_run_trig_matches_direct_call():
    bridge.load_path(str(FU))
    r = json.loads(bridge.run_method("trig", "{}"))
    assert r["status"] == "ok" and r["valid"] and not r["rule_errors"]
    assert len(r["placements"]) == 12
    direct = algorithms.get("trig")(bridge._require())
    assert r["length"] == pytest.approx(direct.length)
    assert r["utilization"] == pytest.approx(direct.utilization)
    assert 0 < r["time_feasible_ms"] <= r["time_place_ms"]
    # 화면이 그리는 좌표는 배치 변환을 적용한 꼭짓점이어야 한다
    assert max(x for p in r["placements"] for x, _ in p["pts"]) == pytest.approx(r["length"])


@pytest.mark.parametrize("name", algorithms.COMPARED)
def test_every_method_reports_a_status(name):
    bridge.load_path(str(FU))
    r = json.loads(bridge.run_method(name, json.dumps({"rows": 100, "unknown": 1})))
    assert r["status"] in ("ok", "not_implemented"), r.get("message")
    assert "unknown" not in r["params"]
    if r["status"] == "ok":
        assert r["valid"], r["valid_errors"]


def test_upload_json_and_bad_extension():
    d = json.loads(bridge.load_upload("my_fu.json", FU.read_bytes()))
    assert d["summary"]["pieces"] == 12
    with pytest.raises(ValueError):
        bridge.load_upload("parts.pdf", b"x")


def test_upload_dxf_sheet_layer_and_width():
    dxf = ROOT / "examples/sample_parts.dxf"
    if not dxf.exists():
        pytest.skip("python examples/make_examples.py 를 먼저 실행")
    # 폭을 안 적으면 SHEET 레이어 사각형(1000x500)의 높이가 폭이 되고, 그 사각형은 조각으로 세지 않는다
    d = json.loads(bridge.load_upload("sample_parts.dxf", dxf.read_bytes()))
    assert d["summary"]["width"] == pytest.approx(500) and d["summary"]["pieces"] == 6
    # 폭을 적으면 그 값을 쓴다
    d = json.loads(
        bridge.load_upload("sample_parts.dxf", dxf.read_bytes(), json.dumps({"width": 300, "rotations": [0]}))
    )
    assert d["summary"]["width"] == 300 and d["summary"]["rotations"] == [0.0]
    r = json.loads(bridge.run_method("trig"))
    assert r["status"] == "ok" and r["valid"]


def test_upload_errors_are_readable(tmp_path):
    with pytest.raises(ValueError, match="JSON 형식이 아닙니다"):
        bridge.load_upload("broken.json", b"{not json")
    svg = ROOT / "examples/sample_parts.svg"
    if svg.exists():
        text = svg.read_text(encoding="utf-8").replace('id="sheet"', 'id="other"')
        with pytest.raises(ValueError, match="원판 폭 칸에 값을 적고"):
            bridge.load_upload("no_sheet.svg", text.encode("utf-8"))


def test_build_site(tmp_path):
    site = tmp_path / "site"
    build_web.build(site)
    for name in build_web.STATIC:
        assert (site / name).exists(), name
    names = zipfile.ZipFile(site / "py.zip").namelist()
    for need in ("bridge.py", "nesting/runner.py", "algorithms/__init__.py", "algorithms/trig/decoder.py"):
        assert need in names
    idx = json.loads((site / "data/index.json").read_text(encoding="utf-8"))
    exp = [e for e in idx if e["group"] == "실험 인스턴스"]
    assert [e["name"] for e in exp] == ["fu", "jakobs1", "shapes0", "shirts", "trousers", "swim", "gardeyn1"]
    assert all((site / e["file"]).exists() for e in idx)


def test_build_site_v2(tmp_path):
    """실무용 화면은 site/v2/에 따로 들어가고, 기존 화면(site/)은 web/ 그대로 남는다."""
    site = tmp_path / "site"
    build_web.build(site)
    v2 = site / build_web.V2
    for name in build_web.STATIC:
        assert (v2 / name).read_bytes() == (ROOT / "web_v2" / name).read_bytes(), name
        assert (site / name).read_bytes() == (ROOT / "web" / name).read_bytes(), name
    assert (v2 / "py.zip").read_bytes() == (site / "py.zip").read_bytes()
    idx = json.loads((v2 / "data/index.json").read_text(encoding="utf-8"))
    assert idx == json.loads((site / "data/index.json").read_text(encoding="utf-8"))
    assert all((v2 / e["file"]).exists() for e in idx)
