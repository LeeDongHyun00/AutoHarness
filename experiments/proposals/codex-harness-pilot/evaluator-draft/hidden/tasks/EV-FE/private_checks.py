import asyncio

from lib import App, CheckList, expect, run_in_browser

checks = CheckList("event-signup", "EV-FE")
VALUES = {"#name": "김하늘", "#email": "haneul@example.com", "#affiliation": "Café Ünïcode",
          "#note": "First line\nSecond line"}


async def fill(page, app, slug, values):
    await page.goto(app.base_url + f"/event.html?slug={slug}")
    await page.wait_for_selector("#signup-form:not([hidden])")
    for selector, value in values.items():
        await page.fill(selector, value)


async def values_of(page, values):
    return {selector: await page.input_value(selector) for selector in values}


async def assert_recoverable(page, values, why):
    await page.wait_for_selector("#form-error:not([hidden])")
    expect((await page.text_content("#form-error")).strip() != "", f"{why}: empty error message")
    await page.wait_for_function("!document.querySelector('#submit-button')?.disabled")
    got = await values_of(page, values)
    expect(got == values, f"{why}: values not kept: {got}")


@checks.add("EV-FE-H1", "network error then 500 then success, with unicode and multi-line values")
def failure_sequence(project, root):
    with App(project, root) as app:
        async def scenario(page):
            calls = []

            async def handler(route):
                calls.append(1)
                if len(calls) == 1:
                    await route.abort("failed")
                elif len(calls) == 2:
                    await route.fulfill(status=500, content_type="application/json",
                                        body='{"detail": "boom", "code": "internal_error"}')
                else:
                    await route.continue_()

            await page.route("**/api/events/spring-meetup/registrations", handler)
            await fill(page, app, "spring-meetup", VALUES)
            await page.click("#submit-button")
            await assert_recoverable(page, VALUES, "network error")
            await page.click("#submit-button")
            await page.wait_for_function("document.querySelector('#form-error')?.textContent.trim() !== ''")
            await assert_recoverable(page, VALUES, "HTTP 500")
            await page.click("#submit-button")
            await page.wait_for_selector("#confirmation:not([hidden])")
            expect(len(calls) == 3, f"expected 3 attempts, saw {len(calls)}")

        run_in_browser(scenario)
        rows = app.sql("SELECT name, affiliation, note FROM registrations WHERE email = ?", ("haneul@example.com",))
        expect(len(rows) == 1, f"stored rows: {len(rows)}")
        expect((rows[0]["name"], rows[0]["affiliation"], rows[0]["note"]) == ("김하늘", "Café Ünïcode", "First line\nSecond line"),
               f"stored values: {dict(rows[0])}")


@checks.add("EV-FE-H1", "a real 409 keeps the values; fixing the email then succeeds once")
def real_conflict(project, root):
    with App(project, root) as app:
        dup = {"#name": "Minji Again", "#email": "minji@example.com", "#affiliation": "", "#note": "dup"}

        async def scenario(page):
            posts = []
            page.on("request", lambda r: r.method == "POST" and posts.append(r.url))
            await fill(page, app, "spring-meetup", dup)
            await page.click("#submit-button")
            await assert_recoverable(page, dup, "409 already_registered")
            await page.fill("#email", "minji.second@example.com")
            await page.click("#submit-button")
            await page.wait_for_selector("#confirmation:not([hidden])")
            await asyncio.sleep(0.3)
            expect(len(posts) == 2, f"expected 2 POSTs, saw {len(posts)}")

        run_in_browser(scenario)
        expect(len(app.sql("SELECT id FROM registrations WHERE email = 'minji.second@example.com'")) == 1,
               "corrected signup not stored exactly once")


@checks.add("EV-FE-H1", "slow failure: clicks while pending send nothing extra, then retry works")
def slow_failure(project, root):
    with App(project, root) as app:
        async def scenario(page):
            calls = []

            async def handler(route):
                calls.append(1)
                if len(calls) == 1:
                    await asyncio.sleep(1.0)
                    await route.fulfill(status=503, content_type="application/json",
                                        body='{"detail": "busy", "code": "unavailable"}')
                else:
                    await route.continue_()

            values = {"#name": "Slow Path", "#email": "slow@example.com", "#affiliation": "X", "#note": ""}
            await page.route("**/api/events/design-clinic/registrations", handler)
            await fill(page, app, "design-clinic", values)
            for _ in range(4):
                await page.click("#submit-button", force=True, no_wait_after=True)
            await assert_recoverable(page, values, "slow 503")
            expect(len(calls) == 1, f"pending clicks sent {len(calls)} requests")
            await page.click("#submit-button")
            await page.wait_for_selector("#confirmation:not([hidden])")

        run_in_browser(scenario)
        expect(len(app.sql("SELECT id FROM registrations WHERE email = 'slow@example.com'")) == 1, "retry not stored once")
