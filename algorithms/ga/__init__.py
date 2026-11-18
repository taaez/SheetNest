"""유전 알고리즘 (구현 예정).

구현 메모
- 염색체: 부품 사본의 배치 순서(순열) + 사본별 회전각.
- 디코더: Bottom-Left(또는 NFP) 배치로 염색체를 실제 배치로 바꾸고, 사용 길이를 적합도로 쓴다.
- 연산자: 토너먼트 선택, 순서 교차(OX), 변이(두 위치 교환, 회전 변경), 엘리트 보존.
- 난수는 random.Random(seed) 하나만 사용해 재현 가능하게 한다.
- 종료: 세대 수 또는 time_limit_s. stats에 세대별 최고 길이(수렴 곡선)를 기록하면 보고서에 쓸 수 있다.
"""

from nesting.model import Instance, Solution


def nest(inst: Instance, *, seed: int = 0, time_limit_s: float | None = None, **params) -> Solution:
    raise NotImplementedError("유전 알고리즘 미구현")
