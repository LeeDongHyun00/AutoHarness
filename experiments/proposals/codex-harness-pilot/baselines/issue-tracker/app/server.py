"""HTTP layer: routing, JSON encoding and error mapping. No business rules here."""

import argparse
import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import db, service
from .errors import AppError, BadRequest, NotFound

STATIC_DIR = (Path(__file__).resolve().parent.parent / "static").resolve()
MAX_BODY = 64 * 1024


def _first(query, name):
    values = query.get(name)
    return values[0] if values else None


def h_me(conn, user_id, params, query, body):
    return 200, {"user": service.user_to_dict(service.current_user(conn, user_id))}


def h_projects(conn, user_id, params, query, body):
    return 200, {"projects": service.list_my_projects(conn, user_id)}


def h_members(conn, user_id, params, query, body):
    return 200, {"members": service.list_members(conn, user_id, params["key"])}


def h_list_issues(conn, user_id, params, query, body):
    issues = service.list_issues(
        conn,
        user_id,
        params["key"],
        status=_first(query, "status") or None,
        sort=_first(query, "sort") or service.DEFAULT_SORT,
    )
    return 200, {"issues": issues}


def h_get_issue(conn, user_id, params, query, body):
    return 200, {"issue": service.get_issue(conn, user_id, params["key"], int(params["issue_id"]))}


def h_create_issue(conn, user_id, params, query, body):
    return 201, {"issue": service.create_issue(conn, user_id, params["key"], body)}


def h_change_status(conn, user_id, params, query, body):
    issue = service.change_status(conn, user_id, params["key"], int(params["issue_id"]), body)
    return 200, {"issue": issue}


ROUTES = [
    ("GET", r"/api/me", h_me),
    ("GET", r"/api/projects", h_projects),
    ("GET", r"/api/projects/(?P<key>[A-Z]+)/members", h_members),
    ("GET", r"/api/projects/(?P<key>[A-Z]+)/issues", h_list_issues),
    ("POST", r"/api/projects/(?P<key>[A-Z]+)/issues", h_create_issue),
    ("GET", r"/api/projects/(?P<key>[A-Z]+)/issues/(?P<issue_id>\d+)", h_get_issue),
    ("PATCH", r"/api/projects/(?P<key>[A-Z]+)/issues/(?P<issue_id>\d+)/status", h_change_status),
]
COMPILED_ROUTES = [(method, re.compile(pattern), handler) for method, pattern, handler in ROUTES]


class Handler(BaseHTTPRequestHandler):
    server_version = "IssueTracker/1.0"

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def log_message(self, fmt, *args):
        if getattr(self.server, "verbose", False):
            super().log_message(fmt, *args)

    def _dispatch(self, method):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            if method == "GET":
                self._serve_static(parsed.path)
            else:
                self._send_error(NotFound("no such endpoint"))
            return
        try:
            status, payload = self._handle_api(method, parsed)
        except AppError as err:
            self._send_error(err)
        except Exception:
            self.log_error("unhandled error for %s %s", method, self.path)
            self._send_json(500, {"error": {"code": "internal_error", "message": "internal server error"}})
        else:
            self._send_json(status, payload)

    def _handle_api(self, method, parsed):
        for route_method, pattern, handler in COMPILED_ROUTES:
            match = pattern.fullmatch(parsed.path)
            if match and route_method == method:
                body = self._read_json() if method in ("POST", "PATCH") else None
                conn = db.connect(self.server.db_path)
                try:
                    return handler(conn, self._user_id(), match.groupdict(), parse_qs(parsed.query), body)
                finally:
                    conn.close()
        raise NotFound("no such endpoint")

    def _user_id(self):
        raw = self.headers.get("X-User-Id")
        if raw is None or not raw.strip().isdigit():
            return None
        return int(raw)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise BadRequest("request body too large")
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            raise BadRequest("request body must be valid JSON")
        if not isinstance(body, dict):
            raise BadRequest("request body must be a JSON object")
        return body

    def _serve_static(self, path):
        relative = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (STATIC_DIR / relative).resolve()
        if STATIC_DIR not in target.parents or not target.is_file():
            self._send_error(NotFound("file not found"))
            return
        data = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix == ".js":
            content_type = "text/javascript"
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _send_error(self, err):
        self._send_json(err.status, {"error": {"code": err.code, "message": err.message}})

    def _send_json(self, status, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def make_server(db_path, host="127.0.0.1", port=8000, verbose=False):
    server = ThreadingHTTPServer((host, port), Handler)
    server.db_path = str(db_path)
    server.verbose = verbose
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the issue tracker.")
    parser.add_argument("--db", default="issue-tracker.db", help="SQLite database file")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--init", action="store_true", help="create schema and demo data if the database is new")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if args.init and not Path(args.db).exists():
        db.init_db(args.db, seed=True)
    server = make_server(args.db, args.host, args.port, args.verbose)
    print(f"Serving on http://{args.host}:{server.server_address[1]}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
