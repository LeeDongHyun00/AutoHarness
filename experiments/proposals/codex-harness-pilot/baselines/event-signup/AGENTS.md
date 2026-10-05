# Notes for coding agents

Event signup service: events with a fixed capacity, confirmed seats and a waitlist.

- Standard library only (Python 3.11+, SQLite). No npm, no bundler; the browser code in `static/` is plain ES modules.
- `app/store.py` holds every SQL statement and never commits. `app/registrations.py` owns the rules and decides when to commit or roll back. `app/web.py` only parses requests and formats responses.
- Error responses are `{"detail": "...", "code": "..."}` built from the classes in `app/errors.py`.
- Run `python -m unittest discover -s tests -v` before finishing. Start the app with `python -m app --db /tmp/signup.db --init` (port 8100).
