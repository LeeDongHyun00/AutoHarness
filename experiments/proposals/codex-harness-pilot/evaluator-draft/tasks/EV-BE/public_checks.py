from lib import App, CheckList, InfraFailure, concurrent_requests, expect

checks = CheckList("event-signup", "EV-BE")
SQL_DELAY_MS = 100


def signups(slug, people):
    return [("POST", f"/api/events/{slug}/registrations", {"name": name, "email": email}) for name, email in people]


def event(app, slug):
    status, body = app.request("GET", f"/api/events/{slug}")
    expect(status == 200, f"GET event returned {status}: {body}")
    return body["event"]


def check_consistency(app, results):
    for status, body in results:
        expect(status == 201, f"signup failed: {status} {body}")
        reg = body["registration"]
        got_status, got = app.request("GET", f"/api/registrations/{reg['id']}",
                                      headers={"X-Registration-Token": reg["token"]})
        expect(got_status == 200, f"lookup failed: {got_status} {got}")
        expect(got["registration"]["status"] == reg["status"],
               f"response said {reg['status']} but stored status is {got['registration']['status']}")


@checks.add("EV-BE-1", "two simultaneous signups for the last seat: one confirmed, one waitlisted")
def last_seat(project, root):
    with App(project, root, sql_delay_ms=SQL_DELAY_MS) as app:
        results, overlapped = concurrent_requests(
            app, signups("spring-meetup", [("P One", "p1@example.com"), ("P Two", "p2@example.com")]))
        if not overlapped:
            raise InfraFailure("requests did not overlap; concurrency cannot be judged")
        check_consistency(app, results)
        statuses = sorted(body["registration"]["status"] for _, body in results)
        expect(statuses == ["confirmed", "waitlisted"], f"statuses: {statuses}")
        ev = event(app, "spring-meetup")
        expect(ev["confirmed_count"] == 3 and ev["seats_left"] == 0, f"event counts: {ev}")


@checks.add("EV-BE-2", "more simultaneous signups than seats never overfill the event")
def more_than_seats(project, root):
    with App(project, root, sql_delay_ms=SQL_DELAY_MS) as app:
        people = [(f"Q {i}", f"q{i}@example.com") for i in range(4)]
        results, overlapped = concurrent_requests(app, signups("design-clinic", people))
        if not overlapped:
            raise InfraFailure("requests did not overlap; concurrency cannot be judged")
        check_consistency(app, results)
        statuses = sorted(body["registration"]["status"] for _, body in results)
        expect(statuses == ["confirmed", "confirmed", "waitlisted", "waitlisted"], f"statuses: {statuses}")
        ev = event(app, "design-clinic")
        expect((ev["confirmed_count"], ev["seats_left"], ev["waitlist_count"]) == (2, 0, 2), f"event counts: {ev}")
        rows = app.sql("SELECT COUNT(*) AS n FROM registrations r JOIN events e ON e.id = r.event_id"
                       " WHERE e.slug = 'design-clinic' AND r.status = 'confirmed'")
        expect(rows[0]["n"] == 2, f"database holds {rows[0]['n']} confirmed rows for capacity 2")
