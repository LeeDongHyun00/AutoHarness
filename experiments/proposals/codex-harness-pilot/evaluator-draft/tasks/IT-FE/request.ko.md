이슈 목록 화면(`static/index.html`, `static/list.js`)에서 상태 필터와 정렬을 바꾸면 주소창 URL은 바뀌지만, 새로고침하거나 브라우저 뒤로/앞으로 가기를 하거나 그 URL로 바로 들어오면 필터와 정렬이 기본값으로 돌아갑니다. URL에 담긴 필터·정렬이 화면에 그대로 복원되도록 고쳐 주세요.

요구사항:
1. 목록 화면을 열 때 URL의 `status`, `sort` 값을 읽어 상태 필터(`#status-filter`), 정렬(`#sort-order`), 이슈 목록에 적용합니다. 예를 들어 상태를 Open, 정렬을 Oldest first로 고른 뒤 새로고침해도 URL·두 컨트롤·목록이 그대로 유지되어야 합니다.
2. 필터나 정렬을 바꿀 때마다 브라우저 기록이 하나씩 쌓이는 지금 동작은 유지합니다. 뒤로/앞으로 가기를 하면 그 기록 시점의 필터·정렬·목록이 다시 보여야 합니다.
3. URL의 `status`가 `open`, `in_progress`, `done`이 아니면 상태 필터는 전체(빈 값)로, `sort`가 `created-desc`, `created-asc`, `title-asc`가 아니면 정렬은 `created-desc`로 처리합니다. 두 값은 서로 독립적으로 판단하고, 이 경우 오류 메시지를 띄우지 않습니다.
4. `project` 파라미터, 이슈 상세 페이지로 가는 링크, 결과가 없을 때의 "No issues match these filters." 안내 등 기존 동작은 그대로 둡니다. 기존 마크업의 `id`와 `.issue[data-issue-id]` 구조도 유지해 주세요.

확인 방법: `python tools/check_public.py`로 공개 검사를 실행할 수 있습니다(Playwright 필요). 기존 테스트 `python -m unittest discover -s tests -v`도 계속 통과해야 합니다.
