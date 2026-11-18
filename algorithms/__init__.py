"""알고리즘 등록소. 모든 알고리즘은 같은 형태의 함수를 제공한다.

    nest(inst: Instance, *, seed: int = 0, time_limit_s: float | None = None, **params) -> Solution

새 알고리즘을 추가하면 REGISTRY에 한 줄 등록한다.
"""

from importlib import import_module

REGISTRY = {
    "baseline": "algorithms.baseline",  # 검증·화면 개발용 단순 배치 (비교 대상 아님)
    "bl": "algorithms.bl",  # Bottom-Left 그리디
    "nfp": "algorithms.nfp",  # No-Fit Polygon 기반 배치
    "ga": "algorithms.ga",  # 유전 알고리즘
}


def get(name: str):
    if name not in REGISTRY:
        raise KeyError(f"알 수 없는 알고리즘 {name}. 가능: {', '.join(REGISTRY)}")
    return import_module(REGISTRY[name]).nest
