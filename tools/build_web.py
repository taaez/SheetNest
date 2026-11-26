"""웹 데모를 정적 사이트(site/)로 만든다. GitHub Pages 배포와 로컬 확인에 같이 쓴다.

python tools/build_web.py            # site/ 폴더 생성
python tools/build_web.py --serve    # 생성 후 http://localhost:8000 에서 열기

site/ 구성
  index.html, app.js, export.js, worker.js, style.css   웹 화면 (web/ 폴더 그대로)
  py.zip          브라우저의 Python(Pyodide)이 읽을 팀 코드: nesting/, algorithms/, bridge.py
  data/*.json     인스턴스 파일, data/index.json은 목록
  v2/             실무용 화면 (web_v2/ 폴더). py.zip과 data/를 따로 복사해 혼자서도 열린다.

알고리즘 코드를 따로 복사하지 않고 저장소의 현재 코드를 그대로 묶으므로,
NFP와 래스터가 main에 합쳐지면 다시 빌드하는 것만으로 웹에 반영된다.
"""

import argparse
import csv
import json
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ["index.html", "app.js", "export.js", "worker.js", "style.css"]
V2 = "v2"  # 실무용 화면이 들어갈 하위 폴더 (원본 web_v2/)
V2_STATIC = [*STATIC, "timing.js"]  # 실무용 화면에만 있는 파일: 계산 전 예상 시간표
PY_DIRS = ["nesting", "algorithms"]


def selected() -> list[tuple[Path, str]]:
    """experiments/selected.txt의 (경로, 설명) 목록."""
    out = []
    for line in (ROOT / "experiments/selected.txt").read_text(encoding="utf-8").splitlines():
        body, _, note = line.partition("#")
        if body.strip():
            out.append((ROOT / body.strip(), note.strip()))
    return out


def index_rows() -> dict[tuple[str, str], dict]:
    rows = {}
    with open(ROOT / "data/instances/index.csv", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[(r["source"], r["name"])] = r
    return rows


def build_zip(path: Path) -> int:
    n = 0
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for d in PY_DIRS:
            for p in sorted((ROOT / d).rglob("*.py")):
                z.write(p, p.relative_to(ROOT).as_posix())
                n += 1
        z.write(ROOT / "web/bridge.py", "bridge.py")
    return n + 1


def build_data(out: Path) -> list[dict]:
    out.mkdir(parents=True, exist_ok=True)
    info = index_rows()
    entries, used = [], set()

    def add(src: Path, group: str, note: str):
        name = src.stem
        if name in used:
            return
        used.add(name)
        shutil.copyfile(src, out / f"{name}.json")
        r = info.get((src.parent.name, name), {})
        entries.append(
            {
                "name": name,
                "file": f"data/{name}.json",
                "group": group,
                "note": note,
                "pieces": int(r["pieces"]) if r.get("pieces") else None,
                "types": int(r["types"]) if r.get("types") else None,
            }
        )

    for src, note in selected():
        add(src, "실험 인스턴스", note)
    for src in sorted((ROOT / "data/instances/sparrow").glob("*.json")):
        if not src.stem.endswith("_c"):  # 자유 회전 변형은 같은 모양이라 제외
            add(src, "기타 벤치마크", "")
    (out / "index.json").write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    return entries


def build(site: Path) -> None:
    if site.exists():
        shutil.rmtree(site)
    site.mkdir(parents=True)
    for name in STATIC:
        shutil.copyfile(ROOT / "web" / name, site / name)
    n_py = build_zip(site / "py.zip")
    entries = build_data(site / "data")
    (site / ".nojekyll").write_text("", encoding="utf-8")
    build_v2(site)
    print(f"site 생성: {site} (Python 파일 {n_py}개, 인스턴스 {len(entries)}개, 실무용 화면 {V2}/ 포함)")


def build_v2(site: Path) -> None:
    """web_v2/ 화면을 site/v2/에 넣는다. 계산 코드와 인스턴스는 site/의 것을 그대로 복사한다."""
    out = site / V2
    out.mkdir()
    for name in V2_STATIC:
        shutil.copyfile(ROOT / "web_v2" / name, out / name)
    shutil.copyfile(site / "py.zip", out / "py.zip")
    shutil.copytree(site / "data", out / "data")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--output", default=str(ROOT / "site"), help="출력 폴더 (기본 site/)")
    ap.add_argument("--serve", action="store_true", help="생성 후 로컬 서버 실행")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    site = Path(a.output)
    build(site)
    if a.serve:
        import functools
        import http.server

        class Handler(http.server.SimpleHTTPRequestHandler):
            # Windows는 레지스트리 설정에 따라 .js를 text/plain으로 보내는 경우가 있는데,
            # 그러면 브라우저가 스크립트 실행을 막는다. 웹에 쓰는 형식은 직접 지정한다.
            extensions_map = {
                **http.server.SimpleHTTPRequestHandler.extensions_map,
                ".js": "text/javascript",
                ".mjs": "text/javascript",
                ".css": "text/css",
                ".html": "text/html",
                ".json": "application/json",
                ".svg": "image/svg+xml",
                ".wasm": "application/wasm",
                ".zip": "application/zip",
            }

        handler = functools.partial(Handler, directory=str(site))
        print(f"http://localhost:{a.port} 에서 열기, 실무용 화면은 http://localhost:{a.port}/{V2}/ (끝내려면 Ctrl+C)")
        try:
            http.server.ThreadingHTTPServer(("127.0.0.1", a.port), handler).serve_forever()
        except KeyboardInterrupt:
            sys.exit(0)


if __name__ == "__main__":
    main()
