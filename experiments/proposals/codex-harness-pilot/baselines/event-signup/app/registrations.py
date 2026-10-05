"""Registration rules: capacity, waitlist and cancellation."""

import re
import secrets

from . import clock, store
from .errors import ConflictError, InvalidInput, NotFoundError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
FIELD_LIMITS = {"name": 100, "email": 254, "affiliation": 100, "note": 500}


def event_to_dict(row):
    confirmed = row["confirmed_count"] or 0
    return {
        "slug": row["slug"],
        "title": row["title"],
        "starts_at": row["starts_at"],
        "capacity": row["capacity"],
        "confirmed_count": confirmed,
        "seats_left": max(row["capacity"] - confirmed, 0),
        "waitlist_count": row["waitlist_count"] or 0,
    }


def registration_to_dict(conn, row, include_token=False):
    data = {
        "id": row["id"],
        "event": {"slug": row["event_slug"], "title": row["event_title"]},
        "name": row["name"],
        "email": row["email"],
        "affiliation": row["affiliation"],
        "note": row["note"],
        "status": row["status"],
        "created_at": row["created_at"],
        "waitlisted_at": row["waitlisted_at"],
        "confirmed_at": row["confirmed_at"],
        "cancelled_at": row["cancelled_at"],
        "waitlist_position": None,
    }
    if row["status"] == "waitlisted":
        data["waitlist_position"] = store.waitlist_position(conn, row["event_id"], row["waitlisted_at"], row["id"])
    # The token is the only credential for managing a registration, so it is
    # returned once at signup and never echoed afterwards.
    if include_token:
        data["token"] = row["token"]
    return data


def clean_fields(payload):
    fields = {}
    for name, limit in FIELD_LIMITS.items():
        value = payload.get(name)
        if value is None:
            value = ""
        if not isinstance(value, str):
            raise InvalidInput(f"{name} must be a string")
        value = value.strip()
        if len(value) > limit:
            raise InvalidInput(f"{name} must be at most {limit} characters")
        fields[name] = value
    if not fields["name"]:
        raise InvalidInput("name is required")
    fields["email"] = fields["email"].lower()
    if not EMAIL_RE.match(fields["email"]):
        raise InvalidInput("email is not valid")
    return fields


def _event_or_404(conn, slug):
    event = store.get_event(conn, slug)
    if event is None:
        raise NotFoundError("event not found", code="event_not_found")
    return event


def list_events(conn):
    return [event_to_dict(row) for row in store.list_events(conn)]


def get_event(conn, slug):
    return event_to_dict(_event_or_404(conn, slug))


def register(conn, slug, payload):
    event = _event_or_404(conn, slug)
    fields = clean_fields(payload)
    confirmed = store.count_confirmed(conn, event["id"])
    status = "confirmed" if confirmed < event["capacity"] else "waitlisted"
    try:
        registration_id = store.insert_registration(
            conn, event["id"], fields, status, secrets.token_urlsafe(16), clock.now()
        )
    except store.DuplicateRegistration:
        conn.rollback()
        raise ConflictError(
            "this email already has an active registration for the event", code="already_registered"
        )
    conn.commit()
    return registration_to_dict(conn, store.get_registration(conn, registration_id), include_token=True)


def _registration_for_token(conn, registration_id, token):
    row = store.get_registration(conn, registration_id)
    # Unknown ids and wrong tokens look identical so ids cannot be probed.
    if row is None or not token or not secrets.compare_digest(row["token"], token):
        raise NotFoundError("registration not found", code="registration_not_found")
    return row


def get_registration(conn, registration_id, token):
    return registration_to_dict(conn, _registration_for_token(conn, registration_id, token))


def cancel(conn, registration_id, token):
    row = _registration_for_token(conn, registration_id, token)
    if row["status"] == "cancelled":
        return registration_to_dict(conn, row)
    store.mark_cancelled(conn, row["id"], clock.now())
    conn.commit()
    return registration_to_dict(conn, store.get_registration(conn, row["id"]))


def waitlist(conn, slug):
    event = _event_or_404(conn, slug)
    return [
        {"position": position, "name": _mask(row["name"])}
        for position, row in enumerate(store.list_waitlist(conn, event["id"]), start=1)
    ]


def _mask(name):
    # The public waitlist shows order, not identities.
    return name[0] + "***" if name else ""
