from lib import App, CheckList, expect, run_in_browser

checks = CheckList("issue-tracker", "IT-INT")
ALICE = {"X-User-Id": "1"}
BOB = {"X-User-Id": "2"}
ERIN = {"X-User-Id": "5"}


def assign(app, project, issue_id, body, headers):
    return app.request("PATCH", f"/api/projects/{project}/issues/{issue_id}/assignee", body, headers)


def get_issue(app, project, issue_id, headers=ALICE):
    status, body = app.request("GET", f"/api/projects/{project}/issues/{issue_id}", headers=headers)
    expect(status == 200, f"GET {project}/{issue_id}: {status} {body}")
    return body["issue"]


@checks.add("IT-INT-H1", "other project: membership is checked against that project")
def other_project(project, root):
    with App(project, root) as app:
        status, body = assign(app, "OPS", 8, {"assignee_id": 1}, ERIN)
        expect(status == 200 and body["issue"]["assignee"] == {"id": 1, "name": "Alice Kim"}, f"OPS assign: {status} {body}")
        status, body = assign(app, "OPS", 8, {"assignee_id": 2}, ERIN)
        expect(status == 400, f"Bob is not an OPS member: expected 400, got {status} {body}")
        expect(get_issue(app, "OPS", 8)["assignee"]["id"] == 1, "assignee changed by an invalid request")
        status, _ = assign(app, "OPS", 8, {"assignee_id": 5}, ALICE)
        expect(status == 200, f"OPS member Alice assigning admin Erin: {status}")


@checks.add("IT-INT-H1", "malformed bodies and missing targets are rejected without changes")
def malformed(project, root):
    with App(project, root) as app:
        assign(app, "CORE", 5, {"assignee_id": 2}, BOB)
        for body, why in (({"assignee_id": "1"}, "string id"), ({}, "missing field"),
                          ({"assignee_id": 1.5}, "fractional id")):
            status, resp = assign(app, "CORE", 5, body, BOB)
            expect(status == 400, f"{why}: expected 400, got {status} {resp}")
        expect(get_issue(app, "CORE", 5)["assignee"]["id"] == 2, "assignee changed by malformed requests")
        status, _ = assign(app, "CORE", 999, {"assignee_id": 1}, BOB)
        expect(status == 404, f"missing issue: {status}")
        status, _ = assign(app, "CORE", 8, {"assignee_id": 1}, BOB)
        expect(status == 404, f"issue of another project via CORE: {status}")
        status, _ = assign(app, "CORE", 5, {"assignee_id": 1}, {})
        expect(status == 401, f"missing user header: {status}")
        status, _ = assign(app, "CORE", 5, {"assignee_id": 1}, ERIN)
        expect(status == 403, f"non-member: {status}")


@checks.add("IT-INT-H1", "assignee survives status changes and appears in every issue response")
def survives_status_change(project, root):
    with App(project, root) as app:
        assign(app, "CORE", 1, {"assignee_id": 3}, ALICE)
        status, body = app.request("PATCH", "/api/projects/CORE/issues/1/status", {"status": "in_progress"}, BOB)
        expect(status == 200 and body["issue"].get("assignee") == {"id": 3, "name": "Carol Park"},
               f"status response assignee: {body}")
        status, body = assign(app, "CORE", 1, {"assignee_id": 2}, BOB)
        expect(body["issue"]["assignee"]["id"] == 2, "reassignment not applied")
        app.restart()
        status, body = app.request("GET", "/api/projects/CORE/issues?status=in_progress", headers=BOB)
        found = {i["id"]: i["assignee"] for i in body["issues"]}
        expect(found.get(1) == {"id": 2, "name": "Bob Lee"}, f"filtered list after restart: {found}")


@checks.add("IT-INT-H1", "UI offers only active members and can unassign")
def ui_options_and_unassign(project, root):
    with App(project, root) as app:
        assign(app, "CORE", 4, {"assignee_id": 1}, ALICE)

        async def scenario(page):
            await page.add_init_script("localStorage.setItem('issueTracker.userId', '1')")
            await page.goto(app.base_url + "/issue.html?project=CORE&id=4")
            await page.wait_for_function("document.querySelector('#issue-assignee')?.textContent.trim() === 'Alice Kim'")
            await page.wait_for_function("document.querySelectorAll('#assignee-select option').length >= 4")
            options = await page.eval_on_selector_all(
                "#assignee-select option", "els => els.map(o => [o.value, o.textContent.trim()])")
            values = sorted(v for v, _ in options)
            expect(values == ["", "1", "2", "3"], f"assignee options: {options}")
            await page.select_option("#assignee-select", "")
            await page.click("#assignee-form button[type=submit]")
            await page.wait_for_function("document.querySelector('#issue-assignee')?.textContent.trim() === 'Unassigned'")
            await page.goto(app.base_url + "/?project=CORE")
            await page.wait_for_selector("#issue-list .issue[data-issue-id='4'] .issue-assignee")
            text = (await page.text_content("#issue-list .issue[data-issue-id='4'] .issue-assignee")).strip()
            expect(text == "Unassigned", f"list shows {text!r} after unassigning")

        run_in_browser(scenario)
        expect(get_issue(app, "CORE", 4)["assignee"] is None, "unassignment not stored")
