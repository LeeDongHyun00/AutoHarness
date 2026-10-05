행사 신청 API(`POST /api/events/{slug}/registrations`)는 확정 인원이 정원보다 적으면 `confirmed`, 아니면 `waitlisted`로 등록합니다. 그런데 여러 사람이 동시에 신청하면 정원을 넘겨 확정되는 경우가 있습니다. 동시에 신청이 들어와도 정원이 지켜지도록 고쳐 주세요.

요구사항:
1. 동시에 몇 건의 신청이 들어오든, 한 행사의 `confirmed` 등록 수는 정원(`capacity`)을 넘으면 안 됩니다. 남은 자리만큼만 `confirmed`가 되고 나머지는 `waitlisted`가 됩니다. 누가 자리를 얻는지는 정하지 않습니다.
2. 각 신청 응답의 `status`는 저장된 상태와 같아야 하고, 행사 조회의 `seats_left`는 음수가 되면 안 됩니다.
3. 같은 이메일의 중복 신청은 지금처럼 하나만 활성 상태로 남고 나머지는 409 `already_registered`입니다.
4. 순차 신청, 대기 순서, 오류 형식, 응답 형식 등 기존 동작은 그대로 둡니다. 서버는 지금처럼 여러 요청을 동시에 처리할 수 있어야 합니다.

확인 방법: `python tools/check_public.py`로 공개 검사를 실행할 수 있습니다(동시 요청 검사 포함). 기존 테스트 `python -m unittest discover -s tests -v`도 계속 통과해야 합니다.
