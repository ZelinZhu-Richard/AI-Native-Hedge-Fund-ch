from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from libraries.schemas.timing import (
    MarketCalendarEvent,
    MarketCalendarEventKind,
    MarketName,
    MarketSession,
    MarketSessionKind,
)
from libraries.time import ensure_utc
from services.timing.rules import US_EQUITIES_TIMEZONE

_PRE_MARKET_OPEN = time(hour=4, minute=0)
_REGULAR_OPEN = time(hour=9, minute=30)
_REGULAR_CLOSE = time(hour=16, minute=0)
_AFTER_HOURS_CLOSE = time(hour=20, minute=0)


@dataclass(frozen=True)
class SessionBounds:
    """Local session bounds for one US equities trading day."""

    open_at: datetime
    close_at: datetime


def classify_us_equities_session(
    *,
    timestamp: datetime,
    overrides: list[MarketCalendarEvent] | None = None,
) -> MarketSession:
    """Classify one UTC timestamp into a coarse US equities session bucket."""

    local_timezone = ZoneInfo(US_EQUITIES_TIMEZONE)
    local_timestamp = ensure_utc(timestamp).astimezone(local_timezone)
    session_date = local_timestamp.date()
    override = _override_for_date(session_date=session_date, overrides=overrides or [])
    if local_timestamp.weekday() >= 5:
        return MarketSession(
            market=MarketName.US_EQUITIES,
            session_date=session_date,
            timezone=US_EQUITIES_TIMEZONE,
            session_kind=MarketSessionKind.CLOSED,
            open_at=None,
            close_at=None,
        )
    if override is not None and override.event_kind is MarketCalendarEventKind.HOLIDAY:
        return MarketSession(
            market=MarketName.US_EQUITIES,
            session_date=session_date,
            timezone=US_EQUITIES_TIMEZONE,
            session_kind=MarketSessionKind.CLOSED,
            open_at=override.open_at,
            close_at=override.close_at,
        )
    if override is not None and override.event_kind is MarketCalendarEventKind.SESSION_OVERRIDE:
        return MarketSession(
            market=MarketName.US_EQUITIES,
            session_date=session_date,
            timezone=US_EQUITIES_TIMEZONE,
            session_kind=override.session_kind or MarketSessionKind.CLOSED,
            open_at=override.open_at,
            close_at=override.close_at,
        )

    bounds = regular_session_bounds(session_date=session_date, override=override)
    pre_market_open = datetime.combine(
        session_date,
        _PRE_MARKET_OPEN,
        tzinfo=local_timezone,
    )
    after_hours_close = datetime.combine(
        session_date,
        _AFTER_HOURS_CLOSE,
        tzinfo=local_timezone,
    )
    if local_timestamp < pre_market_open:
        session_kind = MarketSessionKind.CLOSED
    elif local_timestamp < bounds.open_at:
        session_kind = MarketSessionKind.PRE_MARKET
    elif local_timestamp <= bounds.close_at:
        session_kind = MarketSessionKind.REGULAR
    elif local_timestamp <= after_hours_close:
        session_kind = MarketSessionKind.AFTER_HOURS
    else:
        session_kind = MarketSessionKind.CLOSED
    return MarketSession(
        market=MarketName.US_EQUITIES,
        session_date=session_date,
        timezone=US_EQUITIES_TIMEZONE,
        session_kind=session_kind,
        open_at=bounds.open_at.astimezone(UTC),
        close_at=bounds.close_at.astimezone(UTC),
    )


def next_us_equities_open(
    *,
    timestamp: datetime,
    overrides: list[MarketCalendarEvent] | None = None,
) -> datetime:
    """Return the next regular market open at or after the provided timestamp."""

    local_timezone = ZoneInfo(US_EQUITIES_TIMEZONE)
    local_timestamp = ensure_utc(timestamp).astimezone(local_timezone)
    candidate_date = local_timestamp.date()
    while True:
        if candidate_date.weekday() >= 5:
            candidate_date += timedelta(days=1)
            continue
        override = _override_for_date(session_date=candidate_date, overrides=overrides or [])
        if override is not None and override.event_kind is MarketCalendarEventKind.HOLIDAY:
            candidate_date += timedelta(days=1)
            continue
        bounds = regular_session_bounds(session_date=candidate_date, override=override)
        if candidate_date > local_timestamp.date() or local_timestamp <= bounds.open_at:
            return bounds.open_at.astimezone(UTC)
        candidate_date += timedelta(days=1)


def regular_session_bounds(
    *,
    session_date: date,
    override: MarketCalendarEvent | None = None,
) -> SessionBounds:
    """Return the local regular-session open and close bounds for one date."""

    local_timezone = ZoneInfo(US_EQUITIES_TIMEZONE)
    open_time = _REGULAR_OPEN
    close_time = _REGULAR_CLOSE
    if override is not None:
        if override.event_kind is MarketCalendarEventKind.LATE_OPEN and override.open_at is not None:
            open_time = ensure_utc(override.open_at).astimezone(local_timezone).time()
        if override.event_kind is MarketCalendarEventKind.EARLY_CLOSE and override.close_at is not None:
            close_time = ensure_utc(override.close_at).astimezone(local_timezone).time()
    return SessionBounds(
        open_at=datetime.combine(session_date, open_time, tzinfo=local_timezone),
        close_at=datetime.combine(session_date, close_time, tzinfo=local_timezone),
    )


def _override_for_date(
    *,
    session_date: date,
    overrides: list[MarketCalendarEvent],
) -> MarketCalendarEvent | None:
    """Return one explicit override for the requested date when present."""

    for override in overrides:
        if override.session_date == session_date and override.market is MarketName.US_EQUITIES:
            return override
    return None


__all__ = [
    "classify_us_equities_session",
    "next_us_equities_open",
    "regular_session_bounds",
]
