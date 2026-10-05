from lib import App, CheckList, expect

checks = CheckList("event-signup", "EV-INT")
NOW = "2026-10-09T15:30:00Z"


def insert_reg(app, reg_id, event_id, name, status, waitlisted_at=None):
    app.sql(
        "INSERT INTO registrations (id, event_id, name, email, status, token, created_at, waitlisted_at, confirmed_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (reg_id, event_id, name, f"{name.lower()}@example.com", status, f"tok-{reg_id}",
         "2026-10-04T00:00:00Z", waitlisted_at, "2026-10-04T00:00:00Z" if status == "confirmed" else None),
    )


def reg(app, reg_id, tok=None):
    status, body = app.request("GET", f"/api/registrations/{reg_id}",
                               headers={"X-Registration-Token": tok or f"tok-{reg_id}"})
    expect(status == 200, f"GET {reg_id}: {status} {body}")
    return body["registration"]


def cancel(app, reg_id, tok=None):
    status, body = app.request("POST", f"/api/registrations/{reg_id}/cancel",
                               headers={"X-Registration-Token": tok or f"tok-{reg_id}"})
    expect(status == 200, f"cancel {reg_id}: {status} {body}")
    return body["registration"]


@checks.add("EV-INT-H1", "order is waitlisted_at first, then registration id")
def ordering(project, root):
    with App(project, root, now=NOW) as app:
        # design-clinic (id 3, capacity 2): two confirmed, three waitlisted.
        insert_reg(app, 40, 3, "Conf1", "confirmed")
        insert_reg(app, 41, 3, "Conf2", "confirmed")
        insert_reg(app, 52, 3, "Late", "waitlisted", "2026-10-05T12:00:00Z")
        insert_reg(app, 51, 3, "TieHigh", "waitlisted", "2026-10-05T09:00:00Z")
        insert_reg(app, 50, 3, "TieLow", "waitlisted", "2026-10-05T09:00:00Z")
        insert_reg(app, 60, 3, "EarliestBigId", "waitlisted", "2026-10-05T08:00:00Z")
        cancel(app, 40)
        promoted = reg(app, 60)
        expect(promoted["status"] == "confirmed" and promoted["confirmed_at"] == NOW,
               f"earliest waitlisted_at (despite larger id) should be promoted: {promoted}")
        cancel(app, 41)
        expect(reg(app, 50)["status"] == "confirmed", "tie on waitlisted_at must promote the lower id")
        expect(reg(app, 51)["waitlist_position"] == 1 and reg(app, 52)["waitlist_position"] == 2, "remaining order wrong")


@checks.add("EV-INT-H1", "promotions chain; cancelling a promoted seat promotes the next person")
def chain(project, root):
    with App(project, root, now=NOW) as app:
        cancel(app, 3, "seed-token-3")
        cancel(app, 4, "seed-token-4")
        chan = reg(app, 5, "seed-token-5")
        expect(chan["status"] == "confirmed", f"second promotion missing: {chan}")
        cancel(app, 5, "seed-token-5")
        status, body = app.request("GET", "/api/events/rust-workshop")
        ev = body["event"]
        expect((ev["confirmed_count"], ev["seats_left"], ev["waitlist_count"]) == (0, 1, 0), f"final counts: {ev}")


@checks.add("EV-INT-H1", "other events, wrong tokens and re-registration are unaffected")
def isolation(project, root):
    with App(project, root, now=NOW) as app:
        before = app.sql("SELECT id, status FROM registrations WHERE event_id != 2 ORDER BY id")
        status, _ = app.request("POST", "/api/registrations/3/cancel", headers={"X-Registration-Token": "wrong"})
        expect(status == 404, f"wrong token cancel: {status}")
        expect(reg(app, 4, "seed-token-4")["status"] == "waitlisted", "wrong-token cancel promoted someone")
        cancel(app, 3, "seed-token-3")
        after = app.sql("SELECT id, status FROM registrations WHERE event_id != 2 ORDER BY id")
        expect([dict(r) for r in before] == [dict(r) for r in after], "registrations of other events changed")
        status, body = app.request("POST", "/api/events/rust-workshop/registrations",
                                   {"name": "Ara Yoon", "email": "ara@example.com"})
        expect(status == 201 and body["registration"]["status"] == "waitlisted",
               f"re-registration after cancel should join the waitlist: {status} {body}")
