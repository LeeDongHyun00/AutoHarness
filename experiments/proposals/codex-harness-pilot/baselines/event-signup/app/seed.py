"""Demo data used by `--init` and by the test suite."""

EVENTS = [
    (1, "spring-meetup", "Spring Community Meetup", "2026-11-20T18:00:00Z", 3),
    (2, "rust-workshop", "Intro to Rust Workshop", "2026-11-22T10:00:00Z", 1),
    (3, "design-clinic", "Design Review Clinic", "2026-11-25T14:00:00Z", 2),
]

# (id, event_id, name, email, affiliation, status, token, created_at)
REGISTRATIONS = [
    (1, 1, "Minji Seo", "minji@example.com", "Acme", "confirmed", "seed-token-1", "2026-10-01T09:00:00Z"),
    (2, 1, "Junho Han", "junho@example.com", "", "confirmed", "seed-token-2", "2026-10-01T09:30:00Z"),
    (3, 2, "Ara Yoon", "ara@example.com", "Globex", "confirmed", "seed-token-3", "2026-10-02T10:00:00Z"),
    (4, 2, "Bora Kang", "bora@example.com", "", "waitlisted", "seed-token-4", "2026-10-02T10:05:00Z"),
    (5, 2, "Chan Oh", "chan@example.com", "Initech", "waitlisted", "seed-token-5", "2026-10-02T10:20:00Z"),
]


def load(conn):
    conn.executemany("INSERT INTO events (id, slug, title, starts_at, capacity) VALUES (?, ?, ?, ?, ?)", EVENTS)
    for reg_id, event_id, name, email, affiliation, status, token, created_at in REGISTRATIONS:
        conn.execute(
            "INSERT INTO registrations (id, event_id, name, email, affiliation, status, token, created_at,"
            " waitlisted_at, confirmed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                reg_id,
                event_id,
                name,
                email,
                affiliation,
                status,
                token,
                created_at,
                created_at if status == "waitlisted" else None,
                created_at if status == "confirmed" else None,
            ),
        )
