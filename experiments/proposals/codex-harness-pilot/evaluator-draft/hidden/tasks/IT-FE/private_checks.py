from urllib.parse import parse_qs, urlparse

from lib import App, CheckList, expect, run_in_browser

checks = CheckList("issue-tracker", "IT-FE")
BOB = {"X-User-Id": "2"}


async def ids(page):
    return await page.eval_on_selector_all("#issue-list .issue", "els => els.map(e => Number(e.dataset.issueId))")


async def wait_for_ids(page, expected):
    try:
        await page.wait_for_function(
            "ids => JSON.stringify([...document.querySelectorAll('#issue-list .issue')]"
            ".map(li => Number(li.dataset.issueId))) === JSON.stringify(ids)",
            arg=expected,
        )
    except Exception:
        raise AssertionError(f"issue list is {await ids(page)}, expected {expected}")


async def controls(page):
    return await page.input_value("#status-filter"), await page.input_value("#sort-order")


def add_issues(app):
    # Extra data so expectations differ from the public checks.
    created = []
    for title in ("Zebra crossing icon missing", "alpha build fails on CI", "Middle priority cleanup"):
        status, body = app.request("POST", "/api/projects/CORE/issues", {"title": title}, BOB)
        expect(status == 201, f"setup create failed: {status} {body}")
        created.append(body["issue"]["id"])
    return created


@checks.add("IT-FE-H1", "three-step history with reload in the middle, on different data")
def long_history(project, root):
    with App(project, root, now="2026-10-08T00:00:00Z") as app:
        z, a, m = add_issues(app)
        open_by_title = sorted([(t, i) for t, i in [
            ("Login page shows blank screen on Safari", 1), ("Rate limit password reset endpoint", 4),
            ("Archive old audit logs", 6), ("Zebra crossing icon missing", z),
            ("alpha build fails on CI", a), ("Middle priority cleanup", m)]], key=lambda x: (x[0].lower(), x[1]))
        open_title_ids = [i for _, i in open_by_title]

        async def scenario(page):
            await page.goto(app.base_url + "/?project=CORE")
            await wait_for_ids(page, [m, a, z, 7, 6, 5, 4, 3, 2, 1])
            await page.select_option("#sort-order", "title-asc")
            await page.select_option("#status-filter", "open")
            await wait_for_ids(page, open_title_ids)
            await page.select_option("#status-filter", "in_progress")
            await wait_for_ids(page, [2, 5])
            await page.reload()
            await wait_for_ids(page, [2, 5])
            expect(await controls(page) == ("in_progress", "title-asc"), f"after reload: {await controls(page)}")
            await page.go_back()
            await wait_for_ids(page, open_title_ids)
            expect(await controls(page) == ("open", "title-asc"), f"after back: {await controls(page)}")
            await page.go_back()
            await page.go_back()
            await wait_for_ids(page, [m, a, z, 7, 6, 5, 4, 3, 2, 1])
            expect(await controls(page) == ("", "created-desc"), f"at start: {await controls(page)}")
            await page.go_forward()
            await page.go_forward()
            await wait_for_ids(page, open_title_ids)

        run_in_browser(scenario)


@checks.add("IT-FE-H1", "unknown values are normalised independently; other project works")
def normalisation(project, root):
    with App(project, root) as app:
        async def scenario(page):
            await page.goto(app.base_url + "/?project=CORE&status=bogus&sort=title-asc")
            await page.wait_for_selector("#issue-list .issue")
            expect(await controls(page) == ("", "title-asc"), f"bogus status + valid sort: {await controls(page)}")
            expect(len(await ids(page)) == 7, f"expected all 7 CORE issues, got {await ids(page)}")
            await page.goto(app.base_url + "/?project=CORE&status=done&sort=sideways")
            await wait_for_ids(page, [7, 3])
            expect(await controls(page) == ("done", "created-desc"), f"valid status + bogus sort: {await controls(page)}")
            await page.goto(app.base_url + "/?project=OPS&status=done")
            await wait_for_ids(page, [9])
            expect(not await page.is_visible("#list-message"), "message shown for a valid OPS filter")

        run_in_browser(scenario)


@checks.add("IT-FE-H1", "detail page and browser back return to the filtered list")
def detail_round_trip(project, root):
    with App(project, root) as app:
        async def scenario(page):
            await page.goto(app.base_url + "/?project=CORE")
            await wait_for_ids(page, [7, 6, 5, 4, 3, 2, 1])
            await page.select_option("#status-filter", "open")
            await page.select_option("#sort-order", "created-asc")
            await wait_for_ids(page, [1, 4, 6])
            await page.click("#issue-list .issue[data-issue-id='6'] a")
            await page.wait_for_selector("#issue:not([hidden])")
            await page.go_back()
            await wait_for_ids(page, [1, 4, 6])
            expect(await controls(page) == ("open", "created-asc"), f"after returning: {await controls(page)}")
            q = {k: v[0] for k, v in parse_qs(urlparse(page.url).query).items()}
            expect(q.get("project") == "CORE", f"project lost from URL: {q}")

        run_in_browser(scenario)
