import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def connect(path):
    # One connection per request; the server is threaded and sqlite3
    # connections must not be shared across threads.
    conn = sqlite3.connect(path, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path, seed=False):
    conn = connect(path)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        if seed:
            from . import seed as seed_data

            seed_data.load(conn)
        conn.commit()
    finally:
        conn.close()
