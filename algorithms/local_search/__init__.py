"""2. 지역 탐색 또는 시뮬레이티드 어닐링 (구현 예정, 둘 중 무엇으로 할지 회의에서 확정)

현재 순서를 조금씩 바꿔 가며 BL 디코더로 평가하고, 더 좋으면(또는 SA라면 확률적으로) 받아들인다.

구현 메모
- 시작 해: 정렬 그리디와 같은 순서 (공정 비교: 같은 출발점에서 얼마나 개선하는가)
- 이웃 해 만들기: 두 부품 순서 교환, 한 부품을 다른 위치로 이동, 한 부품의 회전 변경
- 평가: dec.length(seq)  (사용 길이, 작을수록 좋음)
- 지역 탐색: 좋아질 때만 이동 (막히면 재시작 등)
- 시뮬레이티드 어닐링: 나빠져도 exp(-Δ/T) 확률로 이동, 온도 T를 점점 낮춤
- 종료: time_limit_s 또는 평가 횟수 상한(params["max_evals"]) — 실험 조건은 회의에서 확정
- 난수는 random.Random(seed) 하나만 사용 (재현 가능)
- 결과: dec.to_solution(best_seq, "local_search", t0, {"seed": seed, "params": params, "history": [...]})
  history에 (평가 횟수, 최고 길이)를 기록하면 수렴 곡선을 그릴 수 있다.
"""

from nesting.model import Instance, Solution


def nest(inst: Instance, *, seed: int = 0, time_limit_s: float | None = None, **params) -> Solution:
    raise NotImplementedError("지역 탐색 / 시뮬레이티드 어닐링 미구현")
