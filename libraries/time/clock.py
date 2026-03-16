from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""

    return datetime.now(tz=UTC)


def ensure_utc(value: datetime) -> datetime:
    """Normalize a datetime into timezone-aware UTC."""

    if value.tzinfo is None:
        raise ValueError("Naive datetimes are not allowed; provide an explicit timezone.")
    return value.astimezone(UTC)


def isoformat_z(value: datetime) -> str:
    """Render a UTC timestamp using a trailing Z suffix."""

    return ensure_utc(value).isoformat().replace("+00:00", "Z")
