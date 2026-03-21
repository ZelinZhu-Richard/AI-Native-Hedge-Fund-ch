from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from libraries.schemas import (
    AvailabilityBasis,
    AvailabilityWindow,
    DataAvailabilityRule,
    DataAvailabilityTarget,
    DecisionCutoff,
    MarketCalendarEvent,
    MarketCalendarEventKind,
    MarketName,
    MarketSession,
    MarketSessionKind,
    ProvenanceRecord,
    PublicationTiming,
    SameDayAvailabilityPolicy,
    TimingAnomaly,
    TimingAnomalyKind,
)

FIXED_NOW = datetime(2026, 3, 20, 20, 0, tzinfo=UTC)


def test_publication_timing_rejects_invalid_timezone() -> None:
    with pytest.raises(ValueError, match="source_timezone"):
        PublicationTiming(
            event_time=None,
            publication_time=FIXED_NOW,
            internal_available_at=FIXED_NOW,
            source_timezone="Not/A_Real_Timezone",
            normalized_timezone="UTC",
        )


def test_publication_timing_rejects_internal_availability_before_publication() -> None:
    with pytest.raises(ValueError, match="internal_available_at"):
        PublicationTiming(
            event_time=None,
            publication_time=FIXED_NOW,
            internal_available_at=FIXED_NOW.replace(hour=19),
            source_timezone="UTC",
            normalized_timezone="UTC",
        )


def test_availability_window_requires_ordered_bounds() -> None:
    with pytest.raises(ValueError, match="available_until"):
        AvailabilityWindow(
            available_from=FIXED_NOW,
            available_until=FIXED_NOW.replace(hour=19),
            availability_basis=AvailabilityBasis.PUBLICATION_RULE,
            publication_timing=None,
            market_session=None,
            rule_name="test_rule",
        )


def test_market_session_and_calendar_event_validate_timezones() -> None:
    session = MarketSession(
        market=MarketName.US_EQUITIES,
        session_date=date(2026, 3, 20),
        timezone="America/New_York",
        session_kind=MarketSessionKind.REGULAR,
        open_at=datetime(2026, 3, 20, 13, 30, tzinfo=UTC),
        close_at=datetime(2026, 3, 20, 20, 0, tzinfo=UTC),
    )
    assert session.session_kind is MarketSessionKind.REGULAR

    event = MarketCalendarEvent(
        event_kind=MarketCalendarEventKind.EARLY_CLOSE,
        market=MarketName.US_EQUITIES,
        session_date=date(2026, 11, 27),
        timezone="America/New_York",
        open_at=datetime(2026, 11, 27, 14, 30, tzinfo=UTC),
        close_at=datetime(2026, 11, 27, 18, 0, tzinfo=UTC),
    )
    assert event.event_kind is MarketCalendarEventKind.EARLY_CLOSE


def test_data_availability_rule_requires_valid_timezone() -> None:
    with pytest.raises(ValueError, match="timezone"):
        DataAvailabilityRule(
            rule_name="bad_rule",
            applies_to=DataAvailabilityTarget.DOCUMENT,
            market=MarketName.US_EQUITIES,
            timezone="Bad/Timezone",
            requires_publication_time=True,
            same_day_policy=SameDayAvailabilityPolicy.PRE_OPEN_SAME_DAY_ELSE_NEXT_SESSION,
        )


def test_decision_cutoff_requires_eligible_information_time_not_after_decision() -> None:
    with pytest.raises(ValueError, match="eligible_information_time"):
        DecisionCutoff(
            decision_cutoff_id="dcut_test",
            market=MarketName.US_EQUITIES,
            timezone="America/New_York",
            decision_time=FIXED_NOW,
            decision_session_kind=MarketSessionKind.REGULAR,
            eligible_information_time=FIXED_NOW.replace(hour=21),
            rule_name="daily_price_bar_close",
            rationale="test",
            provenance=ProvenanceRecord(processing_time=FIXED_NOW),
        )


def test_timing_anomaly_requires_target_and_message() -> None:
    anomaly = TimingAnomaly(
        timing_anomaly_id="tanom_test",
        target_type="signal",
        target_id="sig_test",
        anomaly_kind=TimingAnomalyKind.MISSING_UPSTREAM_AVAILABILITY,
        blocking=False,
        message="fallback used",
        provenance=ProvenanceRecord(processing_time=FIXED_NOW),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    assert anomaly.target_id == "sig_test"
