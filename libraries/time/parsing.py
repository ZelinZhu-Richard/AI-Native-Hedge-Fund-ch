from __future__ import annotations

from datetime import date, datetime

from libraries.time.clock import ensure_utc


def parse_datetime_value(value: str | datetime) -> datetime:
    """Parse a datetime value and normalize it to UTC."""

    if isinstance(value, datetime):
        return ensure_utc(value)
    normalized_value = value.strip()
    if normalized_value.endswith("Z"):
        normalized_value = normalized_value[:-1] + "+00:00"
    return ensure_utc(datetime.fromisoformat(normalized_value))


def parse_date_value(value: str | date) -> date:
    """Parse a date value from an ISO string or return it unchanged."""

    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return ensure_utc(value).date()
    return date.fromisoformat(value.strip())


def resolve_effective_time(
    *, explicit_effective_at: datetime | None, published_at: datetime | None, ingestion_time: datetime
) -> datetime:
    """Resolve the effective time for a normalized artifact."""

    if explicit_effective_at is not None:
        return ensure_utc(explicit_effective_at)
    if published_at is not None:
        return ensure_utc(published_at)
    return ensure_utc(ingestion_time)
