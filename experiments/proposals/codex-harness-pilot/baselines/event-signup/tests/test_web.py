import json
import urllib.error
import urllib.request

from tests.fixtures import ServerCase


class WebTest(ServerCase):
    def fetch(self, method, path, body=None, token=None):
        headers = {"Content-Type": "application/json"} if body is not None else {}
        if token:
            headers["X-Registration-Token"] = token
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def test_list_events_with_seat_counts(self):
        status, body = self.fetch("GET", "/api/events")
        self.assertEqual(status, 200)
        summary = {e["slug"]: (e["seats_left"], e["waitlist_count"]) for e in body["events"]}
        self.assertEqual(summary, {"spring-meetup": (1, 0), "rust-workshop": (0, 2), "design-clinic": (2, 0)})

    def test_signup_returns_201_and_token(self):
        status, body = self.fetch(
            "POST", "/api/events/design-clinic/registrations", {"name": "Dana", "email": "dana@example.com"}
        )
        self.assertEqual(status, 201)
        reg = body["registration"]
        status, body = self.fetch("GET", f"/api/registrations/{reg['id']}", token=reg["token"])
        self.assertEqual((status, body["registration"]["status"]), (200, "confirmed"))

    def test_errors_use_detail_and_code(self):
        status, body = self.fetch("POST", "/api/events/design-clinic/registrations", {"name": "", "email": "x"})
        self.assertEqual(status, 400)
        self.assertEqual(body["code"], "invalid_input")
        self.assertIn("detail", body)

    def test_duplicate_is_409(self):
        status, body = self.fetch(
            "POST", "/api/events/spring-meetup/registrations", {"name": "Junho", "email": "junho@example.com"}
        )
        self.assertEqual((status, body["code"]), (409, "already_registered"))

    def test_cancel_endpoint(self):
        status, body = self.fetch("POST", "/api/registrations/2/cancel", token="seed-token-2")
        self.assertEqual((status, body["registration"]["status"]), (200, "cancelled"))

    def test_cancel_with_wrong_token_is_404(self):
        status, body = self.fetch("POST", "/api/registrations/2/cancel", token="nope")
        self.assertEqual((status, body["code"]), (404, "registration_not_found"))

    def test_static_index(self):
        with urllib.request.urlopen(self.base_url + "/") as resp:
            self.assertIn(b"event-list", resp.read())

    def test_static_traversal_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self.base_url + "/../app/store.py")
        self.assertEqual(ctx.exception.code, 404)
