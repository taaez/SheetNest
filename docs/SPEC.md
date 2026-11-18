# SheetNest 공통 입출력 형식 (v1 초안)

모든 알고리즘(정렬 그리디, 지역 탐색·SA, GA)은 **같은 입력(instance JSON)을 받아 같은 출력(solution JSON)을 낸다.**
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
| `algorithm` | `greedy`, `local_search`, `ga` 등 짧은 이름 |
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

### 5.1 세 층 중 '순서 탐색'만 비교한다

배치 알고리즘은 세 층으로 이루어진다. **같은 층의 대안끼리만 비교**해야 공정하므로 두 층은 고정한다.

| 층 | 역할 | 이 프로젝트 |
|---|---|---|
| 순서 탐색 | 어떤 순서·회전으로 놓을지 | **비교 대상**: ① 정렬 그리디 ② 지역 탐색 또는 시뮬레이티드 어닐링 ③ 유전 알고리즘 |
| 위치 선택 규칙 | 놓을 수 있는 위치 중 어디를 고를지 | 고정: Bottom-Left (문헌상 가장 널리 쓰이는 규칙) |
| 가능 위치 계산 | 어디에 놓을 수 있는지 | 고정: 후보점 + 공통 겹침 판정 |

- 아래 두 층은 `nesting/decoder.py`의 **BL 디코더** 하나로 구현되어 있고, 세 알고리즘이 그대로 쓴다.
- 고정 층(디코더 옵션 포함)은 본 실험 전에 확정하고 실험 도중 바꾸지 않는다.
- NFP 등 다른 가능 위치 계산 방법은 비교 대상이 아니다. 본 실험 이후 확장으로만 검토한다
  (바꿀 경우 세 알고리즘 실험을 처음부터 다시 돌린다).

### 5.2 알고리즘 함수

```python
def nest(inst: Instance, *, seed: int = 0, time_limit_s: float | None = None, **params) -> Solution: ...
```

- `algorithms/<이름>/__init__.py`에 구현, `algorithms/__init__.py`의 `REGISTRY`에 등록.
- 알고리즘이 정하는 것은 **배치 순서 `seq = [(item_id, rotation), ...]`** 뿐이다 (부품 사본마다 1개).
- 배치·결과 생성은 반드시 디코더로 한다.

```python
import time
from nesting import collision as c
from nesting.decoder import Decoder

c.reset_stats()
t0 = time.perf_counter()
dec = Decoder(inst)  # 고정 층
seq = dec.default_sequence()  # 예: 면적 큰 순 + 들어가는 첫 회전
L = dec.length(seq)  # 평가: 사용 길이 (작을수록 좋음)
...  # 순서 탐색 (알고리즘마다 다른 부분)
return dec.to_solution(best_seq, "ga", t0, {"seed": seed, "params": params, "history": history})
```

- 회전은 `dec.feasible_rotations(item)` 중에서만 고른다 (원판 폭보다 높은 회전은 오류).
- 난수는 `random.Random(seed)` 하나만 쓴다 (재현 가능).

### 5.3 BL 디코더 동작 (`nesting/decoder.py`)

부품을 seq 순서대로 하나씩 놓는다. 부품마다:
1. **후보점 생성**: 이미 놓인 부품들의 바운딩 박스 경계에 맞닿는 위치
   - x 후보: 0, 각 부품의 오른쪽 끝 / y 후보: 0, 각 부품의 위쪽 끝, 각 부품의 아래쪽 끝 − 높이, W − 높이
2. **Bottom-Left 선택**: 후보를 (x, y) 오름차순으로 검사해, 원판 안이고 겹치지 않는 첫 위치를 고른다
3. **미끄러뜨리기**(옵션 `slide=True`, 기본): 그 위치에서 아래로, 왼쪽으로 겹치기 직전까지 반복해서 민다
   (이진 탐색, 최소 단위 W × 1e-3). 바운딩 박스로는 못 들어가는 오목한 틈에 파고들게 한다.

결정적이다(같은 seq → 같은 배치). 겹침 판정은 공통 `collision.overlap()`만 쓴다.

### 5.4 겹침 판정 (`nesting/collision.py`)

```python
from nesting import collision as c

eps = c.tolerance_for(inst.sheet_width)
a = c.Shape.placed(item.polygon, rotation, x, y)  # 변환 + 바운딩 박스·변 박스 캐시
c.overlap(a, b, eps, spacing=0.0)  # 내부가 겹치면 True (맞닿음은 False)
```

- 판정 순서: 바운딩 박스 필터 → 두 박스 교집합 근처의 변만 관통 검사 → 포함 검사(꼭짓점·경계 안쪽 점)
- 순수 Python. shapely와 무작위 12,000쌍 비교 불일치 0건, 1회 평균 약 16µs (개발 환경 기준)

### 5.5 공정한 비교 규칙

세 알고리즘 모두 같은 디코더를 반복 호출하므로 **"같은 예산에서 누가 더 좋은 순서를 찾는가"**로 비교한다.

- 예산: 같은 시간(`time_limit_s`) 또는 같은 평가 횟수(`decode_calls`) — 조건은 회의에서 확정
- 출발점: 지역 탐색·GA는 정렬 그리디와 같은 순서에서 출발 (얼마나 개선하는지 측정)
- 무작위 알고리즘은 시드 10회 이상 반복, 평균·표준편차·최고값 보고
- `stats` 필수 항목: `overlap_checks`, `bbox_rejects`, `decode_calls`, `seed`, `params`
  (탐색 알고리즘은 `history`: (평가 횟수, 최고 길이) 목록 권장 → 수렴 곡선)

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
- [ ] 구멍 안에 작은 부품 넣기(v2) 지원 여부
- [ ] 자유 회전 인스턴스(`_c`) 실험 포함 여부와 이산화 간격
- [ ] 시간 제한 실험 조건(예: 10초, 60초), GA 반복 시드 수
- [ ] 순서 탐색 2번을 지역 탐색과 시뮬레이티드 어닐링 중 무엇으로 할지
- [ ] 디코더 미끄러뜨리기(slide) 사용 여부 (swim·gardeyn1은 개선, shirts는 악화, 시간 증가)
- [ ] 비교 예산 기준: 같은 시간 vs 같은 평가 횟수
