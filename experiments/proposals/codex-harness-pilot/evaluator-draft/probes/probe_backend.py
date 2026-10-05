"""Pre-check that the planted backend defects reproduce.

Usage: python probe_backend.py <baselines-dir>. Not a grader.
"""
import os, sys, tempfile, threading
B = sys.argv[1]

# IT-BE: open -> done should be rejected by the documented lifecycle.
sys.path.insert(0, f"{B}/issue-tracker")
from app import db, service
d = tempfile.mkdtemp(); p = os.path.join(d, "it.db"); db.init_db(p, seed=True)
c = db.connect(p)
try:
    r = service.change_status(c, 2, "CORE", 1, {"status": "done"})
    print("IT-BE open->done:", r["status"], "(defect reproduced)" if r["status"] == "done" else "")
except Exception as e:
    print("IT-BE open->done raised", type(e).__name__)
for m in [k for k in sys.modules if k == "app" or k.startswith("app.")]:
    del sys.modules[m]
sys.path.pop(0)

# EV-BE / EV-INT
sys.path.insert(0, f"{B}/event-signup")
from app import store, registrations
d = tempfile.mkdtemp(); p = os.path.join(d, "ev.db"); store.init_db(p, seed=True)
c = store.connect(p)
c.execute("INSERT INTO events (id, slug, title, starts_at, capacity) VALUES (9, 'race', 'Race', '2026-12-01T00:00:00Z', 1)")
c.commit()

barrier = threading.Barrier(2, timeout=5)
orig = store.count_confirmed
def gated(conn, event_id):
    n = orig(conn, event_id)
    try: barrier.wait()
    except threading.BrokenBarrierError: pass
    return n
store.count_confirmed = gated
results = []
def worker(i):
    conn = store.connect(p)
    try: results.append(registrations.register(conn, "race", {"name": f"U{i}", "email": f"u{i}@example.com"})["status"])
    finally: conn.close()
ts = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
[t.start() for t in ts]; [t.join() for t in ts]
store.count_confirmed = orig
print("EV-BE capacity=1 concurrent statuses:", sorted(results), "(defect reproduced)" if results.count("confirmed") > 1 else "")

registrations.cancel(c, 3, "seed-token-3")
b = registrations.get_registration(c, 4, "seed-token-4")["status"]
print("EV-INT after cancelling confirmed, first waitlisted is:", b, "(defect reproduced)" if b == "waitlisted" else "")
