# Issue Tracker

A small issue tracker: projects, members with roles, and issues that move through a fixed lifecycle.

## Running

```sh
python -m app.server --db /tmp/issues.db --init
```

`--init` creates the schema and demo data when the database file does not exist yet. Open http://127.0.0.1:8000/ and enter a user ID (demo users 1–5) in the header.

## Users and permissions

Requests identify the acting user with the `X-User-Id` header.

| Role | Read issues | Create issues / change status |
|---|---|---|
| admin | yes | yes |
| member | yes | yes |
| viewer | yes | no |

- Users who are not members of a project get `403`.
- Deactivated users (`active = 0`) keep their history but cannot act: every request returns `401`.

Demo data: Alice (CORE admin), Bob (CORE member), Carol (CORE viewer), Dave (CORE member, deactivated), Erin (OPS admin only).

## Issue lifecycle

```
open → in_progress → done
```

Issues only move forward one step at a time; they cannot skip a step or move backwards. Requesting the status an issue already has succeeds without changing it. Invalid moves return `409`.

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/me` | Current user |
| GET | `/api/projects` | Projects the user belongs to, with role |
| GET | `/api/projects/{key}/members` | Members with role and active flag |
| GET | `/api/projects/{key}/issues?status=&sort=` | `status`: `open`, `in_progress`, `done`; `sort`: `created-desc` (default), `created-asc`, `title-asc` |
| POST | `/api/projects/{key}/issues` | `{"title", "description"}` → `201` |
| GET | `/api/projects/{key}/issues/{id}` | Single issue |
| PATCH | `/api/projects/{key}/issues/{id}/status` | `{"status"}` |

Errors: `{"error": {"code": "bad_request|unauthorized|forbidden|not_found|conflict", "message": "..."}}`.

## Frontend

- `index.html` + `list.js` — issue list with status filter and sort; the URL carries the project and the selected filters.
- `issue.html` + `issue.js` — issue detail and status change.
- `api.js` — the only module that calls `fetch`.

## Tests

```sh
python -m unittest discover -s tests -v
```
