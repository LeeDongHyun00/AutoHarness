import asyncio

from lib import App, CheckList, expect, run_in_browser

checks = CheckList("event-signup", "EV-FE")
VALUES = {"#name": "Dana Lim", "#email": "dana@example.com", "#affiliation": "Umbrella", "#note": "Step-free access"}
SIGNUP_URL = "**/api/events/design-clinic/registrations"


async def open_form(page, app):
    await page.goto(app.base_url + "/event.html?slug=design-clinic")
    await page.wait_for_selector("#signup-form:not([hidden])")
    for selector, value in VALUES.items():
        await page.fill(selector, value)


async def field_values(page):
    return {selector: await page.input_value(selector) for selector in VALUES}


def count_rows(app, email):
    return app.sql("SELECT COUNT(*) AS n FROM registrations WHERE email = ?", (email,))[0]["n"]


@checks.add("EV-FE-1", "a 503 keeps every value, shows an error and re-enables the button")
def failure_keeps_input(project, root):
    with App(project, root) as app:
        async def scenario(page):
            async def fail(route):
                await route.fulfill(status=503, content_type="application/json",
                                    body='{"detail": "service unavailable", "code": "unavailable"}')

            await page.route(SIGNUP_URL, fail)
            await open_form(page, app)
            await page.click("#submit-button")
            await page.wait_for_selector("#form-error:not([hidden])")
            expect((await page.text_content("#form-error")).strip() != "", "error message is empty")
            await page.wait_for_function("!document.querySelector('#submit-button')?.disabled")
            expect(await field_values(page) == VALUES, f"values after failure: {await field_values(page)}")

        run_in_browser(scenario)
        expect(count_rows(app, "dana@example.com") == 0, "a registration was stored for a failed request")


@checks.add("EV-FE-2", "retry after a failure sends the kept values and succeeds")
def retry_succeeds(project, root):
    with App(project, root) as app:
        async def scenario(page):
            state = {"failed": False}

            async def fail_once(route):
                if not state["failed"]:
                    state["failed"] = True
                    await route.fulfill(status=503, content_type="application/json",
                                        body='{"detail": "service unavailable", "code": "unavailable"}')
                else:
                    await route.continue_()

            await page.route(SIGNUP_URL, fail_once)
            await open_form(page, app)
            await page.click("#submit-button")
            await page.wait_for_function("!document.querySelector('#submit-button')?.disabled")
            await page.click("#submit-button")
            await page.wait_for_selector("#confirmation:not([hidden])")

        run_in_browser(scenario)
        rows = app.sql("SELECT name, affiliation, note FROM registrations WHERE email = ?", ("dana@example.com",))
        expect(len(rows) == 1, f"expected exactly one stored registration, found {len(rows)}")
        stored = (rows[0]["name"], rows[0]["affiliation"], rows[0]["note"])
        expect(stored == ("Dana Lim", "Umbrella", "Step-free access"), f"stored values: {stored}")


@checks.add("EV-FE-2", "extra clicks while a request is pending send no extra request")
def single_request_while_pending(project, root):
    with App(project, root) as app:
        async def scenario(page):
            sent = []

            async def slow(route):
                sent.append(route.request.method)
                await asyncio.sleep(1.0)
                await route.continue_()

            await page.route(SIGNUP_URL, slow)
            await open_form(page, app)
            for _ in range(3):
                await page.click("#submit-button", force=True, no_wait_after=True)
            await page.wait_for_selector("#confirmation:not([hidden])")
            await asyncio.sleep(0.5)
            expect(sent.count("POST") == 1, f"expected 1 POST, saw {sent.count('POST')}")

        run_in_browser(scenario)
        expect(count_rows(app, "dana@example.com") == 1, "more than one registration stored")


@checks.add("EV-FE-REG", "client-side validation still blocks an empty name without a request")
def validation_kept(project, root):
    with App(project, root) as app:
        async def scenario(page):
            sent = []
            page.on("request", lambda req: req.method == "POST" and sent.append(req.url))
            await open_form(page, app)
            await page.fill("#name", "")
            await page.click("#submit-button")
            await page.wait_for_selector("[data-error-for='name']:not([hidden])")
            await asyncio.sleep(0.3)
            expect(sent == [], f"a request was sent despite invalid input: {sent}")

        run_in_browser(scenario)
