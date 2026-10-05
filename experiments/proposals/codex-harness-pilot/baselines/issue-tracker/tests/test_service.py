from app import service
from app.errors import BadRequest, Conflict, Forbidden, NotFound, Unauthorized

from tests.support import SeededDbTestCase

ALICE, BOB, CAROL, DAVE, ERIN = 1, 2, 3, 4, 5


class ListIssuesTest(SeededDbTestCase):
    def ids(self, **kwargs):
        return [issue["id"] for issue in service.list_issues(self.conn, ALICE, "CORE", **kwargs)]

    def test_default_sort_is_newest_first(self):
        self.assertEqual(self.ids(), [7, 6, 5, 4, 3, 2, 1])

    def test_status_filter(self):
        self.assertEqual(self.ids(status="open"), [6, 4, 1])

    def test_title_sort(self):
        self.assertEqual(self.ids(status="done", sort="title-asc"), [3, 7])

    def test_rejects_unknown_status_and_sort(self):
        with self.assertRaises(BadRequest):
            self.ids(status="closed")
        with self.assertRaises(BadRequest):
            self.ids(sort="priority")

    def test_viewer_can_read(self):
        self.assertEqual(len(service.list_issues(self.conn, CAROL, "CORE")), 7)


class AccessTest(SeededDbTestCase):
    def test_missing_user_is_unauthorized(self):
        with self.assertRaises(Unauthorized):
            service.list_issues(self.conn, None, "CORE")

    def test_inactive_user_is_unauthorized(self):
        with self.assertRaises(Unauthorized):
            service.list_issues(self.conn, DAVE, "CORE")

    def test_non_member_is_forbidden(self):
        with self.assertRaises(Forbidden):
            service.list_issues(self.conn, ERIN, "CORE")

    def test_unknown_project_is_not_found(self):
        with self.assertRaises(NotFound):
            service.list_issues(self.conn, ALICE, "NOPE")

    def test_issue_from_other_project_is_not_found(self):
        with self.assertRaises(NotFound):
            service.get_issue(self.conn, ALICE, "CORE", 8)


class CreateIssueTest(SeededDbTestCase):
    def test_member_creates_open_issue(self):
        issue = service.create_issue(self.conn, BOB, "CORE", {"title": "  New bug  ", "description": "steps"})
        self.assertEqual(issue["title"], "New bug")
        self.assertEqual(issue["status"], "open")
        self.assertEqual(issue["reporter"], {"id": BOB, "name": "Bob Lee"})
        self.assertEqual(issue["created_at"], self.now)

    def test_viewer_cannot_create(self):
        with self.assertRaises(Forbidden):
            service.create_issue(self.conn, CAROL, "CORE", {"title": "Nope"})

    def test_title_is_required(self):
        with self.assertRaises(BadRequest):
            service.create_issue(self.conn, BOB, "CORE", {"title": "   "})


class ChangeStatusTest(SeededDbTestCase):
    def status_of(self, issue_id):
        return service.get_issue(self.conn, ALICE, "CORE", issue_id)["status"]

    def test_open_to_in_progress(self):
        issue = service.change_status(self.conn, BOB, "CORE", 1, {"status": "in_progress"})
        self.assertEqual(issue["status"], "in_progress")
        self.assertEqual(issue["updated_at"], self.now)

    def test_in_progress_to_done(self):
        self.assertEqual(service.change_status(self.conn, BOB, "CORE", 2, {"status": "done"})["status"], "done")

    def test_same_status_is_a_no_op(self):
        issue = service.change_status(self.conn, BOB, "CORE", 1, {"status": "open"})
        self.assertEqual(issue["updated_at"], "2026-09-01T09:00:00Z")

    def test_done_cannot_move_backwards(self):
        with self.assertRaises(Conflict):
            service.change_status(self.conn, BOB, "CORE", 3, {"status": "open"})
        self.assertEqual(self.status_of(3), "done")

    def test_unknown_status_leaves_issue_unchanged(self):
        with self.assertRaises(BadRequest):
            service.change_status(self.conn, BOB, "CORE", 1, {"status": "closed"})
        self.assertEqual(self.status_of(1), "open")

    def test_missing_issue(self):
        with self.assertRaises(NotFound):
            service.change_status(self.conn, BOB, "CORE", 999, {"status": "done"})

    def test_viewer_cannot_change_status(self):
        with self.assertRaises(Forbidden):
            service.change_status(self.conn, CAROL, "CORE", 1, {"status": "in_progress"})
        self.assertEqual(self.status_of(1), "open")
