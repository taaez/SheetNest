"""3. 유전 알고리즘 (구현 예정)

순서·회전의 집단(population)을 진화시키며 BL 디코더로 평가한다.

구현 메모
- 염색체: 부품 사본 순서(순열) + 사본별 회전 → 디코더 입력 seq = [(item_id, rotation), ...]
- 적합도: dec.length(seq)  (사용 길이, 작을수록 좋음)
- 초기 집단: 정렬 그리디 순서 1개 + 무작위 변형들
- 연산자: 토너먼트 선택, 순서 교차(OX), 변이(두 위치 교환, 회전 변경), 엘리트 보존
- 같은 item의 사본끼리는 서로 바꿔도 같은 해이므로, 순열을 item id 목록으로 다뤄도 된다
- 종료: time_limit_s 또는 평가 횟수 상한(params["max_evals"])
- 난수는 random.Random(seed) 하나만 사용 (재현 가능)
- 결과: dec.to_solution(best_seq, "ga", t0, {"seed": seed, "params": params, "history": [...]})
  history에 (평가 횟수, 최고 길이)를 기록하면 수렴 곡선을 그릴 수 있다.
- 디코더 1회가 인스턴스에 따라 0.01~3초 걸리므로 개체 수·세대 수를 작게 시작할 것
"""

from nesting.model import Instance, Solution


def nest(inst: Instance, *, seed: int = 0, time_limit_s: float | None = None, **params) -> Solution:
    raise NotImplementedError("유전 알고리즘 미구현")
