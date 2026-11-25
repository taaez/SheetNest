# SheetNest 공통 입출력 형식 (v1 초안)

모든 알고리즘(삼각법, NFP, 래스터)은 **같은 입력(instance JSON)을 받아 같은 출력(solution JSON)을 낸다.**
이 형식이 바뀌면 전원에게 공지하고 `format` 버전을 올린다.

## 1. 좌표계와 용어

| 용어 | 정의 |
|---|---|
| 원판(sheet) | 폭 `W`가 고정되고 길이는 무한한 띠(strip). 목표는 사용 길이 최소화 |
| 좌표 | x = 길이 방향(최소화 대상), y = 폭 방향, **y축은 위쪽이 +** (수학 좌표) |
| 배치 가능 영역 | `0 ≤ x`, `0 ≤ y ≤ W` |
| 회전 | 원점 기준 **반시계** 방향, 단위 도(degree) |
| 부품 종류(item) | 같은 모양의 부품 묶음. `quantity`개를 모두 배치해야 함 |

## 2. 입력: instance JSON (`format: "nesting-instance/1"`)

```json
{
  "format": "nesting-instance/1",
  "name": "fu",
  "unit": null,
  "source": "sparrow:fu.json",
  "sheet": { "width": 38.0038 },
  "items": [
    { "id": 0, "quantity": 1, "rotations": [0, 90, 180, 270],
      "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]] }
  ],
  "meta": { "converted_from": "sparrow-json" }
}
```

| 필드 | 형식 | 규칙 |
|---|---|---|
| `name` | 문자열 | 인스턴스 이름 |
| `unit` | 문자열 또는 null | `mm`, `cm`, `in` 등. 벤치마크는 단위 없음(null) |
| `source` | 문자열 | `출처:파일명` (sparrow / esicup / dxf / svg) |
| `sheet.width` | 양수 | 원판 폭 W |
| `items[].id` | 정수 | 0부터 시작, 중복 불가 |
| `items[].quantity` | 정수 ≥ 1 | 배치해야 할 개수 |
| `items[].rotations` | 각도 목록 | 허용 회전. 비어 있으면 안 됨 |
| `items[].polygon` | `[[x, y], ...]` | 아래 정규화 규칙을 반드시 만족 |
| `items[].name` | 문자열(선택) | 원본 부품 이름 |
| `meta` | 객체 | 변환 정보, 경고 등 자유 기록. 알고리즘은 읽지 않음 |

**다각형 정규화 규칙** (변환기가 보장, `check_instance()`로 검사)
1. 단순 다각형(자기 교차 없음), 꼭짓점 3개 이상, 구멍 없음(v1)
2. **반시계 방향**, 마지막 점을 첫 점과 겹쳐 쓰지 않음(닫지 않음)
3. 회전 0°에서 바운딩 박스 최솟값이 **(0, 0)**
4. 시작 꼭짓점은 y가 가장 작은 점(같으면 x가 가장 작은 점)
5. 중복점·일직선 위 중간점 제거

## 3. 출력: solution JSON (`format: "nesting-solution/1"`)

```json
{
  "format": "nesting-solution/1",
  "instance": "fu",
  "algorithm": "bl",
  "length": 31.0,
  "utilization": 0.9193,
  "time_ms": 12.3,
  "stats": { "overlap_checks": 18234, "seed": 0, "params": {} },
  "placements": [
    { "item": 0, "copy": 0, "rotation": 90, "x": 10.0, "y": 0.0 }
  ]
}
```

| 필드 | 규칙 |
|---|---|
| `algorithm` | `trig`, `nfp`, `raster` 등 짧은 이름 |
| `placements[]` | 모든 부품 사본마다 정확히 1개. `copy`는 0 ~ quantity-1 |
| `rotation` | 해당 item의 `rotations` 중 하나 |
| `x`, `y` | 배치 변환의 이동량 |
| `length` | 배치된 모든 부품의 x 최댓값 |
| `utilization` | 부품 면적 합 ÷ (W × length) |
| `time_ms` | **배치 결정 단계만** 측정 (파일 읽기·변환 제외) |
| `stats.overlap_checks` | 겹침 판정 함수 호출 횟수 (핵심부 비교 근거, 필수) |
| `stats.seed` | 난수를 쓰는 알고리즘은 필수 |

**배치 변환 (모두 이 식 하나만 사용)**

```
배치된 꼭짓점 p' = R(rotation) · p + (x, y)
```

`p`는 instance의 정규화된 꼭짓점이고 `R`은 원점 기준 반시계 회전이다.
회전 후에는 bbox 최솟값이 (0,0)이 아닐 수 있으므로, 원하는 위치에 놓으려면
`nesting.geometry.rotate()`로 돌린 뒤 bbox를 보고 x, y를 정한다.
코드에서는 `nesting.geometry.transform(poly, rotation, x, y)`를 쓰고, length·utilization은
`nesting.model.make_solution()`으로 계산한다(직접 계산 금지, 모두 같은 함수 사용).

## 4. 유효한 해의 조건 (검증기 `nesting/validate.py`가 확인)

1. 모든 부품 사본이 정확히 한 번씩 배치됨
2. 각 부품의 `rotation`이 허용 목록에 있음
3. 모든 꼭짓점이 `0 ≤ x`, `0 ≤ y ≤ W` 안에 있음
4. 어떤 두 부품도 내부가 겹치지 않음 (**변·꼭짓점끼리 닿는 것은 허용**)
5. `length`, `utilization` 값이 3절 정의와 일치

**허용 오차**: `eps = 1e-6 × W` (원판 폭 대비 상대값, `collision.tolerance_for(W)`).
거리 기준이며, 이보다 작은 파고듦·틈은 무시한다. 벤치마크마다 W가 38~20,000으로 달라 상대값을 쓴다.

**부품 간격(kerf)**: `spacing` 매개변수(기본 0). 0보다 크면 두 부품 사이 거리가 `spacing` 미만인 것도 위반이다.
실험 기본값은 0이며, 반영 여부는 회의에서 확정한다.

```bash
python tools/validate.py <instance.json> <solution.json> [--spacing 0.5]
```

## 5. 비교 구조와 알고리즘 공통 인터페이스

### 5.1 가능 위치 계산 방법 3가지를 비교한다

배치는 세 단계로 이루어진다. 실행 시간의 95~99.6%를 가능 위치 계산이 차지하므로(5.5절 측정),
교수님 조건인 '전체 성능을 좌우하는 핵심 부분에서 비교'를 지키기 위해 이 단계를 비교한다.

| 단계 | 역할 | 이 프로젝트 |
|---|---|---|
| 배치 순서와 회전 | 어떤 순서·회전으로 놓을지 | 고정: 면적 큰 순, 원판 폭에 들어가는 첫 회전 (`nesting/sequence.py`) |
| 위치 선택 규칙 | 놓을 수 있는 위치 중 어디를 고를지 | 고정: Bottom-Left (x 최소, 같으면 y 최소). 정밀도는 방법마다 다르다(아래 표) |
| 가능 위치 계산 | 어디에 놓을 수 있는지 | **비교 대상**: ① 삼각법(직접 판정) ② NFP ③ 래스터 |

세 방법은 문헌에서 비정형 배치의 기하를 다루는 대표 방법으로 꼽힌다(Bennell & Oliveira, 2008).

| 방법 | 폴더 | 원리 | Bottom-Left 정밀도 | 상태 |
|---|---|---|---|---|
| 삼각법(직접 판정) | `algorithms/trig` | 다각형 그대로, 시험하는 위치마다 선분 교차·점 포함 검사. 위치는 Bottom-Left-Fill(Burke 외, 2006) 순서로 훑음 | Δ 간격 열 위에서 정확 (y는 연속) | 구현 완료 |
| NFP | `algorithms/nfp` | 겹치게 되는 기준점 영역(민코프스키 합)을 미리 계산, 점 하나의 포함 검사로 판정 | x, y 모두 정확 | 구현 완료 |
| 래스터 | `algorithms/raster` | 원판·부품을 격자 비트맵으로 바꿔 비트 AND로 판정 | Δ 간격 격자 위에서 정확 (보수적 격자) | 구현 완료 |

Δ = 원판 폭 W / `rows`이고 삼각법과 래스터가 같은 값을 쓴다(기본 `rows` = 200).
직접 판정은 주어진 위치가 가능한지에만 답하므로 정확한 Bottom-Left 위치를 구하려면 NFP 같은 영역 계산이 필요하다.
그래서 세 방법은 같은 규칙을 각자의 표현이 허용하는 범위에서 지키고, 결과 차이는 정밀도와 계산 비용의 차이로 해석한다.
삼각법과 래스터는 Δ 간격 위치만 보므로, 정확한 Bottom-Left 자리가 폭이 Δ보다 좁은 틈이면 그 자리를 건너뛰고 더 오른쪽에 놓을 수 있다.

각 폴더의 `__init__.py`에 원리, 배치 절차, 구현 메모가 있다.

### 5.2 공통 실행 틀과 제약 검사

세 방법은 공통 실행 틀(`nesting/runner.py`) 위에서 돈다. 담당자는 `Placer`를 상속해 `place()` 하나만 구현한다.

```python
class NFPPlacer(Placer):
    name = "nfp"
    REQUIRED_COUNTERS = ("nfp_computed", "nfp_cache_hits", "candidate_evals")

    def place(self, item: int, rotation: float) -> tuple[float, float]:
        poly = self.rotated(item, rotation)  # 원점 기준으로 회전한 다각형
        with self.feasible_timer():  # 가능 위치 계산 구간
            ...  # Bottom-Left로 (x, y) 결정
        ...  # 놓은 부품을 내부 상태에 기록
        return x, y

    def counters(self) -> dict: ...


def nest(inst, *, seed=0, time_limit_s=None, **params) -> Solution:
    return run(inst, NFPPlacer, **params)
```

| 공통 실행 틀이 하는 일 | 방법이 하는 일 |
|---|---|
| `fixed_sequence`로 순서와 회전 고정, 부품을 하나씩 `place()`에 넘김 | 가능 위치 계산, Bottom-Left 선택 |
| 사본 번호 부여, `Placement` 생성 | 놓은 부품 기록 |
| 전체 시간 측정, `feasible_timer` 구간 합산 | 가능 위치 계산을 `feasible_timer`로 감싸기 |
| `make_solution`으로 length, utilization 계산 | 계산량(`counters`) 집계 |

`place()`가 돌려주는 (x, y)는 `Placement`의 x, y와 같다. 원래 다각형을 원점 기준으로 rotation도 반시계 회전한 뒤
(x, y)만큼 옮긴 것이 최종 위치다. 원판 폭은 y 방향, 길이는 x 방향이다.

`feasible_timer`는 생성기 기반 contextmanager를 쓰지 않는다. 호출마다 수 마이크로초가 들어 비율을 왜곡했기 때문이다
(삼각법 shirts에서 97.8%가 91%로 측정됨). 객체 하나를 재사용해 오버헤드를 줄였다.

제약 검사 테스트(`tests/test_constraints.py`, 검사 내용은 `nesting/constraints.py`)는 세 방법 모두에 같은 규칙을 검사한다.
구현 전인 방법은 건너뛰고, 구현하면 자동으로 검사된다.

1. `Placer`를 상속하고 이름이 등록 이름과 같다
2. 부품 사본마다 배치가 정확히 하나 있다
3. 배치 순서와 회전이 `fixed_sequence`와 같다
4. 검증기를 통과한다
5. 필수 stats 키(공통 키와 `REQUIRED_COUNTERS`)가 있다
6. 0 < `time_feasible_ms` ≤ `time_place_ms`
7. 결정적이다

`python tools/report.py [방법...]`은 선정 7개 인스턴스에 같은 검사를 돌리고 수치표와 배치 그림을 `results/report.html`로,
결과표 수치를 `results/<방법>.csv`로 저장한다.

### 5.3 시간·계산량 기록 (필수)

| stats 키 | 의미 |
|---|---|
| `time_place_ms` | 배치 전체 시간 |
| `time_feasible_ms` | 그중 가능 위치 계산에 쓴 시간 |
| `params` | 사용한 매개변수 (삼각법, 래스터의 `rows` 등) |
| 방법별 계산량 | 삼각법 `overlap_checks`, `bbox_rejects`, `columns`, `lifts` / NFP `nfp_computed`, `candidate_evals` / 래스터 `cell_size`, `grid_checks` |

세 방법 모두 결정적이므로 품질(L, U)은 1회 측정으로 충분하고, 시간은 같은 컴퓨터에서 여러 번(예: 5회) 재서 평균을 낸다.

### 5.4 삼각법 배치 동작 (`algorithms/trig/decoder.py`)

Bottom-Left-Fill(Burke 외, 2006) 방식으로 부품을 순서대로 하나씩 놓는다. 부품마다:
1. **열 훑기**: x = 0, Δ, 2Δ, ... 순서로 본다 (Δ = W / `rows`, 기본 200).
2. **열에서 가장 낮은 위치**: y = 0에 놓아 보고, 겹치는 부품이 있으면 그 부품과의 겹침이 풀리는 가장 낮은 높이로 올린다.
   그 높이는 내 꼭짓점이 상대 변 위에 얹히거나 상대 꼭짓점이 내 변 아래에 닿는 높이(꼭짓점-변 접촉 높이) 중 하나이므로,
   후보를 낮은 순서로 판정해 정확히 구한다. 올린 뒤 다시 모든 부품과 판정해 겹침이 없을 때까지 반복한다.
3. **선택**: 원판 위로 넘치면 다음 열로 넘어가고, 처음 들어가는 열의 그 높이를 고른다.
   즉 Δ 간격 열로 제한한 위치 중에서 "x 최소, 같으면 y 최소"인 위치를 정확히 고른다.

결과를 바꾸지 않는 가속 두 가지를 쓴다. 같은 부품·회전의 다음 사본은 직전 사본의 열부터 보고(놓인 부품이 늘면 가능 영역은
줄기만 한다), 모든 놓인 부품의 오른쪽 끝을 지난 열은 판정 없이 y = 0에 놓는다. 두 가속을 끄고 돌려도 배치가 같음을 확인했다.
위치 계산 전체를 `feasible_timer`로 감싼다.

이전 구현(바운딩 박스 경계 후보 + 이진 탐색 미끄러뜨리기)은 시험할 위치가 적어 오목한 틈 같은 자리를 놓쳤고,
같은 상태에서 NFP가 구한 정확한 Bottom-Left 위치와 비교하면 x가 평균 0.6~44% W 뒤에 놓였다(선정 인스턴스 중 gardeyn1 제외 6개).
BLF로 바꾼 뒤 평균은 shapes0 6.7% W, 나머지 0.7% W 이하다. 다만 폭이 Δ보다 좁은 틈을 건너뛰는 경우가 있어
한 번의 배치에서 최대 차이는 jakobs1 10% W, trousers 16% W, shapes0 48% W까지 나온다.

겹침 판정(`nesting/collision.py`)은 바운딩 박스 필터 → 두 박스 교집합 근처 변의 관통 검사 → 포함 검사 순서다.
shapely와 무작위 12,000쌍 비교 불일치 0건. 허용 오차 eps = 1e-6 × W, 맞닿음은 허용.

### 5.5 단계별 시간 측정 (이전 삼각법, 면적 큰 순, 개발 환경)

아래 표는 이전 삼각법 구현으로 잰 값이다. 현재 구현으로 다시 측정할 예정이다.

| 인스턴스 | 배치 1회 | 가능 위치 계산 | 위치 선택·후보 생성 | 순서 바꾸기 1회 |
|---|---|---|---|---|
| fu | 7ms | 94.5% | 4.4% | 약 1µs |
| jakobs1 | 38ms | 97.1% | 2.5% | 약 1µs |
| shapes0 | 292ms | 98.3% | 1.6% | 약 1µs |
| shirts | 1023ms | 97.8% | 2.1% | 약 1µs |
| trousers | 274ms | 97.5% | 2.4% | 약 1µs |
| swim | 742ms | 98.6% | 1.3% | 약 1µs |
| gardeyn1 | 3047ms | 99.6% | 0.3% | 약 1µs |

순서 탐색을 비교하던 이전 구성은 비교 대상이 전체 시간의 0.01% 미만이라 핵심부 비교 조건에 맞지 않아 폐기했다.

## 6. 데이터 출처별 변환 규칙

| 출처 | 원판 폭 | 회전 | 비고 |
|---|---|---|---|
| sparrow JSON | `strip_height` | `discrete` 그대로, `continuous`는 `--continuous-step` 간격(기본 90°) | `zones` 필드 무시. 일부 폭은 원본보다 0.01% 크다(sparrow의 여유값) |
| ESICUP XML | 원판 다각형의 y 범위 | `<enumeration angle>` | `up-left` 원점 파일은 y를 뒤집음(문제 전체가 거울상이 되므로 동치) |
| DXF | `--width` 또는 `--sheet-layer`의 사각형 높이 | 기본 0/90/180/270 | 블록 분해, 곡선은 `--flatten-tol`로 근사, 구멍 제외 |
| SVG | `--width` 또는 `id="sheet"` 사각형 높이 | 기본 0/90/180/270 | 단위 `--unit`(기본 mm), y 뒤집기, 구멍 제외 |

DXF·SVG는 같은 모양 부품을 자동으로 합쳐 `quantity`를 올린다(`--no-merge`로 끔).
현재는 회전 없이 완전히 같은 모양만 합친다.

## 7. 아직 정하지 않은 것 (회의 안건)

- [ ] 부품 간 최소 간격(kerf) 실험 반영 여부 (검증기·겹침 판정은 `spacing`으로 이미 지원, 기본 0)
- [ ] 구멍 안에 작은 부품 넣기 지원 여부
- [ ] 자유 회전 인스턴스(`_c`) 실험 포함 여부
- [ ] 삼각법과 래스터의 `rows` 기본값(200)과 격자 크기 실험 범위
- [ ] 회전을 고정할지, 위치 선택 단계에서 허용 회전을 모두 시도해 가장 좋은 것을 고를지
