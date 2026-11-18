"""1. 정렬 그리디 (구현 예정)

부품 사본의 배치 순서를 정렬 기준 하나로 정하고, BL 디코더로 한 번만 배치한다. 결정적 알고리즘.

구현 메모
- 순서·회전만 정하고, 배치는 반드시 공통 디코더를 쓴다.
      from nesting.decoder import Decoder
      dec = Decoder(inst)
      seq = [(item_id, rotation), ...]          # 부품 사본마다 1개 (총 inst.total_quantity개)
      return dec.to_solution(seq, "greedy", t0, {"seed": seed, "params": params})
- 정렬 기준 후보 (실험으로 비교해 하나를 정하거나, 매개변수로 고를 수 있게):
  면적 큰 순, 바운딩 박스 높이 큰 순, 너비 큰 순, 둘레 큰 순, 오목 정도(볼록 껍질 면적 대비 면적) 순
- 회전: 원판 폭에 들어가는 회전 중 하나 (dec.feasible_rotations(item)). 기본은 첫 번째,
  또는 '바운딩 박스 높이가 큰 회전'처럼 규칙을 정한다.
- 시작 시 nesting.collision.reset_stats()와 t0 = time.perf_counter().
- 참고: dec.default_sequence()가 '면적 큰 순 + 첫 회전' 순서를 만들어 준다 (출발점으로 활용).
"""

from nesting.model import Instance, Solution


def nest(inst: Instance, *, seed: int = 0, time_limit_s: float | None = None, **params) -> Solution:
    raise NotImplementedError("정렬 그리디 미구현")
