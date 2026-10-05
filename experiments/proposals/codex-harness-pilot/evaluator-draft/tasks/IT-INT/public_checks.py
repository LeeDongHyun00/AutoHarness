from lib import App, CheckList, expect, run_in_browser

checks = CheckList("issue-tracker", "IT-INT")
BOB = {"X-User-Id": "2"}
CAROL = {"X-User-Id": "3"}


def assign(app, issue_id, assignee_id, headers=BOB, project="CORE"):
    return app.request("PATCH", f"/api/projects/{project}/issues/{issue_id}/assignee",
                       {"assignee_id": assignee_id}, headers)


def get_issue(app, issue_id, project="CORE"):
    status, body = app.request("GET", f"/api/projects/{project}/issues/{issue_id}", headers=BOB)
    expect(status == 200, f"GET issue {issue_id} returned {status}: {body}")
    return body["issue"]


def listed(app, project="CORE"):
    status, body = app.request("GET", f"/api/projects/{project}/issues", headers=BOB)
    expect(status == 200, f"list returned {status}: {body}")
    return {issue["id"]: issue for issue in body["issues"]}


@checks.add("IT-INT-1", "member assigns an active project member; list, detail and restart agree")
def assign_via_api(project, root):
    with App(project, root) as app:
        expect(get_issue(app, 1).get("assignee", "missing") is None, "unassigned issue must have assignee null")
        status, body = assign(app, 1, 1)
        expect(status == 200, f"expected 200, got {status} {body}")
        expected = {"id": 1, "name": "Alice Kim"}
        expect(body["issue"].get("assignee") == expected, f"response assignee: {body['issue'].get('assignee')}")
        expect(get_issue(app, 1)["assignee"] == expected, "detail does not show the assignee")
        expect(listed(app)[1]["assignee"] == expected, "list does not show the assignee")
        app.restart()
        expect(get_issue(app, 1)["assignee"] == expected, "assignee lost after server restart")
        status, body = app.request("POST", "/api/projects/CORE/issues", {"title": "fresh"}, BOB)
        expect(status == 201 and body["issue"].get("assignee", "missing") is None, f"new issue assignee: {body}")


@checks.add("IT-INT-1", "detail page assigns and the list shows the name after reload")
def assign_via_ui(project, root):
    with App(project, root) as app:
        async def scenario(page):
            await page.add_init_script("localStorage.setItem('issueTracker.userId', '2')")
            await page.goto(app.base_url + "/issue.html?project=CORE&id=1")
            await page.wait_for_selector("#issue:not([hidden])")
            expect((await page.text_content("#issue-assignee")).strip() == "Unassigned", "initial assignee text")
            await page.select_option("#assignee-select", "3")
            await page.click("#assignee-form button[type=submit]")
            await page.wait_for_function("document.querySelector('#issue-assignee')?.textContent.trim() === 'Carol Park'")
            await page.reload()
            await page.wait_for_function("document.querySelector('#issue-assignee')?.textContent.trim() === 'Carol Park'")
            await page.goto(app.base_url + "/?project=CORE")
            await page.wait_for_selector("#issue-list .issue[data-issue-id='1'] .issue-assignee")
            first = (await page.text_content("#issue-list .issue[data-issue-id='1'] .issue-assignee")).strip()
            other = (await page.text_content("#issue-list .issue[data-issue-id='2'] .issue-assignee")).strip()
            expect(first == "Carol Park", f"list assignee for #1: {first!r}")
            expect(other == "Unassigned", f"list assignee for #2: {other!r}")

        run_in_browser(scenario)


@checks.add("IT-INT-2", "unassign works; invalid assignees are 400 and change nothing")
def invalid_assignees(project, root):
    with App(project, root) as app:
        status, _ = assign(app, 2, 2)
        expect(status == 200, f"setup assignment failed: {status}")
        for assignee_id, why in ((4, "inactive member"), (5, "not a project member"), (999, "unknown user")):
            status, body = assign(app, 2, assignee_id)
            expect(status == 400, f"{why}: expected 400, got {status} {body}")
            expect(body.get("error", {}).get("code") == "bad_request", f"{why}: error body {body}")
            expect(get_issue(app, 2)["assignee"] == {"id": 2, "name": "Bob Lee"}, f"{why}: assignee changed")
        status, body = assign(app, 2, None)
        expect(status == 200 and body["issue"]["assignee"] is None, f"unassign: {status} {body}")


@checks.add("IT-INT-2", "viewer cannot assign (403) and nothing changes")
def viewer_forbidden(project, root):
    with App(project, root) as app:
        status, body = assign(app, 1, 2, headers=CAROL)
        expect(status == 403, f"expected 403, got {status} {body}")
        expect(get_issue(app, 1)["assignee"] is None, "assignee changed after forbidden request")
