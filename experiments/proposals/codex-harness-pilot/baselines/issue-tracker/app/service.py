"""Business rules and permission checks.

Every public function takes an open connection and the acting user id (from the
X-User-Id header, or None when it is missing) and returns plain dicts that
server.py serialises as-is.
"""

from . import clock, repository
from .errors import BadRequest, Conflict, Forbidden, NotFound, Unauthorized

STATUSES = ("open", "in_progress", "done")
SORTS = tuple(repository.SORT_SQL)
DEFAULT_SORT = "created-desc"

# Lifecycle documented in README: issues only move forward.
ALLOWED_TRANSITIONS = {
    "open": {"in_progress", "done"},
    "in_progress": {"done"},
    "done": set(),
}

WRITE_ROLES = {"admin", "member"}
MAX_TITLE = 200
MAX_DESCRIPTION = 5000


def user_to_dict(row):
    return {"id": row["id"], "name": row["name"], "email": row["email"], "active": bool(row["active"])}


def issue_to_dict(row):
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "status": row["status"],
        "reporter": {"id": row["reporter_id"], "name": row["reporter_name"]},
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def current_user(conn, user_id):
    if user_id is None:
        raise Unauthorized("X-User-Id header is required")
    user = repository.get_user(conn, user_id)
    # Deactivated accounts keep their history but can no longer act.
    if user is None or not user["active"]:
        raise Unauthorized("unknown or inactive user")
    return user


def _project_access(conn, user_id, project_key, write=False):
    user = current_user(conn, user_id)
    project = repository.get_project(conn, project_key)
    if project is None:
        raise NotFound("project not found")
    membership = repository.get_membership(conn, project["id"], user["id"])
    if membership is None:
        raise Forbidden("you are not a member of this project")
    if write and membership["role"] not in WRITE_ROLES:
        raise Forbidden("your role cannot modify issues")
    return user, project


def _get_issue_or_404(conn, project, issue_id):
    issue = repository.get_issue(conn, project["id"], issue_id)
    if issue is None:
        raise NotFound("issue not found")
    return issue


def list_my_projects(conn, user_id):
    user = current_user(conn, user_id)
    return [
        {"key": row["key"], "name": row["name"], "role": row["role"]}
        for row in repository.list_projects_for_user(conn, user["id"])
    ]


def list_members(conn, user_id, project_key):
    _, project = _project_access(conn, user_id, project_key)
    return [
        dict(user_to_dict(row), role=row["role"]) for row in repository.list_members(conn, project["id"])
    ]


def list_issues(conn, user_id, project_key, status=None, sort=DEFAULT_SORT):
    _, project = _project_access(conn, user_id, project_key)
    if status is not None and status not in STATUSES:
        raise BadRequest(f"unknown status: {status}")
    if sort not in SORTS:
        raise BadRequest(f"unknown sort: {sort}")
    return [issue_to_dict(row) for row in repository.list_issues(conn, project["id"], status, sort)]


def get_issue(conn, user_id, project_key, issue_id):
    _, project = _project_access(conn, user_id, project_key)
    return issue_to_dict(_get_issue_or_404(conn, project, issue_id))


def create_issue(conn, user_id, project_key, payload):
    user, project = _project_access(conn, user_id, project_key, write=True)
    title = payload.get("title")
    description = payload.get("description", "")
    if not isinstance(title, str) or not title.strip():
        raise BadRequest("title is required")
    if len(title.strip()) > MAX_TITLE:
        raise BadRequest(f"title must be at most {MAX_TITLE} characters")
    if not isinstance(description, str) or len(description) > MAX_DESCRIPTION:
        raise BadRequest(f"description must be a string of at most {MAX_DESCRIPTION} characters")
    issue_id = repository.insert_issue(conn, project["id"], title.strip(), description, user["id"], clock.now())
    conn.commit()
    return issue_to_dict(repository.get_issue(conn, project["id"], issue_id))


def change_status(conn, user_id, project_key, issue_id, payload):
    _, project = _project_access(conn, user_id, project_key, write=True)
    status = payload.get("status")
    if status not in STATUSES:
        raise BadRequest(f"unknown status: {status}")
    issue = _get_issue_or_404(conn, project, issue_id)
    if issue["status"] == status:
        return issue_to_dict(issue)
    if status not in ALLOWED_TRANSITIONS[issue["status"]]:
        raise Conflict(f"cannot move an issue from {issue['status']} to {status}")
    repository.update_issue_status(conn, issue["id"], status, clock.now())
    conn.commit()
    return issue_to_dict(repository.get_issue(conn, project["id"], issue["id"]))
