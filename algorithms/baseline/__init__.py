"""기준선(baseline): 바운딩 박스 세로 줄 쌓기.

비교 대상 알고리즘이 아니다. 항상 유효한 해를 빠르게 만들어 주므로
검증기 테스트, 웹 화면 개발, 다른 알고리즘의 '최소 이 정도는 넘어야 한다' 기준으로 쓴다.

방식: 부품을 바운딩 박스 높이가 큰 순으로 정렬 → 허용 회전 중 폭(x 길이)이 가장 작은 회전 선택
→ 아래에서 위로 쌓다가 원판 폭을 넘으면 오른쪽 새 줄로 이동. 박스끼리 겹치지 않으므로 항상 유효.
"""

from __future__ import annotations

import time

from nesting import collision as c
from nesting import geometry as g
from nesting.model import Instance, Placement, Solution, make_solution


def nest(inst: Instance, *, seed: int = 0, time_limit_s: float | None = None, **params) -> Solution:
    c.reset_stats()
    t0 = time.perf_counter()
    W = inst.sheet_width
    jobs = []
    for it in inst.items:
        best = None
        for r in it.rotations:
            minx, miny, maxx, maxy = g.bbox(g.rotate(it.polygon, r))
            w, h = maxx - minx, maxy - miny
            if h <= W + 1e-9 and (best is None or w < best[1]):
                best = (r, w, h, minx, miny)
        if best is None:
            raise ValueError(f"item {it.id}: 원판 폭에 들어가는 회전이 없음")
        for k in range(it.quantity):
            jobs.append((it.id, k, *best))
    jobs.sort(key=lambda j: -j[4])  # 높이 큰 순

    placements, col_x, col_w, y = [], 0.0, 0.0, 0.0
    for item, copy, r, w, h, minx, miny in jobs:
        if y + h > W + 1e-9:  # 새 줄
            col_x, col_w, y = col_x + col_w, 0.0, 0.0
        placements.append(Placement(item=item, copy=copy, rotation=r, x=col_x - minx, y=y - miny))
        y += h
        col_w = max(col_w, w)

    ms = (time.perf_counter() - t0) * 1000
    return make_solution(inst, "baseline", placements, ms, {**c.get_stats(), "seed": seed, "params": params})
