# SheetNest

판재 절단 배치(2D irregular nesting / strip packing) 알고리즘 비교 프로젝트 — 동국대 알고리즘 4조

모양이 제각각인 다각형 부품을 폭이 고정된 원판 위에 겹치지 않게 배치해 **사용 길이를 최소화**한다.

부품을 놓을 순서(면적 큰 순, 들어가는 첫 회전)와 위치 선택 규칙(Bottom-Left: x 최소, 같으면 y 최소)은 고정하고,
실행 시간의 대부분을 차지하는 **가능 위치 계산** 방법 3가지를 비교한다.

| 방법 | 가능 위치를 찾는 방식 | Bottom-Left 정밀도 |
|---|---|---|
| 1. 삼각법 | x를 간격 Δ = 폭 ÷ rows로 훑고, 각 열에서 꼭짓점과 변이 닿는 높이로 겹침이 풀리는 가장 낮은 y를 구한다 (Bottom-Left-Fill) | Δ 간격의 열 위에서 정확, y는 연속 |
| 2. NFP | 이미 놓인 부품마다 No-Fit Polygon을 만들어, 겹치지 않는 영역의 꼭짓점과 교점 중 가장 왼쪽 아래를 고른다 | 연속 공간에서 정확 |
| 3. 래스터 | 원판과 부품을 Δ 격자 비트맵으로 바꿔 비트 연산으로 겹침을 판정한다 | Δ 격자 위에서 정확 |

삼각법과 래스터는 rows 200을 쓴다(실험 1). 자세한 규칙은 [docs/SPEC.md](docs/SPEC.md) 5절.

## 웹

설치 없이 브라우저에서 바로 실행된다. 브라우저 안의 Python(Pyodide)이 이 저장소의 `nesting/`, `algorithms/` 코드를 그대로 돌리므로
두 화면 모두 PC와 결과가 같다.

| 주소 | 폴더 | 용도 |
|---|---|---|
| https://taaez.github.io/SheetNest/v2/ | `web_v2/` | **실무용.** 계산 전에 예상 시간과 추천 방법을 보여 주고, 결과는 가장 짧은 원판 길이와 그 방법을 먼저 보여 준다 |
| https://taaez.github.io/SheetNest/ | `web/` | 알고리즘 비교용. 세 방법의 길이, 시간, 계산량을 나란히 본다 |

- 실무용 화면은 제한 시간(없음, 1초, 10초, 1분, 10분)을 고르면 그 안에 끝날 방법 중 길이가 가장 짧을 방법을 추천한다.
  추천과 실제 결과가 다르면 그대로 알려 준다. 자세한 내용은 [web_v2/README.md](web_v2/README.md).
- main에 합쳐질 때마다 GitHub Actions가 자동으로 다시 배포한다.
- 로컬에서 확인하려면 `python tools/build_web.py --serve`를 실행하고 http://localhost:8000/v2/ 또는 http://localhost:8000/ 을 연다.

## 진행 상황

| 항목 | 상태 |
|---|---|
| 공통 형식, 검증기, 공통 실행 틀 | 완료 |
| 삼각법, NFP, 래스터 | 완료 (선정 7개 모두 제약 만족) |
| 웹 비교용 화면, 실무용 화면 | 완료, 배포 중 |
| 실험 1 격자 간격, 실험 2 복제(실험 0 단계별 시간 포함), 실험 3 실제 인스턴스 23개 | 측정 완료 |
| 설계 보고서, 발표 자료 | 진행 중 |

## 실험

실험 규칙과 추천 기준은 [experiments/README.md](experiments/README.md)에 있다.

| 실험 | 확인할 것 | 실행 |
|---|---|---|
| 0. 병목 확인 | 입력, 순서(A), 위치 계산(B), 결과 생성(C), 검증의 단계별 시간 | 실험 2와 함께 기록 |
| 1. 격자 간격 | rows 100, 200, 400에 따른 삼각법과 래스터의 품질, 시간, Bottom-Left 차이 | `python tools/exp1_rows.py` |
| 2. 복제 | 수량을 1~16배로 늘릴 때 시간 증가율 k와 순위 역전 | `python tools/exp2_scaling.py` |
| 3. 실제 인스턴스 전체 | 23개 인스턴스, 10분 제한, 제한 시간 T별 추천 표, 모양 특징과 시간의 관계 | `python tools/exp3_instances.py` |

결과는 `results/`에 CSV로 저장된다. `results/`는 git에 올리지 않으므로 결과 파일은 단톡방으로 공유한다.
시간은 컴퓨터마다 다르니 비교할 때는 측정한 컴퓨터를 함께 적는다.

## 폴더 구조

```
nesting/
  geometry.py        기본 기하 연산: 면적, 회전, 선분 교차, 점-다각형 판정, 정규화
  collision.py       다각형 겹침 판정 (삼각법과 검증기가 사용) + 계산량 집계
  sequence.py        고정 배치 순서: 면적 큰 순 + 들어가는 첫 회전
  runner.py          공통 실행 틀: Placer(place()만 구현) + run(순서 고정, 시간 측정, 결과 생성)
  constraints.py     제약 검사: 세 방법이 지켜야 하는 공통 규칙
  validate.py        해 검증기
  model.py           Instance / Solution 형식, 저장·불러오기, 형식 검사
  io/                변환기: sparrow JSON, ESICUP XML, DXF, SVG
algorithms/
  baseline/          바운딩 박스 줄 쌓기 (검증·화면 개발용, 비교 대상 아님)
  trig/              1. 삼각법 (Bottom-Left-Fill)
  nfp/               2. NFP
  raster/            3. 래스터
experiments/         실험 규칙(README.md), selected.txt(실험 인스턴스 7개), 부품 그림
web/                 웹 비교용 화면 (브라우저 단독, Pyodide)
web_v2/              웹 실무용 화면, timing.js(실험 3으로 만든 예상 시간표)
tools/
  run.py             알고리즘 실행 + 검증 + 저장
  report.py          선정 7개 실행 → 제약 검사, 수치표, 배치 그림 HTML + CSV (results/)
  exp1_rows.py       실험 1 격자 간격
  exp2_scaling.py    실험 2 복제 (실험 0 단계별 시간 포함)
  exp3_instances.py  실험 3 실제 인스턴스 전체
  raster_experiment.py  래스터 격자 해상도 비교 (래스터 담당의 초기 실험)
  validate.py        solution 검증
  convert.py         파일 1개 → 공통 instance JSON
  build_datasets.py  sparrow·ESICUP 저장소 일괄 변환 + 교차 검증
  preview.py         instance/solution을 SVG로 그려 확인
  build_web.py       웹 배포용 site/ 생성 (--serve로 로컬 확인)
data/instances/      변환된 벤치마크 59개 + index.csv(요약표)
docs/SPEC.md         공통 입출력 형식·겹침 판정·검증 규칙·방법별 정밀도 (반드시 읽기)
docs/IMPLEMENT_GUIDE.md  알고리즘 구현 안내
CONTRIBUTING.md      환경 설정, 브랜치·커밋 규칙
```

## 시작하기

Python 3.11 기준. 자세한 내용은 [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python examples/make_examples.py
pytest
python tools/run.py raster experiments/selected.txt
```

## 자주 쓰는 명령

```bash
# 세 방법 실행과 검증 (선정 7개. gardeyn1에서 삼각법은 약 30초, NFP는 약 8분 걸린다)
python tools/run.py trig experiments/selected.txt
python tools/report.py raster         # 7개 인스턴스 수치표와 배치 그림

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

세 방법 모두 `nesting.runner.Placer`를 상속한 클래스의 `place(item, rotation) -> (x, y)`를 구현한다.
순서 고정, 사본 번호, 시간 측정, Solution 생성은 공통 실행 틀이 세 방법에 똑같이 처리한다.
처음 보는 사람은 [docs/IMPLEMENT_GUIDE.md](docs/IMPLEMENT_GUIDE.md)부터 읽는다.

1. 가능 위치 계산 부분은 `with self.feasible_timer():`로 감싼다 (stats의 `time_feasible_ms`가 됨)
2. 위치 선택은 Bottom-Left (x 최소, 같으면 y 최소)
3. `counters()`로 방법별 계산량(`REQUIRED_COUNTERS`)을 돌려준다
4. 결과를 바꾸지 않는 가속은 세 방법에 똑같이 적용하고, 배치가 그대로인지 테스트로 확인한다 (SPEC 5.2절)
5. `pytest` 통과, `python tools/report.py <방법>`으로 7개 인스턴스 모두 제약 만족 확인

## 데이터

`data/instances/index.csv`에 인스턴스별 부품 종류 수, 총 부품 수, 오목 부품 종류 수, 폭, 면적 합,
길이 하한(면적 합 ÷ 폭)이 정리되어 있다. 실험용 7개는 `experiments/selected.txt`와 `experiments/README.md` 참고.

출처
- ESICUP datasets: https://github.com/ESICUP/datasets
- sparrow (Gardeyn et al., 2025): https://github.com/JeroenGar/sparrow — 실제 산업 인스턴스 `gardeyn0~9`
