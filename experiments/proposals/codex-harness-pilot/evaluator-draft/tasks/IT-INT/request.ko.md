이슈에 담당자(assignee)를 지정하는 기능을 추가해 주세요. API, 데이터 저장, 이슈 상세·목록 화면까지 모두 필요합니다.

API 요구사항:
1. 이슈를 돌려주는 모든 응답(목록, 상세, 생성, 상태 변경)에 `assignee` 필드를 추가합니다. 담당자가 없으면 `null`, 있으면 `{"id": <사용자 id>, "name": <이름>}`입니다. 새로 만든 이슈는 `null`입니다.
2. `PATCH /api/projects/{key}/issues/{id}/assignee`에 `{"assignee_id": <정수 사용자 id 또는 null>}`을 보내면 담당자를 지정하거나(`null`이면) 해제하고, 200과 `{"issue": ...}`를 돌려줍니다. 서버를 다시 시작해도 유지되어야 합니다.
3. 담당자로 지정할 수 있는 사람은 그 프로젝트의 **활성** 멤버(역할 무관)뿐입니다. 존재하지 않는 사용자, 비활성 사용자, 다른 프로젝트 사용자, 정수가 아닌 값, `assignee_id` 누락은 400(`bad_request`)으로 거절하고 이슈를 바꾸지 않습니다. 없는 이슈는 404입니다.
4. 권한은 상태 변경과 같습니다. admin·member만 지정할 수 있고 viewer·비회원은 403, 사용자 헤더 없음·비활성 사용자는 401입니다.

화면 요구사항:
5. 이슈 상세 화면(`issue.html`)에 현재 담당자를 `#issue-assignee`에 표시합니다(없으면 `Unassigned`). `#assignee-form` 안에 `<select id="assignee-select">`와 제출 버튼을 둡니다. 선택지는 `Unassigned`(value `""`)와 프로젝트의 활성 멤버(value = 사용자 id, 표시 = 이름)입니다. 저장하면 `#issue-assignee`가 즉시 바뀌어야 합니다.
6. 이슈 목록의 각 항목(`.issue`) 안에 `.issue-assignee` 요소로 담당자 이름 또는 `Unassigned`를 표시합니다.

기존 기능과 응답 형식, 기존 마크업은 유지해 주세요.

확인 방법: `python tools/check_public.py`로 공개 검사를 실행할 수 있습니다(Playwright 필요). 기존 테스트 `python -m unittest discover -s tests -v`도 계속 통과해야 합니다.
