from lib import App, CheckList, expect

checks = CheckList("issue-tracker", "IT-BE")
ALICE = {"X-User-Id": "1"}
BOB = {"X-User-Id": "2"}
ERIN = {"X-User-Id": "5"}
STATES = ("open", "in_progress", "done")
ALLOWED = {("open", "in_progress"), ("in_progress", "done")}


def patch_status(app, project, issue_id, status, headers):
    return app.request("PATCH", f"/api/projects/{project}/issues/{issue_id}/status", {"status": status}, headers)


def get_issue(app, project, issue_id, headers=ALICE):
    status, body = app.request("GET", f"/api/projects/{project}/issues/{issue_id}", headers=headers)
    expect(status == 200, f"GET {project}/{issue_id} returned {status}: {body}")
    return body["issue"]


def new_issue(app, title, headers=BOB, project="CORE"):
    status, body = app.request("POST", f"/api/projects/{project}/issues", {"title": title}, headers)
    expect(status == 201, f"creating issue failed: {status} {body}")
    return body["issue"]["id"]


def bring_to(app, project, issue_id, state, headers):
    path = {"open": [], "in_progress": ["in_progress"], "done": ["in_progress", "done"]}[state]
    for step in path:
        status, body = patch_status(app, project, issue_id, step, headers)
        expect(status == 200, f"setup move to {step} failed: {status} {body}")


@checks.add("IT-BE-H1", "every transition between the three states follows the lifecycle")
def full_matrix(project, root):
    with App(project, root, now="2026-10-07T01:02:03Z") as app:
        for source in STATES:
            for target in STATES:
                issue_id = new_issue(app, f"matrix {source}->{target}")
                bring_to(app, "CORE", issue_id, source, BOB)
                before = get_issue(app, "CORE", issue_id)
                status, body = patch_status(app, "CORE", issue_id, target, BOB)
                after = get_issue(app, "CORE", issue_id)
                if source == target:
                    expect(status == 200 and after == before, f"{source}->{target}: expected unchanged 200, got {status}")
                elif (source, target) in ALLOWED:
                    expect(status == 200 and after["status"] == target, f"{source}->{target}: expected 200, got {status} {body}")
                else:
                    expect(status == 409, f"{source}->{target}: expected 409, got {status} {body}")
                    expect(body.get("error", {}).get("code") == "conflict", f"{source}->{target}: wrong error body {body}")
                    expect(after == before, f"{source}->{target}: issue changed after 409")


@checks.add("IT-BE-H1", "repeated skip attempts stay rejected; other project follows the same rules")
def repeated_and_other_project(project, root):
    with App(project, root) as app:
        for _ in range(3):
            status, _body = patch_status(app, "CORE", 6, "done", BOB)
            expect(status == 409, f"repeated open->done on CORE/6 returned {status}")
        expect(get_issue(app, "CORE", 6)["status"] == "open", "CORE/6 left open state")
        status, body = patch_status(app, "OPS", 8, "done", ERIN)
        expect(status == 409, f"OPS/8 open->done returned {status} {body}")
        status, body = patch_status(app, "OPS", 9, "open", ERIN)
        expect(status == 409, f"OPS/9 done->open returned {status} {body}")
        status, body = patch_status(app, "OPS", 8, "in_progress", ERIN)
        expect(status == 200, f"OPS/8 open->in_progress returned {status} {body}")


@checks.add("IT-BE-H1", "permission contract is preserved")
def permissions(project, root):
    with App(project, root) as app:
        status, _ = patch_status(app, "CORE", 1, "in_progress", ERIN)
        expect(status == 403, f"non-member got {status}")
        status, _ = patch_status(app, "CORE", 1, "in_progress", {"X-User-Id": "4"})
        expect(status == 401, f"inactive user got {status}")
        status, _ = patch_status(app, "CORE", 1, "in_progress", {})
        expect(status == 401, f"missing user header got {status}")
        expect(get_issue(app, "CORE", 1)["status"] == "open", "issue changed by unauthorised requests")
        status, _ = patch_status(app, "CORE", 8, "in_progress", BOB)
        expect(status == 404, f"issue from another project via CORE got {status}")
