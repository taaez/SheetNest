# SheetNest

판재 절단 배치(2D irregular nesting / strip packing) 알고리즘 비교 프로젝트 — 동국대 알고리즘 4조

모양이 제각각인 다각형 부품을 폭이 고정된 원판 위에 겹치지 않게 배치해 **사용 길이를 최소화**한다.

배치 위치는 공통 Bottom-Left 디코더(후보점 + 공통 겹침 판정)로 고정하고,
**부품을 어떤 순서·회전으로 놓을지 정하는 순서 탐색 알고리즘 3가지**를 비교한다.

1. 정렬 그리디 — 정렬 기준으로 한 번 배치
2. 지역 탐색 또는 시뮬레이티드 어닐링 — 순서를 조금씩 바꿔 개선
3. 유전 알고리즘 — 순서·회전 집단을 진화

## 폴더 구조

```
nesting/
  geometry.py        기본 기하 연산: 면적, 회전, 선분 교차, 점-다각형 판정, 정규화
  collision.py       공통 겹침 판정 + 계산량 집계 (고정 층)
  decoder.py         Bottom-Left 디코더: 순서 → 배치 (고정 층, 세 알고리즘이 공유)
  validate.py        해 검증기
  model.py           Instance / Solution 형식, 저장·불러오기, 형식 검사
  io/                변환기: sparrow JSON, ESICUP XML, DXF, SVG
algorithms/
  baseline/          바운딩 박스 줄 쌓기 (검증·화면 개발용, 비교 대상 아님)
  greedy/            1. 정렬 그리디 (구현 예정)
  local_search/      2. 지역 탐색 또는 시뮬레이티드 어닐링 (구현 예정)
  ga/                3. 유전 알고리즘 (구현 예정)
experiments/         selected.txt(실험 인스턴스 7개), 실험 설명
web/                 웹 데모 (구조 미정)
tools/
  run.py             알고리즘 실행 + 검증 + 저장
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

1. 시그니처: `nest(inst: Instance, *, seed=0, time_limit_s=None, **params) -> Solution`
2. 알고리즘은 배치 순서 `[(item_id, rotation), ...]`만 정한다. 배치는 `nesting.decoder.Decoder`로 한다
3. 평가는 `dec.length(seq)`, 결과는 `dec.to_solution(best_seq, 이름, t0, {...})`
4. 시작 시 `collision.reset_stats()`, 난수는 `random.Random(seed)` 하나만
5. `python tools/run.py <알고리즘> experiments/selected.txt`로 검증기 OK 확인

자세한 규칙은 [docs/SPEC.md](docs/SPEC.md) 5절.

## 데이터

`data/instances/index.csv`에 인스턴스별 부품 종류 수, 총 부품 수, 오목 부품 종류 수, 폭, 면적 합,
길이 하한(면적 합 ÷ 폭)이 정리되어 있다. 실험용 7개는 `experiments/selected.txt`와 `experiments/README.md` 참고.

출처
- ESICUP datasets: https://github.com/ESICUP/datasets
- sparrow (Gardeyn et al., 2025): https://github.com/JeroenGar/sparrow — 실제 산업 인스턴스 `gardeyn0~9`
