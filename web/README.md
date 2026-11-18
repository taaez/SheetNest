# 웹 (미정)

프레임워크·구조는 팀 회의에서 결정한다. 후보:

- A안: FastAPI 백엔드(Python 알고리즘 그대로 호출) + 프론트엔드
- B안: 브라우저만으로 동작 (GitHub Pages 배포, 알고리즘을 JS로 다시 구현해야 함)

화면 개발은 알고리즘 완성을 기다리지 않고 시작할 수 있다.
`python tools/run.py baseline experiments/selected.txt -o results/`로 만든 solution JSON과
`data/instances/` 의 instance JSON으로 배치 결과를 그려 보면 된다. 그리는 방법은 `tools/preview.py` 참고.
