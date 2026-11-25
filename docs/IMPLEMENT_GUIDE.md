# 구현 담당자 안내: 구현할 것은 `place()` 하나

NFP 담당과 래스터 담당을 위한 안내서다. 처음 받은 사람이 이 문서 하나만 읽고 시작할 수 있게 썼다.
AI 도구(Claude, ChatGPT, Copilot 등)와 함께 작업한다면 이 문서 전체를 먼저 AI에게 주고 시작하면 된다(9절 참고).

## 0. 한눈에 보기

- **프로젝트**: 판재 절단 배치(nesting). 폭이 정해진 원단(판재) 위에 다각형 조각들을 겹치지 않게 놓아, 사용한 길이를 최소로 만든다. 의류 공장의 재단 도면(마커) 작업과 같은 문제다.
- **비교 대상**: "이 조각을 여기에 놓을 수 있는가"를 계산하는 방법 세 가지. ① 삼각법(직접 판정) ② NFP ③ 래스터.
- **고정된 것**: 놓는 순서(면적 큰 순)와 회전, 위치 고르는 규칙(Bottom-Left: x 최소, 같으면 y 최소). 세 방법이 모두 같은 순서와 규칙을 쓰므로 결과 차이는 가능 위치 계산에서만 나온다.
- **담당자가 할 일**: `algorithms/nfp/__init__.py` 또는 `algorithms/raster/__init__.py`에 있는 빈 클래스의 `place()`와 `counters()`를 채운다. 나머지(순서, 시간 측정, 결과 생성, 검증)는 이미 공통 코드가 한다.
- **끝났다는 기준**: `pytest`에서 제약 검사가 건너뛰기 없이 통과하고, `python tools/report.py <방법>`에서 7개 인스턴스 모두 "제약 만족"이 나오면 된다.

## 1. 지금 어디까지 되어 있나

| 구성 요소 | 파일 | 상태 |
|---|---|---|
| 공통 입출력 형식 (Instance, Solution) | `nesting/model.py`, `docs/SPEC.md` | 완료 |
| 데이터 변환 (벤치마크 59개), 실험용 7개 선정 | `data/instances/`, `experiments/selected.txt` | 완료 |
| 기하 함수 (회전, 이동, 바운딩 박스, 점 포함 등) | `nesting/geometry.py` | 완료 |
| 다각형 겹침 판정 | `nesting/collision.py` | 완료 (shapely와 12,000쌍 대조, 불일치 0) |
| 해 검증기 (겹침, 원판 이탈, 개수 확인) | `nesting/validate.py` | 완료 |
| 고정 순서와 회전 | `nesting/sequence.py` | 완료 |
| **공통 실행 틀** (Placer, run) | `nesting/runner.py` | 완료 |
| **제약 검사** (공통 규칙 만족 여부) | `nesting/constraints.py`, `tests/test_constraints.py` | 완료 |
| 실행 리포트 (수치표, 배치 그림, CSV) | `tools/report.py` | 완료 |
| ① 삼각법 | `algorithms/trig/` | **완료**, 7개 모두 제약 만족 |
| ② NFP | `algorithms/nfp/` | **완료**, 7개 모두 제약 만족 |
| ③ 래스터 | `algorithms/raster/__init__.py` | **완료**, 7개 모두 제약 만족 |
| 웹 | `web/` | 미착수 (웹 담당) |
| 세 방법 비교 실험, 보고서 6장 | `tools/report.py` | NFP와 래스터 완료 후 진행 |

삼각법 결과 (Bottom-Left-Fill, rows=200, 시간은 1회 측정)

| 인스턴스 | 부품 수 | 사용 길이 | 활용률(%) | 전체 시간(ms) | 가능 위치 계산 비율 |
|---|---|---|---|---|---|
| fu | 12 | 42.3128 | 67.3 | 44 | 100% |
| jakobs1 | 25 | 13.001 | 75.4 | 177 | 100% |
| shapes0 | 43 | 73.0067 | 54.6 | 327 | 100% |
| shirts | 99 | 68.4 | 78.9 | 715 | 100% |
| trousers | 64 | 284.15 | 76.7 | 851 | 100% |
| swim | 48 | 7448.57 | 59.4 | 3187 | 100% |
| gardeyn1 | 50 | 18924 | 77.2 | 29047 | 100% |

## 2. 시작하기 (처음 한 번)

### 2.1 준비물

- **Python 3.11** (CI가 3.11로 돈다). 3.12 이상만 있으면 3.11을 따로 설치한다.
  설치 후 확인: Windows `py -3.11 --version`, macOS/Linux `python3.11 --version`
- **git**, 그리고 GitHub 계정
- **저장소 쓰기 권한**: taaez가 보낸 GitHub collaborator 초대를 메일이나 github.com/notifications에서 수락한다.
  수락하지 않으면 clone과 테스트는 되지만 push가 거부된다.

git을 처음 쓰는 컴퓨터라면 커밋에 남을 이름과 메일을 한 번 설정한다.

```bash
git config --global user.name "GitHub 아이디"
git config --global user.email "GitHub에 등록한 메일"
```

### 2.2 받기, 설치, 테스트

```bash
git clone https://github.com/taaez/SheetNest.git
cd SheetNest

# 가상환경 만들기 (3.11로)
py -3.11 -m venv .venv          # Windows
python3.11 -m venv .venv        # macOS/Linux

# 가상환경 켜기 (터미널을 새로 열 때마다)
.venv\Scripts\activate          # Windows (cmd, PowerShell)
source .venv/bin/activate       # macOS/Linux

python --version                # Python 3.11.x 가 나와야 한다
pip install -r requirements.txt
python examples/make_examples.py
pytest
```

- Windows PowerShell에서 activate가 "스크립트를 실행할 수 없습니다"로 막히면 한 번만
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` 를 실행하고 다시 켠다.
- 가상환경을 켜면 터미널 앞에 `(.venv)`가 붙는다. 이후 `python`, `pip`, `pytest`, `ruff`는 모두 이 상태에서 쓴다.
- `pytest`가 정상이면 마지막 줄이 `56 passed, 10 skipped`처럼 나온다(개수는 코드가 늘면 바뀐다).
  failed가 없으면 된다. skipped는 아직 구현 안 된 NFP와 래스터 검사를 건너뛴 것이다.

### 2.3 지금 상태 눈으로 보기

```bash
python tools/report.py trig --repeat 1     # 삼각법 7개 실행 (1분 안쪽), results/report.html 생성
```

`results/report.html`을 브라우저로 열면 수치표와 배치 그림을 볼 수 있다. 무엇을 만들어야 하는지 감을 잡는 용도다.
구현 전에 `python tools/report.py nfp`를 돌리면 "nfp: 미구현, 건너뜀"이 나오고,
`python tools/run.py nfp ...`는 `NotImplementedError: NFP 미구현`으로 끝난다. 정상이다.

### 2.4 내 브랜치 만들기

```bash
git switch main && git pull
git switch -c 이름/nfp        # 예: yujin/nfp, seungsu/raster
# ... 작업 ...
ruff format . && ruff check . && pytest
git add -A && git commit -m "nfp: 볼록 다각형 민코프스키 합 구현"
git push -u origin 이름/nfp    # 처음 한 번만 -u, 이후에는 git push
```

push하면 GitHub Actions(CI)가 자동으로 검사한다. 저장소 Actions 탭에서 초록 체크인지 확인한다.

## 3. 공통 실행 틀 (`nesting/runner.py`)

세 방법이 똑같은 조건에서 측정되도록 만든 틀이다. 흐름은 이렇다.

```
nest(inst)                                   # algorithms/<방법>/__init__.py
 └ run(inst, MyPlacer)                       # nesting/runner.py
    ├ seq = fixed_sequence(inst)             # [(부품 id, 회전), ...] 면적 큰 순, 사본마다 1개
    ├ placer = MyPlacer(inst, **params)      # 담당자 클래스 생성
    ├ for item, rot in seq:
    │    x, y = placer.place(item, rot)      # ★ 담당자가 구현하는 부분
    │    Placement(item, 사본 번호, rot, x, y) 생성
    ├ 전체 시간, feasible_timer 시간 합산
    └ make_solution(...)                     # 사용 길이, 활용률 계산 → Solution
```

| 공통 틀이 하는 일 | 담당자가 하는 일 |
|---|---|
| 순서와 회전 고정, 조각을 하나씩 `place()`에 넘김 | 놓을 수 있는 위치 계산 |
| 사본 번호 부여, Placement 생성 | Bottom-Left 규칙으로 위치 하나 선택 |
| 전체 시간 측정, `feasible_timer` 구간 합산 | 가능 위치 계산 구간을 `feasible_timer`로 감싸기 |
| 사용 길이, 활용률 계산 | 놓은 조각을 내부에 기록 (다음 조각 계산용) |
| | 계산량 집계 (`counters()`) |

담당자는 순서를 바꾸거나, 시간을 직접 재거나, Solution을 직접 만들지 않는다. 그렇게 하면 세 방법의 측정 조건이 달라진다.

## 4. 구현할 것

### 4.1 클래스 모양 (NFP 예시, 래스터도 같다)

```python
from nesting.runner import Placer, run


class NFPPlacer(Placer):
    name = "nfp"
    REQUIRED_COUNTERS = ("nfp_computed", "nfp_cache_hits", "candidate_evals")

    def __init__(self, inst, **params):
        super().__init__(inst, **params)  # self.inst, self.W(원판 폭), self.params 준비됨
        self.placed = []  # 놓은 조각 기록 (자료구조는 자유)
        self.nfp_computed = 0
        self.nfp_cache_hits = 0
        self.candidate_evals = 0

    def place(self, item: int, rotation: float) -> tuple[float, float]:
        poly = self.rotated(item, rotation)  # 원점 기준으로 회전한 다각형
        with self.feasible_timer():  # 가능 위치 계산 구간 (시간 측정)
            x, y = ...  # Bottom-Left 위치 계산
        self.placed.append(...)  # 이 조각을 놓았다고 기록
        return x, y

    def counters(self) -> dict:
        return {
            "nfp_computed": self.nfp_computed,
            "nfp_cache_hits": self.nfp_cache_hits,
            "candidate_evals": self.candidate_evals,
        }


def nest(inst, *, seed=0, time_limit_s=None, **params):
    return run(inst, NFPPlacer, **params)
```

`nest()`와 클래스 이름, `name`, `REQUIRED_COUNTERS`는 이미 파일에 들어 있다. `place()`와 `counters()` 안만 채우면 된다.

### 4.2 `place()`의 입력과 출력

- **입력**: `item`(부품 id), `rotation`(회전 각도, 도 단위, 반시계). 이 조각의 모양은 `self.rotated(item, rotation)`으로 얻는다.
- **출력**: `(x, y)`. **회전한 다각형 `self.rotated(item, rotation)`의 모든 점에 (x, y)를 더한 것이 최종 위치다.**
- 원판: y 방향 폭이 `self.W`(0 ≤ y ≤ W), x 방향은 0부터 오른쪽으로 무한. 목표는 x 방향 사용 길이를 줄이는 것이다.
- `rotated()`가 돌려주는 다각형은 원점 기준으로 회전만 한 것이라 바운딩 박스 왼쪽 아래가 (0, 0)이 아닐 수 있다(음수일 수도 있다).
  바운딩 박스 왼쪽 아래를 (X, Y)에 두고 싶다면 `minx, miny, _, _ = geometry.bbox(poly)`로 구한 뒤 `x, y = X - minx, Y - miny`를 돌려준다.
- 다각형은 `[[x, y], ...]` 리스트이고 반시계 방향이며 첫 점을 끝에 반복하지 않는다. 볼록이 아닐 수 있다(오목 조각이 많다). 구멍은 없다.

### 4.3 위치 선택 규칙 (Bottom-Left)

놓을 수 있는 위치 중 **x가 가장 작은 곳, x가 같으면 y가 가장 작은 곳**을 고른다. 기준점은 바운딩 박스 왼쪽 아래로 본다.

### 4.4 허용 오차와 맞닿음

- 허용 오차: `eps = collision.tolerance_for(self.W)` (원판 폭의 100만분의 1).
- **맞닿는 것은 허용**한다. 변끼리 닿거나 꼭짓점이 닿는 것은 겹침이 아니다. 내부끼리 조금이라도 겹치면 안 된다.
- 원판 밖으로 eps보다 많이 나가면 안 된다.

### 4.5 쓸 수 있는 공용 도구

| 도구 | 위치 | 쓰임 |
|---|---|---|
| `self.rotated(item, rot)` | Placer | 회전한 다각형 (캐시됨) |
| `self.feasible_timer()` | Placer | `with` 문으로 가능 위치 계산 구간을 감쌈. 중첩해서 쓰지 말 것 |
| `self.W`, `self.inst`, `self.params` | Placer | 원판 폭, 인스턴스 전체, 실행 매개변수 |
| `geometry.bbox, rotate, translate, area, signed_area, is_convex, point_in_polygon, segments_intersect` | `nesting/geometry.py` | 기본 기하 연산 |
| `collision.Shape(poly)`, `collision.overlap(a, b, eps)` | `nesting/collision.py` | 두 다각형 겹침 판정. **디버깅할 때 고른 위치가 정말 안 겹치는지 교차 확인용**으로만 쓴다. 이걸로 위치를 찾으면 삼각법이 되어 버린다 |
| `collision.tolerance_for(W)` | `nesting/collision.py` | 허용 오차 |

### 4.6 방법별 구현 순서 요약

자세한 원리와 메모는 각 파일 맨 위 설명(docstring)에 있다.

**NFP** (`algorithms/nfp/__init__.py`)
1. 볼록 다각형 A, B의 NFP = A ⊕ (−B) (민코프스키 합). 두 다각형 변을 각도 순으로 이어 붙인다.
2. 오목 조각은 볼록 조각들로 나눈다(삼각분할 후 볼록이 유지되는 것끼리 합치기).
3. IFP: 원판 안에 들어가는 기준점 영역. 직사각형 원판이라 직사각형이다.
4. 후보점: IFP 꼭짓점, 각 NFP 꼭짓점, NFP 변끼리 교점, NFP 변과 IFP 경계의 교점.
5. 후보 중 IFP 안이고 어떤 NFP 조각 내부에도 없는 점에서 Bottom-Left로 고른다(NFP 경계 위는 맞닿음이라 허용).
6. NFP는 (부품, 회전, 부품, 회전) 조합마다 한 번만 계산해 캐시한다.
- 계산량: `nfp_computed`(새로 계산한 NFP 수), `nfp_cache_hits`(캐시 재사용 수), `candidate_evals`(판정한 후보점 수)

**래스터** (`algorithms/raster/__init__.py`)
1. 격자 크기 `cell = W / rows`. `rows`는 `self.params.get("rows", 기본값)`으로 받는다.
2. 조각을 칸 단위 비트맵으로 바꾼다. **조금이라도 걸치는 칸은 모두 칠한다**(보수적 래스터화). 행마다 정수 하나의 비트로 표현하면 겹침 검사가 비트 AND가 된다.
3. 원판 비트맵을 x(열) 왼쪽부터, 각 열에서 y 아래부터 훑어 처음 들어가는 칸을 고른다.
4. 칸 좌표를 실제 (x, y)로 바꾼다. 조각 기준점과 격자가 어긋나지 않게 주의한다.
5. 비트맵은 (부품, 회전)마다 한 번만 만들어 캐시한다.
- 계산량: `cell_size`(격자 한 칸 크기), `grid_checks`(격자 겹침 검사 횟수)
- 보수적으로 칠하면 격자에서 안 겹칠 때 실제로도 안 겹치므로 검증기를 자동으로 통과한다. 대신 격자 크기만큼 틈이 생긴다.
- 격자 크기를 바꿔 가며 품질과 속도가 어떻게 변하는지가 래스터 파트 분석의 핵심이다.

## 5. 제약 검사 (공통 규칙 만족 여부)

세 방법이 반드시 지켜야 하는 공통 규칙(제약)을 자동으로 확인한다. 검사 내용은 `nesting/constraints.py`, 테스트는 `tests/test_constraints.py`.

| 번호 | 제약 | 위반하면 생기는 일 |
|---|---|---|
| 1 | Placer를 상속하고 `name`이 등록 이름과 같다 | 리포트, 웹에서 방법을 못 찾음 |
| 2 | 조각마다 배치가 정확히 하나 (개수, 사본 번호 0..수량−1) | 빠지거나 중복된 조각 |
| 3 | 배치 순서와 회전이 `fixed_sequence`와 같다 | 비교가 불공정해짐 |
| 4 | 검증기 통과 (겹침 없음, 원판 안, 길이와 활용률 일치) | 실제로 자를 수 없는 도면 |
| 5 | 필수 stats 키가 있다 (`time_place_ms`, `time_feasible_ms`, `params`, `REQUIRED_COUNTERS`) | 결과표를 못 만듦 |
| 6 | 0 < 가능 위치 계산 시간 ≤ 전체 시간 | `feasible_timer`를 안 썼거나 잘못 씀 |
| 7 | 결정적이다 (두 번 돌리면 같은 배치) | 실험 재현이 안 됨. 무작위를 쓰지 말 것 |

검사하는 인스턴스: 정사각형 5개(squares), 오목 L자와 사각형(concave), fu, jakobs1.

```bash
pytest -q tests/test_constraints.py          # 제약 검사만
pytest -q tests/test_constraints.py -k nfp   # 내 방법만
pytest                                       # 전체 (push 전에)
```

- `place()`가 `NotImplementedError`를 내면 그 방법의 검사는 건너뛴다(s로 표시). 구현하면 자동으로 검사가 시작된다.
- 실패하면 어떤 제약을 어겼는지 문장으로 나온다. 예: `배치 순서나 회전이 fixed_sequence와 다름`, `검증기 실패: [검증 실패 (66건)] ... 겹침: item 5#0 ↔ item 2#0`.
- 모든 브랜치 push마다 GitHub Actions(CI)가 같은 검사를 돌린다. 빨간 X면 고친다.

## 6. 결과 확인 (실행 리포트)

```bash
python tools/report.py nfp                   # 7개 인스턴스, 시간 5회 평균
python tools/report.py nfp --repeat 1        # 빠르게 확인
python tools/report.py trig nfp raster       # 세 방법 함께
python tools/run.py nfp data/instances/sparrow/fu.json   # 인스턴스 하나만
```

`results/report.html`(수치표, 배치 그림, 제약 만족 여부)과 `results/<방법>.csv`(보고서 결과표용)가 생긴다.
`results/` 폴더는 git에 올리지 않는다.

리포트 열의 뜻

| 열 | 뜻 |
|---|---|
| 사용 길이 | 원단을 x 방향으로 어디까지 썼는지. 짧을수록 좋음 |
| 하한 대비 | 이론상 최소 길이(조각 면적 합 ÷ 폭)보다 몇 % 더 썼는지 |
| 활용률(%) | 사용한 원단 중 조각이 된 비율. 높을수록 좋음 |
| 전체 시간(ms) | 배치 전체 시간, 반복 평균 ± 표준편차 |
| 가능 위치 계산(ms), 비율 | `feasible_timer`로 감싼 시간과 그 비율 |
| 방법별 계산량 | `counters()`가 돌려준 값 |
| 제약 만족 | 5절 제약을 모두 지켰는지 |

## 7. 하지 말아야 할 것

- `nesting/` 폴더나 `docs/SPEC.md`를 고치지 않는다. 고쳐야 하면 팀 단체방에 먼저 말한다(모든 방법에 영향).
- 순서를 바꾸거나 회전을 고르지 않는다. 받은 `rotation`을 그대로 쓴다.
- `time.perf_counter()`로 시간을 직접 재거나 `make_solution()`을 직접 부르지 않는다.
- `feasible_timer()`를 중첩하거나 가능 위치 계산과 상관없는 부분(결과 기록 등)까지 감싸지 않는다.
- 무작위(random)를 쓰지 않는다. 결과가 매번 같아야 한다.
- `collision.overlap`으로 후보를 하나씩 검사해 위치를 찾지 않는다. 그건 삼각법이다.
- shapely 같은 외부 기하 라이브러리를 핵심 계산에 쓰지 않는다. 직접 구현한 알고리즘을 비교하는 과제다. 디버깅에서 대조용으로 쓰는 건 괜찮다.

## 8. 끝났는지 확인하는 목록

- [ ] `pytest`에서 내 방법의 제약 검사가 건너뛰지 않고 모두 통과
- [ ] `python tools/report.py <방법>`에서 7개 모두 "제약 만족"
- [ ] `ruff format .`와 `ruff check .` 통과 (CI가 검사함)
- [ ] 자기 브랜치에 push하고 CI 초록 체크 확인
- [ ] PR로 main에 합치기
- [ ] `results/<방법>.csv`를 1번(실험 총괄)에게 전달, 보고서 4장 내 파트 작성(보고서 양식 참고)

## 9. AI 도구와 함께 작업할 때

AI에게 처음 줄 것: 이 문서 전체, 내 방법 파일(`algorithms/nfp/__init__.py` 또는 `algorithms/raster/__init__.py`),
`nesting/runner.py`, 완성 예시인 `algorithms/trig/decoder.py`. 필요하면 `nesting/geometry.py`도 준다.

첫 요청 예시

```
위 안내서와 파일을 읽어. 나는 SheetNest의 NFP 담당이다.
algorithms/nfp/__init__.py의 NFPPlacer.place()와 counters()만 구현해 줘.
nesting/ 폴더와 다른 알고리즘 파일은 고치지 마.
4.2절 좌표 규칙(rotated 다각형에 (x, y)를 더한 것이 최종 위치)과
4.3절 Bottom-Left 규칙, 4.4절 맞닿음 허용을 지켜.
가능 위치 계산은 with self.feasible_timer(): 안에서 해.
먼저 볼록 다각형 NFP(민코프스키 합)부터 단계별로 구현하고, 각 단계마다 테스트할 방법도 알려 줘.
```

AI가 만든 코드를 받으면 반드시 `pytest -q tests/test_constraints.py -k <방법>`과 `python tools/report.py <방법> --repeat 1`로 확인한다.
테스트가 통과해도 배치 그림을 보고 이상한 빈틈이 없는지, 삼각법보다 훨씬 나쁜 인스턴스가 없는지 직접 본다.
결과가 나쁘면 그 원인을 이해하는 것까지가 담당 업무다(보고서와 발표 질문 대비).

## 10. 파일 지도

```
algorithms/
  nfp/__init__.py        ← NFP 담당이 채울 파일
  raster/__init__.py     ← 래스터 담당이 채울 파일
  trig/decoder.py        완성 예시 (삼각법)
  __init__.py            방법 등록 (REGISTRY, COMPARED)
nesting/
  runner.py              공통 실행 틀 (Placer, run)
  constraints.py         제약 검사 내용
  sequence.py            고정 순서
  geometry.py            기하 함수
  collision.py           겹침 판정 (디버깅 대조용)
  validate.py            해 검증기
  model.py               Instance, Solution 형식
tests/test_constraints.py  제약 검사 테스트
tools/report.py          실행 리포트
tools/run.py             인스턴스 하나 실행
experiments/selected.txt 실험용 인스턴스 7개
docs/SPEC.md             전체 규칙 (5절이 비교 구조)
```
