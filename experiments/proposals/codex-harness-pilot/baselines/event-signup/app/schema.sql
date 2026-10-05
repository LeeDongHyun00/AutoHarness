CREATE TABLE events (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  starts_at TEXT NOT NULL,
  capacity INTEGER NOT NULL CHECK (capacity >= 0)
);

CREATE TABLE registrations (
  id INTEGER PRIMARY KEY,
  event_id INTEGER NOT NULL REFERENCES events(id),
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  affiliation TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK (status IN ('confirmed', 'waitlisted', 'cancelled')),
  token TEXT NOT NULL,
  created_at TEXT NOT NULL,
  waitlisted_at TEXT,
  confirmed_at TEXT,
  cancelled_at TEXT
);

-- One active (confirmed or waitlisted) registration per email per event.
CREATE UNIQUE INDEX uniq_active_registration
  ON registrations(event_id, email) WHERE status != 'cancelled';

CREATE INDEX idx_registrations_queue
  ON registrations(event_id, status, waitlisted_at, id);
