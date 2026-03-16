from __future__ import annotations

from datetime import UTC, datetime

import pytest

from libraries.time import parse_datetime_value, resolve_effective_time


def test_parse_datetime_value_normalizes_offset_input_to_utc() -> None:
    parsed = parse_datetime_value("2026-05-08T18:35:00-04:00")

    assert parsed == datetime(2026, 5, 8, 22, 35, tzinfo=UTC)


def test_parse_datetime_value_rejects_naive_strings() -> None:
    with pytest.raises(ValueError):
        parse_datetime_value("2026-05-08T18:35:00")


def test_resolve_effective_time_prefers_explicit_then_published_then_ingestion() -> None:
    ingestion_time = datetime(2026, 5, 8, 23, 15, tzinfo=UTC)
    published_at = datetime(2026, 5, 8, 22, 35, tzinfo=UTC)
    explicit_effective_at = datetime(2026, 5, 8, 20, 30, tzinfo=UTC)

    assert (
        resolve_effective_time(
            explicit_effective_at=explicit_effective_at,
            published_at=published_at,
            ingestion_time=ingestion_time,
        )
        == explicit_effective_at
    )
    assert (
        resolve_effective_time(
            explicit_effective_at=None,
            published_at=published_at,
            ingestion_time=ingestion_time,
        )
        == published_at
    )
    assert (
        resolve_effective_time(
            explicit_effective_at=None,
            published_at=None,
            ingestion_time=ingestion_time,
        )
        == ingestion_time
    )
