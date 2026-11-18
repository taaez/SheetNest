# SheetNest 공통 입출력 형식 (v1 초안)

모든 알고리즘(BL, NFP, GA)은 **같은 입력(instance JSON)을 받아 같은 출력(solution JSON)을 낸다.**
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
| `algorithm` | `bl`, `nfp`, `ga` 등 짧은 이름 |
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

## 5. 알고리즘 공통 인터페이스

```python
from nesting.model import Instance, Solution


def nest(inst: Instance, *, seed: int = 0, time_limit_s: float | None = None, **params) -> Solution: ...
```

- `algorithms/<이름>/__init__.py`에 구현하고 `algorithms/__init__.py`의 `REGISTRY`에 등록한다.
- `time_limit_s`가 주어지면 그 안에 가장 좋은 해를 반환한다.
- 결과는 `nesting.model.make_solution()`으로 만든다 (length·utilization 계산 통일).

**겹침 판정 (공통 모듈 `nesting/collision.py`)**

```python
from nesting import collision as c

eps = c.tolerance_for(inst.sheet_width)
a = c.Shape.placed(item.polygon, rotation, x, y)  # 변환 + 바운딩 박스 캐시
c.overlap(a, b, eps, spacing=0.0)  # 내부가 겹치면 True (맞닿음은 False)
c.inside_sheet(a, inst.sheet_width, eps)  # 원판 안인지
```

- 각자 겹침 판정을 따로 구현하지 않는다. 그래야 "핵심부 비교" 조건이 지켜진다.
- 판정 순서: 바운딩 박스 필터 → 변 관통 검사 → 포함 검사(꼭짓점·경계 안쪽 점).
- 순수 Python 구현. 실험에서 느리면 그때 최적화한다(결과는 바뀌면 안 됨, 테스트로 확인).

**계산량 기록 (필수)**

```python
c.reset_stats()  # 알고리즘 시작 시
...
make_solution(inst, "bl", placements, time_ms, {**c.get_stats(), "seed": seed, "params": params})
```

`overlap_checks`는 `overlap()` 호출 횟수, `bbox_rejects`는 그중 바운딩 박스 필터에서 끝난 횟수다.
NFP처럼 `overlap()`을 거의 쓰지 않는 알고리즘은 `candidate_evals` 등 자체 지표를 추가한다(정의는 회의에서 확정).

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
- [ ] NFP 방식의 계산량 지표 정의
