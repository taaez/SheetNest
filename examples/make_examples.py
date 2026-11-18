"""DXF/SVG 읽기 테스트용 샘플 도면을 만든다 (실제 공방 도면을 받기 전 임시용).

  python examples/make_examples.py   → examples/sample_parts.dxf, examples/sample_parts.svg

포함 내용(두 파일 공통):
  1) 사각형 100x60 (닫힌 폴리라인/rect) 2개 → quantity 2로 합쳐져야 함
  2) L자형 (LINE 6개로 끊어 그림 / path) → 끝점 이어 붙이기 확인
  3) 반원 끝 막대 (ARC + LINE 조합 / 호 명령) → 곡선 근사 확인
  4) 지름 50 원 (CIRCLE)
  5) 구멍 뚫린 판 (바깥 120x80 + 안쪽 원) → 구멍 제외 확인
  6) 원판 사각형 (DXF: SHEET 레이어 1000x500, SVG: id="sheet")
"""

from pathlib import Path

import ezdxf

HERE = Path(__file__).resolve().parent


def make_dxf(path: Path):
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4  # mm
    msp = doc.modelspace()
    doc.layers.add("SHEET")
    msp.add_lwpolyline([(0, -600), (1000, -600), (1000, -100), (0, -100)], close=True, dxfattribs={"layer": "SHEET"})
    msp.add_lwpolyline([(0, 0), (100, 0), (100, 60), (0, 60)], close=True)
    msp.add_lwpolyline([(150, 0), (250, 0), (250, 60), (150, 60)], close=True)
    L = [(300, 0), (380, 0), (380, 20), (320, 20), (320, 70), (300, 70)]
    for a, b in zip(L, L[1:] + L[:1]):
        msp.add_line(a, b)
    # 반원 끝 막대: 직선 2개 + 반원 호 2개 (중심 (450,15),(530,15), 반지름 15)
    msp.add_line((450, 0), (530, 0))
    msp.add_line((530, 30), (450, 30))
    msp.add_arc((530, 15), 15, 270, 90)
    msp.add_arc((450, 15), 15, 90, 270)
    msp.add_circle((620, 25), 25)
    msp.add_lwpolyline([(700, 0), (820, 0), (820, 80), (700, 80)], close=True)
    msp.add_circle((760, 40), 20)  # 구멍
    msp.add_text("TEXT_IS_IGNORED").set_placement((0, 200))
    doc.saveas(path)


SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="1100mm" height="700mm" viewBox="0 0 1100 700">
  <rect id="sheet" x="0" y="150" width="1000" height="500" fill="none" stroke="gray"/>
  <g transform="translate(0,100)">
    <rect x="0" y="0" width="100" height="60" fill="none" stroke="black"/>
    <rect x="150" y="0" width="100" height="60" fill="none" stroke="black"/>
  </g>
  <path d="M300 0 H380 V20 H320 V70 H300 Z" fill="none" stroke="black"/>
  <path d="M450 0 H530 A15 15 0 0 1 530 30 H450 A15 15 0 0 1 450 0 Z" fill="none" stroke="black"/>
  <circle cx="620" cy="25" r="25" fill="none" stroke="black"/>
  <path d="M700 0 H820 V80 H700 Z M780 40 A20 20 0 1 0 740 40 A20 20 0 1 0 780 40 Z" fill="none" stroke="black"/>
</svg>
"""

if __name__ == "__main__":
    make_dxf(HERE / "sample_parts.dxf")
    (HERE / "sample_parts.svg").write_text(SVG, encoding="utf-8")
    print("saved sample_parts.dxf, sample_parts.svg")
