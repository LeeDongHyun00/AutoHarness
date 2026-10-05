from lib import App, CheckList, InfraFailure, concurrent_requests, expect

checks = CheckList("event-signup", "EV-BE")
SQL_DELAY_MS = 100


def add_event(app, slug, capacity):
    app.sql("INSERT INTO events (slug, title, starts_at, capacity) VALUES (?, ?, '2026-12-01T10:00:00Z', ?)",
            (slug, slug.title(), capacity))


def fire(app, slug, people):
    calls = [("POST", f"/api/events/{slug}/registrations", {"name": n, "email": e}) for n, e in people]
    results, overlapped = concurrent_requests(app, calls)
    if not overlapped:
        raise InfraFailure("requests did not overlap; concurrency cannot be judged")
    return results


def counts(app, slug):
    rows = app.sql("SELECT r.status, COUNT(*) AS n FROM registrations r JOIN events e ON e.id = r.event_id"
                   " WHERE e.slug = ? GROUP BY r.status", (slug,))
    return {row["status"]: row["n"] for row in rows}


@checks.add("EV-BE-H1", "capacity 1, three simultaneous signups")
def capacity_one(project, root):
    with App(project, root, sql_delay_ms=SQL_DELAY_MS) as app:
        add_event(app, "solo-talk", 1)
        results = fire(app, "solo-talk", [(f"S{i}", f"s{i}@example.com") for i in range(3)])
        statuses = sorted(body.get("registration", {}).get("status") for _, body in results)
        expect(statuses == ["confirmed", "waitlisted", "waitlisted"], f"statuses: {statuses} {results}")
        expect(counts(app, "solo-talk") == {"confirmed": 1, "waitlisted": 2}, f"stored: {counts(app, 'solo-talk')}")
        waitlisted = [b["registration"] for _, b in results if b["registration"]["status"] == "waitlisted"]
        expect(sorted(r["waitlist_position"] for r in waitlisted) == [1, 2], f"positions: {waitlisted}")


@checks.add("EV-BE-H1", "full event: simultaneous signups all join the waitlist")
def already_full(project, root):
    with App(project, root, sql_delay_ms=SQL_DELAY_MS) as app:
        results = fire(app, "rust-workshop", [("W1", "w1@example.com"), ("W2", "w2@example.com")])
        expect(all(s == 201 for s, _ in results), f"responses: {results}")
        regs = [b["registration"] for _, b in results]
        expect([r["status"] for r in regs] == ["waitlisted", "waitlisted"], f"statuses: {regs}")
        expect(sorted(r["waitlist_position"] for r in regs) == [3, 4], f"positions: {regs}")
        expect(counts(app, "rust-workshop") == {"confirmed": 1, "waitlisted": 4}, f"stored: {counts(app, 'rust-workshop')}")


@checks.add("EV-BE-H1", "same email twice at once: one active registration; other events untouched")
def duplicate_email(project, root):
    with App(project, root, sql_delay_ms=SQL_DELAY_MS) as app:
        before = counts(app, "spring-meetup")
        results = fire(app, "design-clinic", [("Dup", "dup@example.com"), ("Dup", "DUP@example.com")])
        codes = sorted(status for status, _ in results)
        expect(codes == [201, 409], f"status codes: {results}")
        conflict = [b for s, b in results if s == 409][0]
        expect(conflict.get("code") == "already_registered", f"conflict body: {conflict}")
        rows = app.sql("SELECT status FROM registrations WHERE email = 'dup@example.com'")
        expect([r["status"] for r in rows] == ["confirmed"], f"stored rows: {[dict(r) for r in rows]}")
        expect(counts(app, "spring-meetup") == before, "another event changed")
