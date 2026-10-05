확정(`confirmed`)된 신청을 취소하면 자리는 비지만, 대기자가 있어도 자동으로 확정되지 않습니다. 확정 신청이 취소되면 대기 1순위가 자동으로 확정되도록 해 주세요. API와 등록 상태 화면 모두에 반영되어야 합니다.

요구사항:
1. 확정 신청을 취소하면(`POST /api/registrations/{id}/cancel`) 그 행사의 대기자 중 1순위가 `confirmed`가 됩니다. 순서는 README와 같이 `waitlisted_at`이 빠른 순, 같으면 등록 id가 작은 순입니다.
2. 승격된 신청의 `confirmed_at`은 취소 시각(`app.clock.now()`)이고 `waitlist_position`은 `null`입니다. 남은 대기자의 순번은 하나씩 앞당겨집니다.
3. 취소와 승격은 함께 저장되어야 합니다. 취소만 반영되고 승격이 빠진 상태가 남으면 안 됩니다. 서버를 다시 시작해도 결과가 유지되어야 합니다.
4. 이미 취소된 신청을 다시 취소하거나, 대기 중인 신청을 취소할 때는 아무도 승격되지 않습니다. 대기자가 없으면 자리만 비고 새 등록은 생기지 않습니다. 다른 행사의 신청은 바뀌지 않습니다.
5. 등록 상태 화면(`registration.html`)에서 취소하면 `#registration-state`가 `Cancelled`로 바뀌고, 승격된 사람의 등록 화면에는 `Confirmed`가 보여야 합니다. 기존 응답 형식과 마크업은 유지합니다.

확인 방법: `python tools/check_public.py`로 공개 검사를 실행할 수 있습니다(Playwright 필요). 기존 테스트 `python -m unittest discover -s tests -v`도 계속 통과해야 합니다.
