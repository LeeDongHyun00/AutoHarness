from app import registrations
from app.errors import ConflictError, InvalidInput, NotFoundError

from tests.fixtures import FIXED_NOW, DatabaseCase


def signup(name, email, **extra):
    return dict({"name": name, "email": email}, **extra)


class RegisterTest(DatabaseCase):
    def test_confirmed_while_seats_remain(self):
        reg = registrations.register(self.conn, "spring-meetup", signup("Dana", "dana@example.com"))
        self.assertEqual(reg["status"], "confirmed")
        self.assertEqual(reg["confirmed_at"], FIXED_NOW)
        self.assertIsNone(reg["waitlist_position"])
        self.assertTrue(reg["token"])
        self.assertEqual(registrations.get_event(self.conn, "spring-meetup")["seats_left"], 0)

    def test_waitlisted_when_full(self):
        reg = registrations.register(self.conn, "rust-workshop", signup("Dana", "dana@example.com"))
        self.assertEqual(reg["status"], "waitlisted")
        self.assertEqual(reg["waitlisted_at"], FIXED_NOW)
        self.assertEqual(reg["waitlist_position"], 3)

    def test_fills_then_waitlists_in_order(self):
        first = registrations.register(self.conn, "design-clinic", signup("A", "a@example.com"))
        second = registrations.register(self.conn, "design-clinic", signup("B", "b@example.com"))
        third = registrations.register(self.conn, "design-clinic", signup("C", "c@example.com"))
        self.assertEqual([first["status"], second["status"], third["status"]], ["confirmed", "confirmed", "waitlisted"])

    def test_email_is_normalised_and_fields_trimmed(self):
        reg = registrations.register(
            self.conn, "design-clinic", signup("  Dana  ", " Dana@Example.COM ", affiliation=" Umbrella ")
        )
        self.assertEqual((reg["name"], reg["email"], reg["affiliation"]), ("Dana", "dana@example.com", "Umbrella"))

    def test_duplicate_active_email_is_rejected(self):
        with self.assertRaises(ConflictError) as ctx:
            registrations.register(self.conn, "spring-meetup", signup("Minji", "MINJI@example.com"))
        self.assertEqual(ctx.exception.code, "already_registered")

    def test_can_register_again_after_cancelling(self):
        registrations.cancel(self.conn, 1, "seed-token-1")
        reg = registrations.register(self.conn, "spring-meetup", signup("Minji", "minji@example.com"))
        self.assertEqual(reg["status"], "confirmed")

    def test_validation(self):
        for payload in (signup("", "x@example.com"), signup("X", "not-an-email"), signup("X", "x@example.com", note=5)):
            with self.subTest(payload=payload), self.assertRaises(InvalidInput):
                registrations.register(self.conn, "design-clinic", payload)

    def test_unknown_event(self):
        with self.assertRaises(NotFoundError) as ctx:
            registrations.register(self.conn, "nope", signup("X", "x@example.com"))
        self.assertEqual(ctx.exception.code, "event_not_found")


class ManageRegistrationTest(DatabaseCase):
    def test_lookup_requires_matching_token(self):
        self.assertEqual(registrations.get_registration(self.conn, 1, "seed-token-1")["status"], "confirmed")
        for token in ("wrong", "", None):
            with self.subTest(token=token), self.assertRaises(NotFoundError):
                registrations.get_registration(self.conn, 1, token)

    def test_token_is_not_echoed_after_signup(self):
        self.assertNotIn("token", registrations.get_registration(self.conn, 1, "seed-token-1"))

    def test_cancel_frees_a_seat(self):
        reg = registrations.cancel(self.conn, 2, "seed-token-2")
        self.assertEqual(reg["status"], "cancelled")
        self.assertEqual(reg["cancelled_at"], FIXED_NOW)
        self.assertEqual(registrations.get_event(self.conn, "spring-meetup")["seats_left"], 2)

    def test_cancel_twice_is_harmless(self):
        registrations.cancel(self.conn, 2, "seed-token-2")
        again = registrations.cancel(self.conn, 2, "seed-token-2")
        self.assertEqual(again["status"], "cancelled")
        self.assertEqual(registrations.get_event(self.conn, "spring-meetup")["seats_left"], 2)

    def test_waitlist_positions_follow_join_order(self):
        self.assertEqual(registrations.get_registration(self.conn, 4, "seed-token-4")["waitlist_position"], 1)
        self.assertEqual(registrations.get_registration(self.conn, 5, "seed-token-5")["waitlist_position"], 2)

    def test_public_waitlist_masks_names(self):
        self.assertEqual(
            registrations.waitlist(self.conn, "rust-workshop"),
            [{"position": 1, "name": "B***"}, {"position": 2, "name": "C***"}],
        )
