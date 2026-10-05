"""All SQL lives here; the service layer never builds queries itself."""

SORT_SQL = {
    "created-desc": "i.created_at DESC, i.id DESC",
    "created-asc": "i.created_at ASC, i.id ASC",
    "title-asc": "i.title COLLATE NOCASE ASC, i.id ASC",
}

ISSUE_SELECT = (
    "SELECT i.id, i.project_id, i.title, i.description, i.status, i.reporter_id,"
    " r.name AS reporter_name, i.created_at, i.updated_at"
    " FROM issues i JOIN users r ON r.id = i.reporter_id"
)


def get_user(conn, user_id):
    return conn.execute("SELECT id, name, email, active FROM users WHERE id = ?", (user_id,)).fetchone()


def get_project(conn, key):
    return conn.execute("SELECT id, key, name FROM projects WHERE key = ?", (key,)).fetchone()


def list_projects_for_user(conn, user_id):
    return conn.execute(
        "SELECT p.id, p.key, p.name, m.role FROM project_members m"
        " JOIN projects p ON p.id = m.project_id"
        " WHERE m.user_id = ? ORDER BY p.key",
        (user_id,),
    ).fetchall()


def get_membership(conn, project_id, user_id):
    return conn.execute(
        "SELECT role FROM project_members WHERE project_id = ? AND user_id = ?",
        (project_id, user_id),
    ).fetchone()


def list_members(conn, project_id):
    return conn.execute(
        "SELECT u.id, u.name, u.email, u.active, m.role FROM project_members m"
        " JOIN users u ON u.id = m.user_id"
        " WHERE m.project_id = ? ORDER BY u.name COLLATE NOCASE, u.id",
        (project_id,),
    ).fetchall()


def list_issues(conn, project_id, status, sort):
    sql = ISSUE_SELECT + " WHERE i.project_id = ?"
    params = [project_id]
    if status is not None:
        sql += " AND i.status = ?"
        params.append(status)
    sql += " ORDER BY " + SORT_SQL[sort]
    return conn.execute(sql, params).fetchall()


def get_issue(conn, project_id, issue_id):
    return conn.execute(
        ISSUE_SELECT + " WHERE i.project_id = ? AND i.id = ?", (project_id, issue_id)
    ).fetchone()


def insert_issue(conn, project_id, title, description, reporter_id, now):
    cur = conn.execute(
        "INSERT INTO issues (project_id, title, description, status, reporter_id, created_at, updated_at)"
        " VALUES (?, ?, ?, 'open', ?, ?, ?)",
        (project_id, title, description, reporter_id, now, now),
    )
    return cur.lastrowid


def update_issue_status(conn, issue_id, status, now):
    conn.execute("UPDATE issues SET status = ?, updated_at = ? WHERE id = ?", (status, now, issue_id))
