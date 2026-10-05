import os
import tempfile
import threading
import unittest
from unittest import mock

from app import store, web

FIXED_NOW = "2026-10-03T08:00:00Z"


class DatabaseCase(unittest.TestCase):
    """Each test gets its own seeded SQLite file and a pinned clock."""

    def setUp(self):
        workdir = tempfile.TemporaryDirectory()
        self.addCleanup(workdir.cleanup)
        self.db_path = os.path.join(workdir.name, "signup.db")
        store.init_db(self.db_path, seed=True)
        patcher = mock.patch.dict(os.environ, {"APP_NOW": FIXED_NOW})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.conn = store.connect(self.db_path)
        self.addCleanup(self.conn.close)


class ServerCase(DatabaseCase):
    def setUp(self):
        super().setUp()
        self.server = web.create_server(self.db_path, port=0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base_url = f"http://127.0.0.1:{self.server.server_address[1]}"
