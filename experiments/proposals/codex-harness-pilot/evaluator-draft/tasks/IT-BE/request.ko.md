README에 적힌 이슈 상태 흐름은 `open → in_progress → done`이고, 단계를 건너뛰거나 되돌아갈 수 없습니다. 그런데 지금 API(`PATCH /api/projects/{key}/issues/{id}/status`)는 `open`에서 바로 `done`으로 바꾸는 요청을 허용합니다. 상태 변경이 README의 규칙을 정확히 따르도록 고쳐 주세요.

요구사항:
1. 허용되는 변경은 `open → in_progress`, `in_progress → done` 두 가지뿐입니다. 성공하면 200과 변경된 이슈를 돌려주고, 이후 조회에도 반영되어야 합니다.
2. 그 밖의 변경(`open → done`, `in_progress → open`, `done → open`, `done → in_progress`)은 409와 `{"error": {"code": "conflict", ...}}`로 거절하고 이슈를 바꾸지 않습니다.
3. 현재와 같은 상태로 바꾸는 요청은 지금처럼 200으로 성공하되 아무것도 바꾸지 않습니다.
4. 알 수 없는 상태값은 400, 없는 이슈는 404를 돌려주고 이슈를 바꾸지 않습니다. 권한 규칙(viewer·비회원 403, 사용자 헤더 없음·비활성 사용자 401)과 응답 형식은 그대로 유지합니다.

확인 방법: `python tools/check_public.py`로 공개 검사를 실행할 수 있습니다. 기존 테스트 `python -m unittest discover -s tests -v`도 계속 통과해야 합니다.
