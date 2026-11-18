"""가능 위치 계산 방법 3. 래스터(격자). 구현 예정.

원리
  원판과 부품을 격자로 바꾼다. 부품이 조금이라도 걸치는 칸은 모두 칠한다(보수적 래스터화).
  새 부품을 어떤 위치에 놓을 때 원판에서 이미 칠해진 칸과 부품의 칸이 하나라도 겹치면 불가능하다.
  부품을 넉넉하게 칠했으므로 격자에서 안 겹치면 실제 다각형도 안 겹친다. 결과는 항상 유효하지만
  격자 크기만큼 틈이 생겨 활용률은 손해를 본다.

배치 (순서와 회전은 nesting.sequence.fixed_sequence로 고정, 위치 선택은 Bottom-Left)
  1. 격자 크기 cell = 원판 폭 / params["rows"] (기본값은 실험으로 정함, 예: 폭 방향 200칸)
  2. 부품을 회전한 뒤 칸 단위 비트맵으로 바꾼다. 행마다 정수 하나의 비트로 표현하면
     겹침 검사가 비트 AND 연산이 되어 순수 Python에서도 빠르다.
  3. 원판 비트맵을 열(x) 방향으로 왼쪽부터, 각 열에서 아래(y)부터 훑어 처음 들어가는 칸을 고른다.
  4. 고른 칸의 좌표를 실제 x, y로 바꾼다. 부품 기준점과 격자가 어긋나지 않게 주의한다.

구현 메모
  래스터화는 다각형 내부 칸(스캔라인 채우기)과 경계가 지나가는 칸을 모두 칠한다.
  부품 비트맵은 (부품, 회전) 조합마다 한 번만 만들어 캐시한다.
  격자 크기를 바꿔 가며 정확도와 속도의 맞교환을 실험하는 것이 분석의 핵심이다.
  결과는 반드시 nesting.validate.validate를 통과해야 한다(보수적 래스터화면 자동으로 통과).

시간 기록 (stats 필수 키, 삼각법과 같은 의미)
  time_place_ms     배치 전체 시간
  time_feasible_ms  가능 위치 계산에 쓴 시간 (래스터화 + 격자 겹침 검사)
  cell_size         격자 한 칸 크기, grid_checks 격자 겹침 검사 횟수
"""

from nesting.model import Instance, Solution


def nest(inst: Instance, *, seed: int = 0, time_limit_s: float | None = None, **params) -> Solution:
    raise NotImplementedError("래스터 미구현")
