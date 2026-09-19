"""
All timestamps in AddressGuard AI are stored as timezone-aware UTC
datetimes. The frontend is responsible for converting to the viewer's
local timezone for display. This module is the single source of truth
so no other file ever calls datetime.now() or datetime.utcnow() directly.
"""
from datetime import datetime, timezone


def now_utc() -> datetime:
    """Return the current time as a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    """Serialize a timezone-aware datetime to ISO-8601 with explicit offset."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()
