# 과제 6개와 채점 계약 (W2)

**작성일:** 2026-10-05 · **상태:** 초안 완성 / 6개 과제 baseline-red·reference-green 자동 검증 통과 / 독립 검토 전 / 동결 전

## 구성

```
evaluator-draft/
  baseline-failures.json        과제별 의도된 결함 기록 (평가자 측 자료)
  probes/                       W1 사전 확인 스크립트 (채점기 아님)
  grader/
    lib.py                      앱 실행·HTTP·DB·브라우저 공통 도구 (작업 공간에도 그대로 복사됨)
    grade.py                    채점 진입점
    install_public_checks.py    작업 공간에 공개 검사 설치
    verify_red_green.py         baseline-red / reference-green 일괄 검증
  tasks/<ID>/
    request.ko.md               Codex에 그대로 전달할 요청문
    requirements.yaml           요구사항 계약 (노션 16.2 필드)
    public_checks.py            공개 검사
  hidden/tasks/<ID>/
    private_checks.py           비공개 검사 (Codex 작업 공간에 넣지 않음)
    reference.patch             reference 구현
  red-green-2026-10-05.json     검증 결과
```

비공개 검사와 reference patch는 `hidden/`에 있습니다. 2026-10-05 사용자 결정(D4)으로 공개 저장소에 그대로 둡니다. 따라서 "비공개"는 **Codex 작업 공간과 하네스 생성기 입력에 넣지 않는다**는 뜻이지 접근 통제가 아닙니다. 모델이 인터넷에서 이 저장소를 찾아볼 수 있는 실행 환경이라면 숨겨진 검사가 새어 나갈 수 있으므로, W5에서 Codex 작업 공간의 네트워크 접근을 막거나 실행 로그로 이 저장소 접근 여부를 확인해야 합니다.

## 실행 흐름

1. `export_baseline.py`로 baseline을 새 작업 공간에 내보냅니다.
2. 조건에 맞는 하네스를 적용합니다(A는 없음).
3. `install_public_checks.py --task <ID> --workspace <dir>`로 공개 검사를 설치합니다. 모든 조건에 똑같이 적용합니다.
4. Codex가 `request.ko.md`를 받아 구현합니다. 작업 공간에서 `python tools/check_public.py`를 실행할 수 있습니다.
5. 종료 후 작업 공간 밖에서 채점합니다.

```sh
python grader/grade.py --task IT-BE --submission <workspace> --out result.json
```

## 채점 규칙

- **성공 정의:** 기존 테스트(`REG-tests`), 공개 검사, 비공개 검사가 모두 `pass`일 때만 과제 성공입니다. 비공개 검사가 없으면 `not_available`로 남고 성공이 아닙니다.
- **검사 조작 방지:** 채점 전에 작업 공간을 복사하고, `tests/`를 baseline 원본으로 덮어씁니다. 모델이 기존 테스트를 고치거나 지워도 회귀를 숨길 수 없습니다.
- **외부 관찰만 사용:** 검사는 HTTP 응답, SQLite 행, 브라우저 화면만 봅니다. 프로젝트 모듈을 import하거나 내부 함수 이름을 강제하지 않으므로, 구현 방식이 달라도 계약을 지키면 통과합니다.
- **격리:** 검사마다 새 앱 프로세스와 새 seed DB를 쓰고, 시계는 `APP_NOW`로 고정합니다.
- **상태 구분:** `pass`, `fail`(assertion·UI timeout), `startup_failure`, `infra_failure`, `timeout`, `error`를 구분해 기록합니다. red 판정에는 `fail`만 인정합니다.
- **동시성(EV-BE):** 요청 스레드를 barrier로 동시에 출발시키고, `sitecustomize`로 앱의 모든 SQLite 연결에 `registrations` 문장마다 100ms 지연을 넣어 읽기와 쓰기 사이의 간격을 넓힙니다. 모든 요청이 실제로 동시에 진행 중이었는지(클라이언트 측 시간 창 겹침)를 확인하고, 겹치지 않았으면 판정 대신 `infra_failure`로 기록합니다. 지연은 모든 구현에 똑같이 적용되는 환경 조건이며 특정 코드 경로에 의존하지 않습니다.

## 원 설계에서 바꾼 점

| 항목 | 원 설계(노션 16.3) | 변경 | 이유 |
|---|---|---|---|
| 공개 검사 위치 | baseline 저장소 안 `tools/check_public.py` | 하네스 적용 뒤 작업 공간에 설치 | baseline에 넣으면 생성기가 과제 목록과 검사 내용을 보게 됨 |
| 공개 검사 명령 | `python3 tools/check_public.py --task TASK_ID` | `python tools/check_public.py` (`--task`는 선택) | 작업 공간마다 과제가 하나뿐 |
| 비공개 검사 위치 | 별도 비공개 저장소 | 이 공개 저장소의 `hidden/` | 사용자 결정(D4). 작업 공간·생성기 입력에서만 분리 |

## 확정한 "새 제안" 규칙

노션 16.3에서 실행 전 고정하기로 한 항목을 요청문과 검사에 다음과 같이 고정했습니다.

- **IT-FE:** 알 수 없는 `status`·`sort`는 서로 독립적으로 기본값(전체 / `created-desc`)으로 처리하고 오류를 표시하지 않음. 필터 변경마다 기록 항목 1개.
- **IT-BE:** `open → in_progress → done`만 허용, 같은 상태는 200 무변경, 금지된 변경은 409 `conflict`, 알 수 없는 값 400, 없는 이슈 404.
- **IT-INT:** `assignee` 필드(`null` 또는 `{id, name}`), `PATCH .../assignee`에 `{"assignee_id"}`, 프로젝트의 활성 멤버만 지정 가능(역할 무관), 잘못된 대상·형식은 400, 권한은 상태 변경과 동일. 화면 요소 `#issue-assignee`, `#assignee-form`, `#assignee-select`, `.issue-assignee`.
- **EV-FE:** 서버 오류·거절·네트워크 오류 모두 입력 유지, 대기 중 중복 클릭은 요청 1회.
- **EV-BE:** 확정 수 ≤ 정원, 누가 자리를 얻는지는 정하지 않음, 응답 상태 = 저장 상태.
- **EV-INT:** 대기 순서는 `waitlisted_at` → id, 승격 `confirmed_at` = 취소 시각, 취소와 승격은 함께 저장.

## 검증 결과 (2026-10-05)

`grader/verify_red_green.py`로 과제마다 다음을 자동 확인했습니다.

- **red:** baseline에서 목표 요구사항(-1, -2) 중 하나 이상이 assertion으로 실패하고, 기존 테스트는 통과하며, 기동·인프라 오류가 없음.
- **green:** baseline에 reference patch만 적용하면 기존 테스트, 공개 검사, 비공개 검사가 모두 통과.

| 과제 | red | green | baseline에서 실패한 목표 요구사항 |
|---|---|---|---|
| IT-FE | OK | OK | IT-FE-1, IT-FE-2 |
| IT-BE | OK | OK | IT-BE-1 |
| IT-INT | OK | OK | IT-INT-1, IT-INT-2 |
| EV-FE | OK | OK | EV-FE-1, EV-FE-2 |
| EV-BE | OK | OK | EV-BE-1, EV-BE-2 |
| EV-INT | OK | OK | EV-INT-1, EV-INT-2 |

같은 결과가 두 번 연속 나왔습니다. 결과 파일에는 검사 파일 해시가 들어 있습니다(비공개 검사 해시 포함, 내용은 없음).

## 확인하지 않은 것과 남은 일

- 작성자 외 검토자의 요청-검사 대응과 reference patch 검토. 같은 작성자가 결함, 검사, 정답을 모두 만들었습니다.
- reference patch 외의 다른 올바른 구현(예: EV-BE를 프로세스 잠금으로 해결)이 통과하는지는 확인하지 않았습니다. 검사는 외부 관찰만 쓰도록 설계했지만 실제 다양성은 파일럿에서 드러납니다.
- Codex 작업 공간에서 UI 공개 검사를 돌리려면 Playwright와 Chromium이 필요합니다(W5 환경 조건). 경로는 `PW_CHROMIUM`으로 지정할 수 있습니다.
- 수집할 패치에서 설치된 `tools/check_public.py`, `tools/pilot_checks/`는 제외해야 합니다(W5). 채점기는 이미 이 둘을 무시합니다.
