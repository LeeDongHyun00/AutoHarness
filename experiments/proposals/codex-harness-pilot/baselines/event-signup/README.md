# Event Signup

Sign up for community events. Each event has a fixed capacity; once it is full, new signups join a waitlist.

## Quick start

```sh
python -m app --db /tmp/signup.db --init
```

Then open http://127.0.0.1:8100/. `--init` creates the schema and demo events when the database file is new.

## How signups work

- A signup needs a name and a valid email; affiliation and notes are optional. Emails are stored lower-case.
- While confirmed signups are below capacity, a new signup is `confirmed`. Otherwise it is `waitlisted`.
- The waitlist is ordered by the time a person joined it (`waitlisted_at`), then by registration id.
- An email can have only one active (`confirmed` or `waitlisted`) registration per event; a second attempt returns `409 already_registered`. After cancelling, the same email may sign up again.
- Signing up returns a `token`. It is shown only once and is required (header `X-Registration-Token`) to view or cancel the registration. A wrong token and an unknown id both return `404 registration_not_found`.
- Cancelling sets the status to `cancelled`. Cancelling an already cancelled registration succeeds without changes.

Demo data: `spring-meetup` (capacity 3, 2 confirmed), `rust-workshop` (capacity 1, 1 confirmed, 2 waitlisted), `design-clinic` (capacity 2, empty). Seed tokens are `seed-token-<id>`.

## API

| Method | Path | Body / header | Result |
|---|---|---|---|
| GET | `/api/events` | | events with `seats_left`, `waitlist_count` |
| GET | `/api/events/{slug}` | | one event |
| GET | `/api/events/{slug}/waitlist` | | positions with masked names |
| POST | `/api/events/{slug}/registrations` | `{"name", "email", "affiliation", "note"}` | `201` registration incl. `token` |
| GET | `/api/registrations/{id}` | `X-Registration-Token` | registration incl. `waitlist_position` |
| POST | `/api/registrations/{id}/cancel` | `X-Registration-Token` | updated registration |

Errors: `{"detail": "...", "code": "invalid_input|event_not_found|registration_not_found|already_registered|..."}`.

## Pages

- `/` — event list
- `/event.html?slug=...` — event details and signup form
- `/registration.html?id=...&token=...` — registration status and cancellation

## Tests

```sh
python -m unittest discover -s tests -v
```
