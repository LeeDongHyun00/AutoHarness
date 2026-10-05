"""Shared helpers for pilot checks.

This file is copied unchanged into each Codex workspace as part of the public
check bundle, so it must never reference private checks or reference patches.
Checks only observe external behaviour (HTTP, SQLite rows, the browser); they
never import the project's modules, so any reasonable implementation passes.
"""

import argparse
import asyncio
import json
import os
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

PROJECTS = {
    "issue-tracker": {"module": "app.server"},
    "event-signup": {"module": "app"},
}
FIXED_NOW = "2026-10-06T09:00:00Z"
STARTUP_TIMEOUT = 15
CHECK_TIMEOUT = 120
UI_TIMEOUT_MS = 10_000

# Loaded through PYTHONPATH by the app process when a check asks for a SQL
# delay. Every sqlite3 connection gets a trace callback that sleeps before
# statements touching `registrations`, which widens the window between reads
# and writes so concurrent requests really overlap instead of relying on luck.
SITECUSTOMIZE = '''
import os, sqlite3, threading, time
_delay = float(os.environ.get("PILOT_SQL_DELAY_MS", "0")) / 1000
_log = os.environ.get("PILOT_SQL_LOG")
_lock = threading.Lock()
_connect = sqlite3.connect

def _trace(sql):
    if _log:
        with _lock, open(_log, "a", encoding="utf-8") as fh:
            fh.write("%.6f\\t%d\\t%r\\n" % (time.monotonic(), threading.get_ident(), sql))
    if _delay and "registrations" in sql.lower():
        time.sleep(_delay)

def connect(*args, **kwargs):
    conn = _connect(*args, **kwargs)
    conn.set_trace_callback(_trace)
    return conn

sqlite3.connect = connect
'''


class StartupFailure(Exception):
    """The app did not come up; reported separately from assertion failures."""


class InfraFailure(Exception):
    """The check environment is missing something (e.g. Playwright)."""


def expect(condition, message):
    if not condition:
        raise AssertionError(message)


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


_RUNNING = []


class App:
    """One app process on a fresh seeded database."""

    def __init__(self, project, root, now=FIXED_NOW, sql_delay_ms=0):
        self.project = project
        self.root = Path(root)
        self.now = now
        self.sql_delay_ms = sql_delay_ms
        self.workdir = Path(tempfile.mkdtemp(prefix="pilot-check-"))
        self.db_path = self.workdir / "app.db"
        self.sql_log = self.workdir / "sql.log"
        self.port = None
        self.proc = None

    @property
    def base_url(self):
        return f"http://127.0.0.1:{self.port}"

    def start(self):
        hook_dir = self.workdir / "hook"
        hook_dir.mkdir(exist_ok=True)
        (hook_dir / "sitecustomize.py").write_text(SITECUSTOMIZE, encoding="utf-8")
        env = dict(os.environ)
        env.update(
            APP_NOW=self.now,
            PYTHONPATH=os.pathsep.join([str(hook_dir), str(self.root)]),
            PYTHONDONTWRITEBYTECODE="1",
            PILOT_SQL_DELAY_MS=str(self.sql_delay_ms),
            PILOT_SQL_LOG=str(self.sql_log),
        )
        self.port = _free_port()
        log = open(self.workdir / "server.log", "ab")
        cmd = [sys.executable, "-m", PROJECTS[self.project]["module"], "--db", str(self.db_path),
               "--init", "--port", str(self.port)]
        self.proc = subprocess.Popen(cmd, cwd=self.root, env=env, stdout=log, stderr=subprocess.STDOUT)
        _RUNNING.append(self)
        deadline = time.monotonic() + STARTUP_TIMEOUT
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise StartupFailure(f"app exited with {self.proc.returncode}: {self.log_tail()}")
            try:
                with urllib.request.urlopen(self.base_url + "/", timeout=1):
                    return self
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(0.1)
        raise StartupFailure(f"app did not answer within {STARTUP_TIMEOUT}s: {self.log_tail()}")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(5)
        if self in _RUNNING:
            _RUNNING.remove(self)

    def restart(self):
        """Stop and start on the same database file (data must survive)."""
        self.stop()
        return self.start()

    def log_tail(self, lines=15):
        try:
            text = (self.workdir / "server.log").read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return ""
        return "\n".join(text.splitlines()[-lines:])

    def request(self, method, path, body=None, headers=None, timeout=10):
        data = None
        all_headers = dict(headers or {})
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            all_headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base_url + path, data=data, method=method, headers=all_headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, _json_or_text(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, _json_or_text(err.read())

    def sql(self, query, params=()):
        conn = sqlite3.connect(self.db_path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(query, params).fetchall()
            conn.commit()
            return rows
        finally:
            conn.close()

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()


def _json_or_text(raw):
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return {"_raw": raw.decode("utf-8", errors="replace")}


def concurrent_requests(app, calls, timeout=10):
    """Fire requests at the same instant from separate threads.

    Returns (results, overlapped). `overlapped` is True only if every request
    was in flight at the same time, i.e. all started before any finished.
    """
    barrier = threading.Barrier(len(calls))
    results = [None] * len(calls)
    windows = [None] * len(calls)

    def worker(index, call):
        barrier.wait(timeout)
        start = time.monotonic()
        results[index] = app.request(*call, timeout=timeout)
        windows[index] = (start, time.monotonic())

    threads = [threading.Thread(target=worker, args=(i, c)) for i, c in enumerate(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout + 5)
    if any(w is None for w in windows):
        raise AssertionError("a concurrent request did not complete")
    overlapped = max(w[0] for w in windows) < min(w[1] for w in windows)
    return results, overlapped


def run_in_browser(scenario):
    """Run `async scenario(page)` in a fresh headless Chromium page."""
    try:
        from playwright.async_api import async_playwright
    except ImportError as err:
        raise InfraFailure("playwright is not installed") from err

    async def main():
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(executable_path=os.environ.get("PW_CHROMIUM") or None)
            try:
                page = await (await browser.new_context()).new_page()
                page.set_default_timeout(UI_TIMEOUT_MS)
                return await scenario(page)
            finally:
                await browser.close()

    return asyncio.run(main())


class CheckList:
    def __init__(self, project, task):
        self.project = project
        self.task = task
        self.items = []

    def add(self, requirement, title):
        def register(func):
            self.items.append({"requirement": requirement, "title": title, "func": func})
            return func

        return register


def run_one(item, project, root):
    outcome = {}

    def target():
        try:
            item["func"](project, root)
            outcome["status"] = "pass"
        except AssertionError as err:
            outcome.update(status="fail", detail=str(err) or "assertion failed")
        except StartupFailure as err:
            outcome.update(status="startup_failure", detail=str(err))
        except InfraFailure as err:
            outcome.update(status="infra_failure", detail=str(err))
        except Exception as err:
            # Playwright timeouts land here; they are still behaviour failures.
            name = type(err).__name__
            status = "fail" if "Timeout" in name else "error"
            outcome.update(status=status, detail=f"{name}: {err}\n{traceback.format_exc(limit=3)}")

    started = time.monotonic()
    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(CHECK_TIMEOUT)
    if thread.is_alive():
        outcome = {"status": "timeout", "detail": f"exceeded {CHECK_TIMEOUT}s"}
    for app in list(_RUNNING):
        app.stop()
    return {
        "requirement": item["requirement"],
        "title": item["title"],
        "seconds": round(time.monotonic() - started, 2),
        **outcome,
    }


def run_checklist(checklist, root, visibility):
    return [dict(run_one(item, checklist.project, root), visibility=visibility) for item in checklist.items]


def print_report(results):
    for r in results:
        mark = "PASS" if r["status"] == "pass" else r["status"].upper()
        print(f"[{mark}] {r['requirement']} {r['title']}")
        if r["status"] != "pass":
            print("    " + (r.get("detail") or "").strip().replace("\n", "\n    "))
    passed = sum(r["status"] == "pass" for r in results)
    print(f"{passed}/{len(results)} checks passed")


def public_main(checklist):
    """Entry point used by tools/check_public.py inside a workspace."""
    parser = argparse.ArgumentParser(description=f"Public checks for task {checklist.task}")
    parser.add_argument("--task", default=checklist.task)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args()
    if args.task != checklist.task:
        parser.error(f"this workspace only has checks for {checklist.task}")
    results = run_checklist(checklist, args.root, "public")
    print_report(results)
    return 0 if all(r["status"] == "pass" for r in results) else 1
