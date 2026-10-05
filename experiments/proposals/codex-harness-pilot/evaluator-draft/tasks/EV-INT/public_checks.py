from lib import FIXED_NOW, App, CheckList, expect, run_in_browser

checks = CheckList("event-signup", "EV-INT")


def token(reg_id):
    return {"X-Registration-Token": f"seed-token-{reg_id}"}


def reg(app, reg_id):
    status, body = app.request("GET", f"/api/registrations/{reg_id}", headers=token(reg_id))
    expect(status == 200, f"GET registration {reg_id} returned {status}: {body}")
    return body["registration"]


def cancel(app, reg_id):
    status, body = app.request("POST", f"/api/registrations/{reg_id}/cancel", headers=token(reg_id))
    expect(status == 200, f"cancel {reg_id} returned {status}: {body}")
    return body["registration"]


def event(app, slug):
    return app.request("GET", f"/api/events/{slug}")[1]["event"]


@checks.add("EV-INT-1", "cancelling a confirmed seat promotes the first waitlisted person")
def promotion(project, root):
    with App(project, root) as app:
        expect(cancel(app, 3)["status"] == "cancelled", "cancelled registration status")
        bora, chan = reg(app, 4), reg(app, 5)
        expect(bora["status"] == "confirmed", f"first waitlisted is {bora['status']}")
        expect(bora["confirmed_at"] == FIXED_NOW, f"confirmed_at is {bora['confirmed_at']!r}, expected {FIXED_NOW}")
        expect(bora["waitlist_position"] is None, f"promoted waitlist_position is {bora['waitlist_position']}")
        expect(chan["status"] == "waitlisted" and chan["waitlist_position"] == 1, f"second waitlisted: {chan}")
        ev = event(app, "rust-workshop")
        expect((ev["confirmed_count"], ev["seats_left"], ev["waitlist_count"]) == (1, 0, 1), f"event counts: {ev}")
        app.restart()
        expect(reg(app, 4)["status"] == "confirmed", "promotion lost after restart")


@checks.add("EV-INT-1", "registration pages show the promotion after cancelling in the browser")
def promotion_in_ui(project, root):
    with App(project, root) as app:
        async def scenario(page):
            await page.goto(app.base_url + "/registration.html?id=3&token=seed-token-3")
            await page.wait_for_selector("#registration:not([hidden])")
            await page.click("#cancel-button")
            await page.wait_for_function("document.querySelector('#registration-state')?.textContent.trim() === 'Cancelled'")
            await page.goto(app.base_url + "/registration.html?id=4&token=seed-token-4")
            await page.wait_for_selector("#registration:not([hidden])")
            state = (await page.text_content("#registration-state")).strip()
            expect(state == "Confirmed", f"promoted person's page shows {state!r}")
            await page.goto(app.base_url + "/registration.html?id=5&token=seed-token-5")
            await page.wait_for_selector("#registration-position:not([hidden])")
            position = (await page.text_content("#registration-position")).strip()
            expect("number 1" in position, f"remaining waitlisted page shows {position!r}")

        run_in_browser(scenario)


@checks.add("EV-INT-2", "repeat cancels and waitlisted cancels never promote extra people")
def no_extra_promotion(project, root):
    with App(project, root) as app:
        cancel(app, 5)
        expect(reg(app, 3)["status"] == "confirmed", "cancelling a waitlisted person changed the confirmed one")
        expect(reg(app, 4)["waitlist_position"] == 1, "waitlist order wrong after waitlisted cancel")
        cancel(app, 3)
        cancel(app, 3)
        expect(reg(app, 4)["status"] == "confirmed", "first waitlisted not promoted")
        ev = event(app, "rust-workshop")
        expect((ev["confirmed_count"], ev["waitlist_count"]) == (1, 0), f"event counts after repeats: {ev}")


@checks.add("EV-INT-2", "cancelling with an empty waitlist just frees the seat")
def empty_waitlist(project, root):
    with App(project, root) as app:
        before = app.sql("SELECT COUNT(*) AS n FROM registrations")[0]["n"]
        cancel(app, 2)
        ev = event(app, "spring-meetup")
        expect((ev["confirmed_count"], ev["seats_left"]) == (1, 2), f"event counts: {ev}")
        expect(app.sql("SELECT COUNT(*) AS n FROM registrations")[0]["n"] == before, "registration rows were added")
