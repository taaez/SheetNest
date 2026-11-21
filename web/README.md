# 웹 데모

도면을 고르거나 올리면 세 가지 가능 위치 계산 방법(삼각법, NFP, 래스터)으로 배치하고,
사용 길이, 활용률, 시간, 배치 그림을 나란히 비교한다. 결과는 커터용 SVG와 DXF로 받을 수 있다.

## 구조

서버가 없다. 브라우저 안에서 Python(Pyodide)을 띄워 **저장소의 Python 코드를 그대로** 실행한다.
그래서 알고리즘을 JavaScript로 다시 짜지 않는다. NFP와 래스터가 main에 합쳐지면 웹에도 자동으로 나온다.

```
index.html, style.css   화면
app.js                  화면 동작 (도면 선택, 실행 버튼, 비교표, 재생)
export.js               배치 그림 SVG, 커터용 SVG, DXF 만들기
worker.js               Web Worker. Pyodide를 띄우고 bridge.py를 부른다 (계산 중에도 화면이 멈추지 않음)
bridge.py               웹과 팀 코드를 잇는 Python 모듈. algorithms.get(이름)으로 실행하고 결과를 JSON으로 돌려준다
```

`tools/build_web.py`가 위 파일과 `nesting/`, `algorithms/`, 인스턴스 파일을 `site/` 폴더 하나로 묶는다.

## 내 PC에서 열기

```bash
python tools/build_web.py --serve
```

브라우저에서 http://localhost:8000 을 연다. 처음 열 때 Python 실행 환경(약 10MB)을 내려받으므로 인터넷이 필요하다.
코드를 고친 뒤에는 Ctrl+C로 끄고 같은 명령을 다시 실행한다. `index.html`을 더블클릭해서 열면 동작하지 않는다.

## 배포

main에 합쳐지면 `.github/workflows/pages.yml`이 자동으로 GitHub Pages에 올린다.
주소: https://taaez.github.io/SheetNest/
처음 한 번은 저장소 주인이 Settings > Pages > Source를 "GitHub Actions"로 바꿔야 한다.

## 방법이 추가되거나 매개변수가 바뀔 때

- 방법 목록은 `algorithms.COMPARED`에서 읽는다. 구현 전인 방법은 화면에 "구현 중"으로 나온다.
- 화면에서 바꿀 매개변수는 `bridge.py`의 `PARAMS`에 적는다. 지금은 래스터의 `rows`(폭 방향 칸 수)만 있다.
- 비교표의 계산량 이름은 `app.js`의 `COUNTER_LABELS`에 한글 이름을 적는다.

## 검사

`tests/test_web_bridge.py`가 bridge.py와 사이트 빌드를 검사한다(CI에 포함).
브라우저에서 재는 시간은 PC에서 직접 돌린 것보다 1.7~2.7배 느리다(삼각법 7개 인스턴스 기준).
보고서의 시간은 `tools/report.py` 값을 쓰고, 웹의 시간은 시연용으로만 본다.
