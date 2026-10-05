"""Single source of "now" so tests and fixtures can pin time with APP_NOW."""

import os
from datetime import datetime, timezone


def now() -> str:
    fixed = os.environ.get("APP_NOW")
    if fixed:
        return fixed
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
