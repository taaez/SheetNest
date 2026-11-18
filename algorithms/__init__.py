"""알고리즘 등록소.

비교 구조 (docs/SPEC.md 5절)
    순서 탐색  ← 비교 대상: greedy / local_search / ga
    BL 디코더  ← 고정 (nesting/decoder.py)
    겹침 판정  ← 고정 (nesting/collision.py)

모든 알고리즘은 같은 형태의 함수를 제공한다.
    nest(inst: Instance, *, seed: int = 0, time_limit_s: float | None = None, **params) -> Solution
"""

from importlib import import_module

REGISTRY = {
    "baseline": "algorithms.baseline",  # 바운딩 박스 줄 쌓기: 검증·화면 개발용 (비교 대상 아님)
    "greedy": "algorithms.greedy",  # 1. 정렬 그리디: 정렬 기준으로 순서를 한 번 정해 배치
    "local_search": "algorithms.local_search",  # 2. 지역 탐색 또는 시뮬레이티드 어닐링 (회의에서 확정)
    "ga": "algorithms.ga",  # 3. 유전 알고리즘
}

COMPARED = ["greedy", "local_search", "ga"]


def get(name: str):
    if name not in REGISTRY:
        raise KeyError(f"알 수 없는 알고리즘 {name}. 가능: {', '.join(REGISTRY)}")
    return import_module(REGISTRY[name]).nest
