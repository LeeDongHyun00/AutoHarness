"""SQLite access. Functions here run single statements and never commit;
registrations.py decides where a unit of work ends."""

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")

REGISTRATION_COLUMNS = (
    "r.id, r.event_id, e.slug AS event_slug, e.title AS event_title, r.name, r.email,"
    " r.affiliation, r.note, r.status, r.token, r.created_at, r.waitlisted_at,"
    " r.confirmed_at, r.cancelled_at"
)


class DuplicateRegistration(Exception):
    pass


def connect(path):
    # The server is threaded; each request opens and closes its own connection.
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path, seed=False):
    conn = connect(path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        if seed:
            from . import seed as seed_data

            seed_data.load(conn)
        conn.commit()
    finally:
        conn.close()


def list_events(conn):
    return conn.execute(
        "SELECT e.id, e.slug, e.title, e.starts_at, e.capacity,"
        " SUM(r.status = 'confirmed') AS confirmed_count,"
        " SUM(r.status = 'waitlisted') AS waitlist_count"
        " FROM events e LEFT JOIN registrations r ON r.event_id = e.id"
        " GROUP BY e.id ORDER BY e.starts_at, e.id"
    ).fetchall()


def get_event(conn, slug):
    return conn.execute(
        "SELECT e.id, e.slug, e.title, e.starts_at, e.capacity,"
        " SUM(r.status = 'confirmed') AS confirmed_count,"
        " SUM(r.status = 'waitlisted') AS waitlist_count"
        " FROM events e LEFT JOIN registrations r ON r.event_id = e.id"
        " WHERE e.slug = ? GROUP BY e.id",
        (slug,),
    ).fetchone()


def count_confirmed(conn, event_id):
    return conn.execute(
        "SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'confirmed'", (event_id,)
    ).fetchone()[0]


def insert_registration(conn, event_id, fields, status, token, now):
    try:
        cur = conn.execute(
            "INSERT INTO registrations (event_id, name, email, affiliation, note, status, token,"
            " created_at, waitlisted_at, confirmed_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event_id,
                fields["name"],
                fields["email"],
                fields["affiliation"],
                fields["note"],
                status,
                token,
                now,
                now if status == "waitlisted" else None,
                now if status == "confirmed" else None,
            ),
        )
    except sqlite3.IntegrityError as err:
        if "registrations.event_id, registrations.email" in str(err):
            raise DuplicateRegistration() from err
        raise
    return cur.lastrowid


def get_registration(conn, registration_id):
    return conn.execute(
        f"SELECT {REGISTRATION_COLUMNS} FROM registrations r JOIN events e ON e.id = r.event_id WHERE r.id = ?",
        (registration_id,),
    ).fetchone()


def mark_cancelled(conn, registration_id, now):
    conn.execute(
        "UPDATE registrations SET status = 'cancelled', cancelled_at = ? WHERE id = ?", (now, registration_id)
    )


def list_waitlist(conn, event_id):
    return conn.execute(
        "SELECT id, name, waitlisted_at FROM registrations"
        " WHERE event_id = ? AND status = 'waitlisted' ORDER BY waitlisted_at, id",
        (event_id,),
    ).fetchall()


def waitlist_position(conn, event_id, waitlisted_at, registration_id):
    ahead = conn.execute(
        "SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'waitlisted'"
        " AND (waitlisted_at < ? OR (waitlisted_at = ? AND id < ?))",
        (event_id, waitlisted_at, waitlisted_at, registration_id),
    ).fetchone()[0]
    return ahead + 1
