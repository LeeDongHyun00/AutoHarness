from lib import App, CheckList, expect

checks = CheckList("issue-tracker", "IT-BE")
BOB = {"X-User-Id": "2"}
CAROL = {"X-User-Id": "3"}


def patch_status(app, issue_id, status, headers=BOB, project="CORE"):
    return app.request("PATCH", f"/api/projects/{project}/issues/{issue_id}/status", {"status": status}, headers)


def get_issue(app, issue_id, project="CORE"):
    status, body = app.request("GET", f"/api/projects/{project}/issues/{issue_id}", headers=BOB)
    expect(status == 200, f"GET issue {issue_id} returned {status}: {body}")
    return body["issue"]


@checks.add("IT-BE-1", "open -> in_progress -> done succeeds and is stored")
def forward_path(project, root):
    with App(project, root) as app:
        for target in ("in_progress", "done"):
            status, body = patch_status(app, 1, target)
            expect(status == 200, f"open path to {target}: expected 200, got {status} {body}")
            expect(body["issue"]["status"] == target, f"response status {body['issue']['status']!r} != {target!r}")
            expect(get_issue(app, 1)["status"] == target, f"stored status is not {target}")


@checks.add("IT-BE-1", "open -> done is rejected with 409 conflict and the issue stays open")
def skip_is_rejected(project, root):
    with App(project, root) as app:
        before = get_issue(app, 4)
        status, body = patch_status(app, 4, "done")
        expect(status == 409, f"expected 409, got {status} {body}")
        expect(body.get("error", {}).get("code") == "conflict", f"expected error code 'conflict', got {body}")
        after = get_issue(app, 4)
        expect(after == before, f"issue changed after rejected request: {before} -> {after}")


@checks.add("IT-BE-1", "requesting the current status succeeds without changes")
def same_status_no_op(project, root):
    with App(project, root) as app:
        before = get_issue(app, 2)
        status, body = patch_status(app, 2, "in_progress")
        expect(status == 200, f"expected 200, got {status} {body}")
        expect(get_issue(app, 2) == before, "issue changed on a same-status request")


@checks.add("IT-BE-2", "unknown status is 400 and missing issue is 404, nothing changes")
def invalid_inputs(project, root):
    with App(project, root) as app:
        before = get_issue(app, 1)
        status, body = patch_status(app, 1, "closed")
        expect(status == 400, f"unknown status: expected 400, got {status} {body}")
        expect(get_issue(app, 1) == before, "issue changed after unknown status")
        status, body = patch_status(app, 999, "in_progress")
        expect(status == 404, f"missing issue: expected 404, got {status} {body}")


@checks.add("IT-BE-2", "viewer cannot change status (403) and nothing changes")
def viewer_forbidden(project, root):
    with App(project, root) as app:
        before = get_issue(app, 1)
        status, body = patch_status(app, 1, "in_progress", headers=CAROL)
        expect(status == 403, f"expected 403, got {status} {body}")
        expect(get_issue(app, 1) == before, "issue changed after forbidden request")
