"""Demo data used by `--init` and by the test suite."""

USERS = [
    (1, "Alice Kim", "alice@example.com", 1),
    (2, "Bob Lee", "bob@example.com", 1),
    (3, "Carol Park", "carol@example.com", 1),
    (4, "Dave Choi", "dave@example.com", 0),
    (5, "Erin Jung", "erin@example.com", 1),
]

PROJECTS = [
    (1, "CORE", "Core Platform"),
    (2, "OPS", "Operations"),
]

MEMBERS = [
    (1, 1, "admin"),
    (1, 2, "member"),
    (1, 3, "viewer"),
    (1, 4, "member"),
    (2, 5, "admin"),
    (2, 1, "member"),
]

ISSUES = [
    (1, 1, "Login page shows blank screen on Safari", "Reported by two customers.", "open", 2, "2026-09-01T09:00:00Z"),
    (2, 1, "Add CSV export for reports", "", "in_progress", 1, "2026-09-03T10:30:00Z"),
    (3, 1, "Fix typo in onboarding email", "", "done", 2, "2026-09-04T08:15:00Z"),
    (4, 1, "Rate limit password reset endpoint", "", "open", 1, "2026-09-10T14:00:00Z"),
    (5, 1, "Dashboard chart overlaps legend", "Only below 900px width.", "in_progress", 2, "2026-09-12T16:45:00Z"),
    (6, 1, "Archive old audit logs", "", "open", 1, "2026-09-15T11:20:00Z"),
    (7, 1, "Upgrade SQLite driver", "", "done", 2, "2026-09-18T13:05:00Z"),
    (8, 2, "Rotate staging certificates", "", "open", 5, "2026-09-05T07:00:00Z"),
    (9, 2, "Document on-call handoff", "", "done", 5, "2026-09-20T18:00:00Z"),
]


def load(conn):
    conn.executemany("INSERT INTO users (id, name, email, active) VALUES (?, ?, ?, ?)", USERS)
    conn.executemany("INSERT INTO projects (id, key, name) VALUES (?, ?, ?)", PROJECTS)
    conn.executemany("INSERT INTO project_members (project_id, user_id, role) VALUES (?, ?, ?)", MEMBERS)
    conn.executemany(
        "INSERT INTO issues (id, project_id, title, description, status, reporter_id, created_at, updated_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [row + (row[-1],) for row in ISSUES],
    )
