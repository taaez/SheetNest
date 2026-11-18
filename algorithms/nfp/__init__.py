"""가능 위치 계산 방법 2. No-Fit Polygon(NFP). 구현 예정.

원리
  고정된 부품 A와 놓을 부품 B가 있을 때, B의 기준점이 들어가면 A와 겹치게 되는 영역이 NFP다.
  A와 B의 겹침 검사가 'B의 기준점이 NFP 안에 있는가'라는 점 하나의 검사로 바뀐다.
  볼록 다각형의 NFP는 A와 −B(원점 대칭)의 민코프스키 합으로, 두 다각형의 변을 각도순으로
  이어 붙여 O(n + m)에 구한다. 오목 다각형은 볼록 조각으로 나눠 조각별 NFP를 구한다.

배치 (순서와 회전은 nesting.sequence.fixed_sequence로 고정, 위치 선택은 Bottom-Left)
  1. IFP: B가 원판 안에 있는 기준점 영역. 직사각형 원판이면 직사각형이다.
  2. 이미 놓인 부품마다 NFP를 그 부품 위치로 옮긴다.
  3. 후보점: IFP 꼭짓점, NFP 꼭짓점, NFP 변끼리의 교점, NFP 변과 IFP 경계의 교점.
  4. 후보 중 IFP 안이고 어떤 NFP 내부에도 없는 점에서 x 최소, 같으면 y 최소를 고른다.
     오목 부품을 볼록 조각으로 나눴다면 '모든 조각 NFP의 내부가 아닌 점'으로 판정해
     NFP 합집합을 직접 계산하지 않아도 된다.

구현 메모
  NFP는 (부품 A, 회전 a, 부품 B, 회전 b) 조합마다 한 번만 만들어 캐시한다.
  점이 NFP 경계 위에 있으면 맞닿음이므로 허용한다. 허용 오차는 collision.tolerance_for(W).
  결과는 반드시 nesting.validate.validate를 통과해야 한다. 디버깅할 때 collision.overlap으로
  고른 위치가 실제로 안 겹치는지 교차 확인할 수 있다.

시간 기록 (stats 필수 키, 삼각법과 같은 의미)
  time_place_ms     배치 전체 시간
  time_feasible_ms  가능 위치 계산에 쓴 시간 (NFP 생성 + 후보점 계산·판정)
  nfp_computed      새로 계산한 NFP 개수, nfp_cache_hits 캐시 재사용 횟수
  candidate_evals   판정한 후보점 개수
"""

from nesting.model import Instance, Solution


def nest(inst: Instance, *, seed: int = 0, time_limit_s: float | None = None, **params) -> Solution:
    raise NotImplementedError("NFP 미구현")
