import os
import tempfile
import threading
import unittest

from app import db, server


class SeededDbTestCase(unittest.TestCase):
    """Fresh seeded database per test with time pinned through APP_NOW."""

    now = "2026-10-01T12:00:00Z"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db_path = os.path.join(tmp.name, "test.db")
        db.init_db(self.db_path, seed=True)
        previous = os.environ.get("APP_NOW")
        os.environ["APP_NOW"] = self.now
        self.addCleanup(self._restore_now, previous)
        self.conn = db.connect(self.db_path)
        self.addCleanup(self.conn.close)

    @staticmethod
    def _restore_now(previous):
        if previous is None:
            os.environ.pop("APP_NOW", None)
        else:
            os.environ["APP_NOW"] = previous


class LiveServerTestCase(SeededDbTestCase):
    def setUp(self):
        super().setUp()
        self.server = server.make_server(self.db_path, port=0)
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
