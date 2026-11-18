# 작업 규칙

## 1. 처음 설정 (한 번만)

Python **3.11**을 설치한 뒤:

```bash
git clone https://github.com/taaez/SheetNest.git
cd SheetNest
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt
python examples/make_examples.py
pytest
```

`pytest`가 모두 통과하면 준비 완료.

## 2. 브랜치

- **각자 자기 브랜치에서 작업하고 push한다.** 브랜치 이름: `이름/작업` (예: `taejeong/validator`, `yujin/bl`)
- **main에는 최종 결과물만 올린다.** 자기 브랜치에서 테스트가 통과한 것을 main에 합친다.
- 작업 시작 전 main 최신 내용을 받아 온다.

```bash
git switch main && git pull
git switch -c 이름/작업            # 새 브랜치
# ... 작업 ...
git add -A && git commit -m "BL: 후보 위치 생성 추가"
git push -u origin 이름/작업
```

- main에 합칠 때는 GitHub에서 PR을 만들어 합치는 것을 권장한다(CI 결과를 확인할 수 있음).
- 모든 브랜치 push마다 CI(GitHub Actions)가 자동으로 검사·테스트를 돌린다. 빨간 X가 뜨면 고친다.

## 3. 커밋 메시지

`영역: 무엇을 했는지` 형식, 한국어로 짧게.

```
BL: 회전별 후보 위치 생성
NFP: 볼록 다각형 민코프스키 합 구현
core: 겹침 판정 바운딩 박스 필터 개선
web: 결과 비교 화면 초안
docs: SPEC에 kerf 규칙 추가
```

## 4. 코드 스타일

커밋 전에 실행:

```bash
ruff format .     # 자동 정렬
ruff check . --fix
```

## 5. 공통 모듈 규칙

- 겹침 판정은 `nesting/collision.py`의 `overlap()`만 사용한다. 각자 따로 만들지 않는다.
- 결과는 `nesting.model.make_solution()`으로 만든다.
- `nesting/`, `docs/SPEC.md`를 바꾸면 팀 대화방에 공지한다 (모두의 코드에 영향).
- 알고리즘 결과는 `tools/run.py`로 실행해 검증기 OK를 확인한다.
