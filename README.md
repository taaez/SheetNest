# SheetNest

판재 절단 배치(2D irregular nesting / strip packing) 알고리즘 비교 프로젝트 — 동국대 알고리즘 4조

모양이 제각각인 다각형 부품을 폭이 고정된 원판 위에 겹치지 않게 배치해 **사용 길이를 최소화**한다.
Bottom-Left 그리디, No-Fit Polygon 배치, 유전 알고리즘 세 가지를 같은 입력·출력 형식으로 구현해 비교한다.

## 폴더 구조

```
nesting/
  geometry.py        기하 코어: 면적, 회전, 선분 교차, 점-다각형 판정, 정규화 (A)
  model.py           Instance / Solution 형식, 저장·불러오기, 형식 검사 (A)
  io/                변환기: sparrow JSON, ESICUP XML, DXF, SVG (A)
algorithms/          bl_ga/ (B), nfp/ (C)            ← 앞으로 추가
web/, experiments/   웹 데모와 실험 자동화 (D)        ← 앞으로 추가
tools/
  convert.py         파일 1개 → 공통 instance JSON
  build_datasets.py  sparrow·ESICUP 저장소 일괄 변환 + 교차 검증
  preview.py         instance/solution을 SVG로 그려 확인
data/instances/      변환된 벤치마크 59개 + index.csv(요약표)
docs/SPEC.md         공통 입출력 형식 (반드시 읽기)
examples/            DXF/SVG 샘플 도면 생성기
tests/               pytest
```

## 시작하기

```bash
pip install -r requirements.txt
python examples/make_examples.py
pytest -q
```

## 자주 쓰는 명령

```bash
# 도면 변환
python tools/convert.py examples/sample_parts.dxf --sheet-layer SHEET -o out.json
python tools/convert.py examples/sample_parts.svg --unit mm -o out.json
python tools/convert.py my_parts.dxf --width 1220 --rotations 0,180 -o my_parts.json

# 변환 결과 눈으로 확인
python tools/preview.py data/instances/esicup/shirts.json -o shirts.svg

# 벤치마크 다시 만들기 (원본 저장소가 필요할 때만)
git clone --depth 1 https://github.com/JeroenGar/sparrow ../sparrow
git clone --depth 1 https://github.com/ESICUP/datasets ../esicup-datasets
python tools/build_datasets.py --sparrow ../sparrow --esicup ../esicup-datasets
```

## 알고리즘 작성 규칙

1. 시그니처: `nest(inst: Instance, *, seed=0, time_limit_s=None, **params) -> Solution`
2. 겹침 판정은 `nesting/geometry.py`의 공통 함수만 사용 (각자 구현 금지)
3. 결과는 `nesting.model.make_solution()`으로 만들고, `stats.overlap_checks`를 꼭 기록
4. 시간은 배치 결정 단계만 측정

## 데이터

`data/instances/index.csv`에 인스턴스별 부품 종류 수, 총 부품 수, 오목 부품 종류 수, 폭, 면적 합,
길이 하한(면적 합 ÷ 폭)이 정리되어 있다. 처음에는 `fu`(볼록 12개) → `jakobs1` → `shirts` 순으로 테스트하는 것을 권장한다.

출처
- ESICUP datasets: https://github.com/ESICUP/datasets
- sparrow (Gardeyn et al., 2025): https://github.com/JeroenGar/sparrow — 실제 산업 인스턴스 `gardeyn0~9`
