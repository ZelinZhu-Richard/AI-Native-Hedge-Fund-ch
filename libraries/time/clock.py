from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Protocol for explicit time sources used by services and tests."""

    def now(self) -> datetime:
        """Return the current timezone-aware UTC timestamp."""


@dataclass(frozen=True)
class SystemClock:
    """Clock backed by the system wall clock."""

    def now(self) -> datetime:
        """Return the current timezone-aware UTC timestamp."""

        return utc_now()


@dataclass(frozen=True)
class FrozenClock:
    """Deterministic clock for tests and replay-oriented workflows."""

    fixed_time: datetime

    def now(self) -> datetime:
        """Return the fixed timezone-aware UTC timestamp."""

        return ensure_utc(self.fixed_time)


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
