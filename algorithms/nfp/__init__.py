"""No-Fit Polygon 기반 배치 (구현 예정).

구현 메모
- 볼록 다각형 A, B의 NFP = A ⊕ (−B) (민코프스키 합): 두 다각형의 변을 각도순으로 병합해 O(n+m).
- 오목 다각형은 볼록 조각으로 분할해 조각별 NFP를 구하고 합친다.
- IFP(원판 안쪽 가능 영역)는 직사각형: x ≥ −minx, miny' 범위 등 회전된 bbox로 계산.
- 놓을 수 있는 위치 = IFP 안이면서 모든 NFP 바깥. 후보(꼭짓점·교점) 중 x 최소 → y 최소 선택.
- NFP는 (부품 A, 회전 a, 부품 B, 회전 b) 조합마다 캐시해 재사용.
- 계산량 지표: NFP 방식은 overlap()을 거의 쓰지 않으므로, stats에 "candidate_evals"(후보 위치 평가 횟수),
  "nfp_computed"(NFP 계산 횟수)를 추가로 기록한다. (지표 정의는 팀 회의에서 확정)
- 최종 결과는 검증기(nesting.validate)를 통과해야 한다.
"""

from nesting.model import Instance, Solution


def nest(inst: Instance, *, seed: int = 0, time_limit_s: float | None = None, **params) -> Solution:
    raise NotImplementedError("NFP 배치 미구현")
