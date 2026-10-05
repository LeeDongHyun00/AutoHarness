# AGENTS.md

Issue tracker for small teams. Python standard library only — do not add third-party packages.

## Layout

- `app/server.py` — HTTP routing and JSON responses. Keep business rules out of it.
- `app/service.py` — business rules and permission checks.
- `app/repository.py` — the only module that contains SQL.
- `app/schema.sql`, `app/seed.py` — schema and demo data (also used by tests).
- `static/` — vanilla JavaScript ES modules, no build step.

## Commands

- Tests: `python -m unittest discover -s tests -v`
- Run locally: `python -m app.server --db /tmp/issues.db --init`, then open http://127.0.0.1:8000/

## Conventions

- API errors use `{"error": {"code": ..., "message": ...}}`. Raise the matching class from `app/errors.py`; never build error responses by hand.
- Timestamps are UTC ISO-8601 strings from `app.clock.now()`.
