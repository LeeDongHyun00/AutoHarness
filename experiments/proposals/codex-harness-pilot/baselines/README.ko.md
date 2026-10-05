# 파일럿 합성 프로젝트 baseline (W1)

**작성일:** 2026-10-05 · **상태:** 초안 완성 / 독립 검토 전 / **동결 전**

48회 파일럿용 합성 프로젝트 2개입니다. 기술 스택은 D3에 따라 같습니다(Python 3.11+ 표준 라이브러리 HTTP 서버, SQLite, 바닐라 JS ES 모듈, 외부 패키지 없음). 대신 프로젝트별 규칙과 데이터 흐름은 일부러 다르게 만들었습니다.

| | issue-tracker | event-signup |
|---|---|---|
| 계층 | `server.py` → `service.py` → `repository.py` | `web.py`(`@route`) → `registrations.py` → `store.py`(commit 금지) |
| 인증 | `X-User-Id` 헤더, 역할 admin/member/viewer, 비활성 사용자 | 신청 시 1회 발급하는 `X-Registration-Token` |
| 오류 형식 | `{"error": {"code", "message"}}` | `{"detail", "code"}` |
| 실행 | `python -m app.server --init` (8000) | `python -m app --init` (8100) |
| 기존 지침 | 상세한 `AGENTS.md` | 짧은 `AGENTS.md` |
| 기존 테스트 | 28개 통과 | 22개 통과 |

각 baseline에는 해당 프로젝트 과제 3개의 결함과 미완성 기능이 함께 들어 있습니다. 내용은 `../evaluator-draft/baseline-failures.json`에 따로 기록했습니다. baseline 안에는 결함을 암시하는 주석, TODO, 과제 ID가 없습니다(키워드 검사 결과 무해한 테스트 문자열 1건만 걸림). 기존 공개 테스트는 의도된 결함을 검사하지 않으며, 올바른 수정 후에도 깨지지 않도록 작성했습니다.

## 내보내기

하네스 생성과 Codex 실행은 이 폴더가 아니라 **내보낸 단일 커밋 저장소**에서 시작합니다. 그래야 이 저장소의 계획 문서와 평가 초안이 모델 작업 공간으로 새지 않습니다.

```sh
python experiments/proposals/codex-harness-pilot/export_baseline.py issue-tracker /path/to/new-dir
```

커밋 작성자와 날짜를 고정하므로 같은 파일 트리에서는 항상 같은 커밋 ID가 나옵니다(2회 내보내기로 확인).

| 프로젝트 | 내보낸 커밋 | 파일 수 |
|---|---|---|
| issue-tracker | `f7d9a0dc2b89c93e30e20ff8758928d57bf7fc3b` | 22 |
| event-signup | `774bc9ae64ef16ad15718892c8a2eb2b32fc66ca` | 25 |

이 커밋 ID는 동결 전 값입니다. 검토 중 파일이 바뀌면 ID도 바뀌며, 동결할 때 최종 ID를 다시 기록합니다.

## 확인한 것

- 두 프로젝트 기존 테스트 전부 통과(내보낸 저장소에서도 동일).
- `../evaluator-draft/probes/`의 사전 확인 스크립트로 결함 6개가 의도대로 재현됨을 관찰했습니다. 백엔드는 직접 호출로, 화면은 Playwright + Chromium으로 확인했습니다. 동시성은 `count_confirmed` 직후 barrier로 두 요청을 교차시켜 재현했습니다.
- 정상 흐름도 확인했습니다. 목록, 상세 이동, 상태 변경, 신청 성공, 신청 취소 화면이 콘솔 오류 없이 동작했습니다(favicon 404와 의도한 409 제외).

## 확인하지 않은 것

- 사전 확인 스크립트는 채점기가 아닙니다. 과제별 요청, 요구사항 YAML, 공개·비공개 검사, reference patch, baseline-red/reference-green 판정은 W2 범위입니다.
- 작성자 외 독립 검토와 동결은 하지 않았습니다.
- 실제 HTTP 요청 두 개를 barrier로 동시에 보낼 때 결함이 안정적으로 재현되는지는 W2 채점기에서 확인해야 합니다.

## 계보 기록

- 작성: Claude Code 세션(2026-10-05). 기존 템플릿을 쓰지 않고 새로 작성했습니다.
- 두 프로젝트는 같은 작성자, 같은 날, 같은 스택이므로 **같은 family**로 취급합니다. 최종 평가 holdout에 같은 계보의 프로젝트를 넣지 않습니다.
- 같은 작성자가 과제와 결함을 설계했으므로 하네스에 유리한 편향이 생길 수 있습니다. 결과는 이 합성 환경의 효과로 한정합니다.
