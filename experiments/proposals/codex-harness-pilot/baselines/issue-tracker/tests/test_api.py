import json
import urllib.error
import urllib.request

from tests.support import LiveServerTestCase


class ApiTest(LiveServerTestCase):
    def call(self, method, path, body=None, user_id="1"):
        headers = {}
        if user_id is not None:
            headers["X-User-Id"] = user_id
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base_url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def test_missing_user_header_uses_error_envelope(self):
        status, body = self.call("GET", "/api/me", user_id=None)
        self.assertEqual(status, 401)
        self.assertEqual(body["error"]["code"], "unauthorized")

    def test_list_with_filter_and_sort(self):
        status, body = self.call("GET", "/api/projects/CORE/issues?status=open&sort=created-asc")
        self.assertEqual(status, 200)
        self.assertEqual([issue["id"] for issue in body["issues"]], [1, 4, 6])

    def test_create_issue(self):
        status, body = self.call("POST", "/api/projects/CORE/issues", {"title": "From API"}, user_id="2")
        self.assertEqual(status, 201)
        self.assertEqual(body["issue"]["status"], "open")

    def test_backwards_transition_is_conflict(self):
        status, body = self.call("PATCH", "/api/projects/CORE/issues/3/status", {"status": "open"})
        self.assertEqual(status, 409)
        self.assertEqual(body["error"]["code"], "conflict")

    def test_invalid_json_body(self):
        request = urllib.request.Request(
            self.base_url + "/api/projects/CORE/issues",
            data=b"{not json",
            method="POST",
            headers={"X-User-Id": "1", "Content-Type": "application/json"},
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request)
        self.assertEqual(ctx.exception.code, 400)

    def test_members_endpoint(self):
        status, body = self.call("GET", "/api/projects/CORE/members")
        self.assertEqual(status, 200)
        self.assertEqual([m["name"] for m in body["members"]], ["Alice Kim", "Bob Lee", "Carol Park", "Dave Choi"])


class StaticFilesTest(LiveServerTestCase):
    def test_index_is_served(self):
        with urllib.request.urlopen(self.base_url + "/") as response:
            self.assertIn(b"issue-list", response.read())

    def test_path_traversal_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.base_url + "/../app/db.py")
        self.assertEqual(ctx.exception.code, 404)
