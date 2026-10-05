"""HTTP server. Routes are registered with @route and return (status, body)."""

import argparse
import json
import mimetypes
import re
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from . import registrations, store
from .errors import InvalidInput, NotFoundError, SignupError

STATIC_ROOT = (Path(__file__).resolve().parent.parent / "static").resolve()
MAX_BODY = 32 * 1024
TOKEN_HEADER = "X-Registration-Token"

ROUTES = []


def route(method, pattern):
    def register(func):
        ROUTES.append((method, re.compile(pattern), func))
        return func

    return register


@dataclass
class RequestContext:
    conn: object
    params: dict
    body: Optional[dict]
    token: Optional[str]


@route("GET", r"/api/events")
def list_events(ctx):
    return 200, {"events": registrations.list_events(ctx.conn)}


@route("GET", r"/api/events/(?P<slug>[a-z0-9-]+)")
def get_event(ctx):
    return 200, {"event": registrations.get_event(ctx.conn, ctx.params["slug"])}


@route("GET", r"/api/events/(?P<slug>[a-z0-9-]+)/waitlist")
def get_waitlist(ctx):
    return 200, {"waitlist": registrations.waitlist(ctx.conn, ctx.params["slug"])}


@route("POST", r"/api/events/(?P<slug>[a-z0-9-]+)/registrations")
def create_registration(ctx):
    return 201, {"registration": registrations.register(ctx.conn, ctx.params["slug"], ctx.body)}


@route("GET", r"/api/registrations/(?P<registration_id>\d+)")
def get_registration(ctx):
    registration = registrations.get_registration(ctx.conn, int(ctx.params["registration_id"]), ctx.token)
    return 200, {"registration": registration}


@route("POST", r"/api/registrations/(?P<registration_id>\d+)/cancel")
def cancel_registration(ctx):
    registration = registrations.cancel(ctx.conn, int(ctx.params["registration_id"]), ctx.token)
    return 200, {"registration": registration}


class SignupHandler(BaseHTTPRequestHandler):
    server_version = "EventSignup/1.0"

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def log_message(self, fmt, *args):
        if getattr(self.server, "verbose", False):
            super().log_message(fmt, *args)

    def handle_request(self, method):
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            if method == "GET":
                self.serve_static(path)
            else:
                self.respond_error(NotFoundError("no such endpoint"))
            return
        try:
            status, body = self.dispatch(method, path)
        except SignupError as err:
            self.respond_error(err)
        except Exception:
            self.log_error("unhandled error for %s %s", method, self.path)
            self.respond(500, {"detail": "internal server error", "code": "internal_error"})
        else:
            self.respond(status, body)

    def dispatch(self, method, path):
        for route_method, pattern, func in ROUTES:
            match = pattern.fullmatch(path)
            if match and route_method == method:
                body = self.read_body() if method == "POST" else None
                conn = store.connect(self.server.db_path)
                try:
                    ctx = RequestContext(conn, match.groupdict(), body, self.headers.get(TOKEN_HEADER))
                    return func(ctx)
                finally:
                    conn.close()
        raise NotFoundError("no such endpoint")

    def read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise InvalidInput("request body too large")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            raise InvalidInput("request body must be valid JSON")
        if not isinstance(body, dict):
            raise InvalidInput("request body must be a JSON object")
        return body

    def serve_static(self, path):
        name = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (STATIC_ROOT / name).resolve()
        if STATIC_ROOT not in target.parents or not target.is_file():
            self.respond_error(NotFoundError("file not found"))
            return
        content = target.read_bytes()
        content_type = "text/javascript" if target.suffix == ".js" else mimetypes.guess_type(target.name)[0]
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type or 'application/octet-stream'}; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

    def respond_error(self, err):
        self.respond(err.http_status, {"detail": err.detail, "code": err.code})

    def respond(self, status, body):
        content = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)


def create_server(db_path, host="127.0.0.1", port=8100, verbose=False):
    server = ThreadingHTTPServer((host, port), SignupHandler)
    server.db_path = str(db_path)
    server.verbose = verbose
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m app", description="Run the event signup service.")
    parser.add_argument("--db", default="event-signup.db", help="SQLite database file")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8100)
    parser.add_argument("--init", action="store_true", help="create schema and demo data if the database is new")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if args.init and not Path(args.db).exists():
        store.init_db(args.db, seed=True)
    server = create_server(args.db, args.host, args.port, args.verbose)
    print(f"Event signup listening on http://{args.host}:{server.server_address[1]}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
