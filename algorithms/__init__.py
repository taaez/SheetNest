"""알고리즘 등록소.

비교 구조 (docs/SPEC.md 5절)
    배치 순서와 회전   고정  nesting/sequence.py (면적 큰 순, 들어가는 첫 회전)
    위치 선택 규칙     고정  Bottom-Left (x 최소, 같으면 y 최소)
    가능 위치 계산     비교  trig(삼각법, 직접 판정) / nfp(No-Fit Polygon) / raster(격자)

모든 알고리즘은 같은 형태의 함수를 제공한다.
    nest(inst: Instance, *, seed: int = 0, time_limit_s: float | None = None, **params) -> Solution
비교 대상 세 방법은 공통 실행 틀(nesting/runner.py)의 Placer를 상속해 place()만 구현하고,
tests/test_contract.py의 계약 테스트를 통과해야 한다.
"""

from importlib import import_module

REGISTRY = {
    "baseline": "algorithms.baseline",  # 바운딩 박스 줄 쌓기, 검증과 화면 개발용 (비교 대상 아님)
    "trig": "algorithms.trig",  # 1. 삼각법(직접 판정)
    "nfp": "algorithms.nfp",  # 2. No-Fit Polygon
    "raster": "algorithms.raster",  # 3. 래스터(격자)
}

COMPARED = ["trig", "nfp", "raster"]


def get(name: str):
    if name not in REGISTRY:
        raise KeyError(f"알 수 없는 알고리즘 {name}. 가능: {', '.join(REGISTRY)}")
    return import_module(REGISTRY[name]).nest


def get_placer(name: str):
    """비교 대상 방법의 Placer 클래스 (계약 테스트, 리포트용)."""
    from nesting.runner import Placer

    mod = import_module(REGISTRY[name])
    for v in vars(mod).values():
        if isinstance(v, type) and issubclass(v, Placer) and v is not Placer and v.name == name:
            return v
    raise KeyError(f"{name}: Placer 클래스를 찾지 못함")
