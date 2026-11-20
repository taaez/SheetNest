# SheetNest

판재 절단 배치(2D irregular nesting / strip packing) 알고리즘 비교 프로젝트 — 동국대 알고리즘 4조

모양이 제각각인 다각형 부품을 폭이 고정된 원판 위에 겹치지 않게 배치해 **사용 길이를 최소화**한다.

부품을 놓을 순서(면적 큰 순)와 위치 선택 규칙(Bottom-Left)은 고정하고,
실행 시간의 대부분을 차지하는 **가능 위치 계산** 방법 3가지를 비교한다.

1. 삼각법(직접 판정) — 다각형 그대로, 선분 교차·점 포함 검사
2. NFP(No-Fit Polygon) — 겹치게 되는 영역을 미리 계산해 점 하나로 판정
3. 래스터 — 격자 비트맵으로 바꿔 비트 연산으로 판정

## 폴더 구조

```
nesting/
  geometry.py        기본 기하 연산: 면적, 회전, 선분 교차, 점-다각형 판정, 정규화
  collision.py       다각형 겹침 판정 (삼각법의 핵심, 검증기도 사용) + 계산량 집계
  sequence.py        고정 배치 순서: 면적 큰 순 + 들어가는 첫 회전
  runner.py          공통 실행 틀: Placer(place()만 구현) + run(순서 고정, 시간 측정, 결과 생성)
  constraints.py     제약 검사: 세 방법이 지켜야 하는 공통 규칙 (제약 만족 여부)
  validate.py        해 검증기
  model.py           Instance / Solution 형식, 저장·불러오기, 형식 검사
  io/                변환기: sparrow JSON, ESICUP XML, DXF, SVG
algorithms/
  baseline/          바운딩 박스 줄 쌓기 (검증·화면 개발용, 비교 대상 아님)
  trig/              1. 삼각법(직접 판정) (구현 완료)
  nfp/               2. NFP (구현 예정)
  raster/            3. 래스터 (구현 예정)
experiments/         selected.txt(실험 인스턴스 7개), 실험 설명
web/                 웹 데모 (구조 미정)
tools/
  run.py             알고리즘 실행 + 검증 + 저장
  report.py          선정 7개 실행 → 제약 검사, 수치표, 배치 그림 HTML + CSV (results/)
  validate.py        solution 검증
  convert.py         파일 1개 → 공통 instance JSON
  build_datasets.py  sparrow·ESICUP 저장소 일괄 변환 + 교차 검증
  preview.py         instance/solution을 SVG로 그려 확인
data/instances/      변환된 벤치마크 59개 + index.csv(요약표)
docs/SPEC.md         공통 입출력 형식·겹침 판정·검증 규칙 (반드시 읽기)
CONTRIBUTING.md      환경 설정, 브랜치·커밋 규칙
```

## 시작하기

Python 3.11 기준. 자세한 내용은 [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python examples/make_examples.py
pytest
python tools/run.py baseline experiments/selected.txt
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

**NFP, 래스터 담당은 [docs/IMPLEMENT_GUIDE.md](docs/IMPLEMENT_GUIDE.md)부터 읽는다.**

구현할 것은 `nesting.runner.Placer`를 상속한 클래스의 `place(item, rotation) -> (x, y)` 하나다.
순서 고정, 사본 번호, 시간 측정, Solution 생성은 공통 실행 틀이 세 방법에 똑같이 처리한다.
`algorithms/nfp`, `algorithms/raster`에 빈 클래스가 있고, 완성된 예시는 `algorithms/trig/decoder.py`다.

1. 가능 위치 계산 부분은 `with self.feasible_timer():`로 감싼다 (stats의 `time_feasible_ms`가 됨)
2. 위치 선택은 Bottom-Left (x 최소, 같으면 y 최소)
3. `counters()`로 방법별 계산량(`REQUIRED_COUNTERS`)을 돌려준다
4. `pytest -q tests/test_constraints.py` 통과 (구현 전에는 자동으로 건너뜀)
5. `python tools/report.py <방법>`으로 7개 인스턴스 수치와 배치 그림 확인

자세한 규칙은 [docs/SPEC.md](docs/SPEC.md) 5절.

## 데이터

`data/instances/index.csv`에 인스턴스별 부품 종류 수, 총 부품 수, 오목 부품 종류 수, 폭, 면적 합,
길이 하한(면적 합 ÷ 폭)이 정리되어 있다. 실험용 7개는 `experiments/selected.txt`와 `experiments/README.md` 참고.

출처
- ESICUP datasets: https://github.com/ESICUP/datasets
- sparrow (Gardeyn et al., 2025): https://github.com/JeroenGar/sparrow — 실제 산업 인스턴스 `gardeyn0~9`
