from lib import App, CheckList, expect, run_in_browser

checks = CheckList("issue-tracker", "IT-FE")


async def wait_for_ids(page, expected):
    try:
        await page.wait_for_function(
            "ids => JSON.stringify([...document.querySelectorAll('#issue-list .issue')]"
            ".map(li => Number(li.dataset.issueId))) === JSON.stringify(ids)",
            arg=expected,
        )
    except Exception:
        actual = await page.eval_on_selector_all("#issue-list .issue", "els => els.map(e => Number(e.dataset.issueId))")
        raise AssertionError(f"issue list is {actual}, expected {expected}")


async def controls(page):
    return await page.input_value("#status-filter"), await page.input_value("#sort-order")


def query(page):
    from urllib.parse import parse_qs, urlparse

    return {k: v[0] for k, v in parse_qs(urlparse(page.url).query).items()}


@checks.add("IT-FE-1", "status=open + sort=created-asc survives a reload")
def reload_keeps_filters(project, root):
    with App(project, root) as app:
        async def scenario(page):
            await page.goto(app.base_url + "/?project=CORE")
            await wait_for_ids(page, [7, 6, 5, 4, 3, 2, 1])
            await page.select_option("#status-filter", "open")
            await wait_for_ids(page, [6, 4, 1])
            await page.select_option("#sort-order", "created-asc")
            await wait_for_ids(page, [1, 4, 6])
            await page.reload()
            await wait_for_ids(page, [1, 4, 6])
            expect(await controls(page) == ("open", "created-asc"), f"controls after reload: {await controls(page)}")
            q = query(page)
            expect(q.get("status") == "open" and q.get("sort") == "created-asc", f"URL query after reload: {q}")

        run_in_browser(scenario)


@checks.add("IT-FE-2", "back and forward restore each history entry")
def history_navigation(project, root):
    with App(project, root) as app:
        async def scenario(page):
            await page.goto(app.base_url + "/?project=CORE")
            await wait_for_ids(page, [7, 6, 5, 4, 3, 2, 1])
            await page.select_option("#status-filter", "done")
            await wait_for_ids(page, [7, 3])
            await page.select_option("#sort-order", "title-asc")
            await wait_for_ids(page, [3, 7])
            await page.go_back()
            await wait_for_ids(page, [7, 3])
            expect(await controls(page) == ("done", "created-desc"), f"after 1st back: {await controls(page)}")
            await page.go_back()
            await wait_for_ids(page, [7, 6, 5, 4, 3, 2, 1])
            expect(await controls(page) == ("", "created-desc"), f"after 2nd back: {await controls(page)}")
            await page.go_forward()
            await wait_for_ids(page, [7, 3])
            expect(await controls(page) == ("done", "created-desc"), f"after forward: {await controls(page)}")

        run_in_browser(scenario)


@checks.add("IT-FE-2", "direct links apply filters; unknown values fall back to defaults")
def direct_links(project, root):
    with App(project, root) as app:
        async def scenario(page):
            await page.goto(app.base_url + "/?project=CORE&status=in_progress&sort=created-asc")
            await wait_for_ids(page, [2, 5])
            expect(await controls(page) == ("in_progress", "created-asc"), f"direct link controls: {await controls(page)}")
            await page.goto(app.base_url + "/?project=CORE&status=bogus&sort=nope")
            await wait_for_ids(page, [7, 6, 5, 4, 3, 2, 1])
            expect(await controls(page) == ("", "created-desc"), f"unknown values controls: {await controls(page)}")
            expect(not await page.is_visible("#list-message"), "an error message is shown for unknown URL values")

        run_in_browser(scenario)


@checks.add("IT-FE-REG", "issue links, empty results and project parameter still work")
def regressions(project, root):
    with App(project, root) as app:
        async def scenario(page):
            # Filters are chosen in the UI here: reading them from the URL is the
            # task itself, so this regression check must not depend on it.
            await page.goto(app.base_url + "/?project=OPS")
            await wait_for_ids(page, [9, 8])
            await page.select_option("#status-filter", "in_progress")
            await page.wait_for_selector("#list-message:not([hidden])")
            text = (await page.text_content("#list-message")).strip()
            expect(text == "No issues match these filters.", f"empty-state message: {text!r}")
            await page.goto(app.base_url + "/?project=CORE")
            await wait_for_ids(page, [7, 6, 5, 4, 3, 2, 1])
            await page.select_option("#status-filter", "open")
            await wait_for_ids(page, [6, 4, 1])
            await page.click("#issue-list .issue[data-issue-id='4'] a")
            await page.wait_for_selector("#issue:not([hidden])")
            title = await page.text_content("#issue-title")
            expect(title == "Rate limit password reset endpoint", f"detail page title: {title!r}")

        run_in_browser(scenario)
