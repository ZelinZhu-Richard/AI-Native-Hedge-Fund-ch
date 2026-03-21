from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, model_validator

from libraries.schemas.base import ProvenanceRecord, StrictModel, TimestampedModel


def _assert_valid_timezone(value: str, *, field_name: str) -> None:
    """Require timezone fields to carry a valid IANA timezone name."""

    if not value:
        raise ValueError(f"{field_name} must be non-empty.")
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"{field_name} must be a valid IANA timezone name.") from exc


class MarketName(StrEnum):
    """Market scopes supported by the first timing layer."""

    US_EQUITIES = "us_equities"


class MarketSessionKind(StrEnum):
    """Coarse market session buckets for deterministic timing rules."""

    PRE_MARKET = "pre_market"
    REGULAR = "regular"
    AFTER_HOURS = "after_hours"
    CLOSED = "closed"


class MarketCalendarEventKind(StrEnum):
    """Explicit manual calendar override event kinds."""

    HOLIDAY = "holiday"
    EARLY_CLOSE = "early_close"
    LATE_OPEN = "late_open"
    SESSION_OVERRIDE = "session_override"


class AvailabilityBasis(StrEnum):
    """Basis used to justify when information becomes available downstream."""

    PUBLICATION_RULE = "publication_rule"
    DERIVED_FROM_INPUTS = "derived_from_inputs"
    MARKET_DATA_CLOSE = "market_data_close"
    COMPATIBILITY_FALLBACK = "compatibility_fallback"


class SameDayAvailabilityPolicy(StrEnum):
    """High-level availability policy used by a timing rule."""

    PRE_OPEN_SAME_DAY_ELSE_NEXT_SESSION = "pre_open_same_day_else_next_session"
    MAX_INPUT_AVAILABILITY = "max_input_availability"
    BAR_CLOSE = "bar_close"


class DataAvailabilityTarget(StrEnum):
    """Artifact families governed by timing rules."""

    DOCUMENT = "document"
    FEATURE = "feature"
    SIGNAL = "signal"
    PRICE_BAR = "price_bar"


class TimingAnomalyKind(StrEnum):
    """Structured timing anomalies that should remain inspectable."""

    MISSING_PUBLICATION_TIMESTAMP = "missing_publication_timestamp"
    INVALID_TIMEZONE = "invalid_timezone"
    PUBLICATION_AFTER_INTERNAL_AVAILABILITY = "publication_after_internal_availability"
    EVENT_AFTER_PUBLICATION = "event_after_publication"
    RETRIEVED_BEFORE_PUBLICATION = "retrieved_before_publication"
    INGESTED_BEFORE_PUBLICATION = "ingested_before_publication"
    DECISION_BEFORE_AVAILABILITY = "decision_before_availability"
    IMPOSSIBLE_MARKET_SESSION = "impossible_market_session"
    MISSING_UPSTREAM_AVAILABILITY = "missing_upstream_availability"
    UPSTREAM_AVAILABILITY_AFTER_DERIVED_ARTIFACT = "upstream_availability_after_derived_artifact"


class PublicationTiming(StrictModel):
    """Normalized publication and internal availability timing for one artifact."""

    event_time: datetime | None = Field(
        default=None,
        description="UTC time when the underlying event happened when known.",
    )
    publication_time: datetime = Field(description="UTC time when the source made the item visible.")
    internal_available_at: datetime = Field(
        description="UTC time when the platform should treat the item as usable."
    )
    source_timezone: str = Field(description="Source timezone assumption for the original timestamp.")
    normalized_timezone: str = Field(
        default="UTC",
        description="Normalized timezone used by the platform after conversion.",
    )
    rule_name: str | None = Field(
        default=None,
        description="Timing rule used to resolve internal availability when applicable.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Explicit notes about assumptions or conservatism in the timing record.",
    )

    @model_validator(mode="after")
    def validate_publication_timing(self) -> PublicationTiming:
        """Require valid timezones and direct ordering consistency."""

        _assert_valid_timezone(self.source_timezone, field_name="source_timezone")
        _assert_valid_timezone(self.normalized_timezone, field_name="normalized_timezone")
        if self.internal_available_at < self.publication_time:
            raise ValueError(
                "internal_available_at must be greater than or equal to publication_time."
            )
        return self


class MarketSession(StrictModel):
    """Resolved market session classification for one timestamp."""

    market: MarketName = Field(description="Market scope used for session classification.")
    session_date: date = Field(description="Local market date for the session.")
    timezone: str = Field(description="IANA timezone used for session boundaries.")
    session_kind: MarketSessionKind = Field(description="Resolved market session kind.")
    open_at: datetime | None = Field(
        default=None,
        description="UTC market open time for the session date when applicable.",
    )
    close_at: datetime | None = Field(
        default=None,
        description="UTC market close time for the session date when applicable.",
    )

    @model_validator(mode="after")
    def validate_session(self) -> MarketSession:
        """Require valid timezone metadata and ordered bounds when both exist."""

        _assert_valid_timezone(self.timezone, field_name="timezone")
        if self.open_at is not None and self.close_at is not None and self.close_at < self.open_at:
            raise ValueError("close_at must be greater than or equal to open_at.")
        return self


class MarketCalendarEvent(StrictModel):
    """Minimal explicit market calendar override for deterministic local timing."""

    event_kind: MarketCalendarEventKind = Field(description="Override event type.")
    market: MarketName = Field(description="Market scope affected by the override.")
    session_date: date = Field(description="Local market date affected by the override.")
    timezone: str = Field(description="IANA timezone used by the override.")
    open_at: datetime | None = Field(
        default=None,
        description="UTC override open time when applicable.",
    )
    close_at: datetime | None = Field(
        default=None,
        description="UTC override close time when applicable.",
    )
    session_kind: MarketSessionKind | None = Field(
        default=None,
        description="Explicit session-kind override when needed.",
    )
    notes: list[str] = Field(default_factory=list, description="Override notes.")

    @model_validator(mode="after")
    def validate_event(self) -> MarketCalendarEvent:
        """Require timezone validity and ordered override times."""

        _assert_valid_timezone(self.timezone, field_name="timezone")
        if self.open_at is not None and self.close_at is not None and self.close_at < self.open_at:
            raise ValueError("close_at must be greater than or equal to open_at.")
        return self


class DataAvailabilityRule(StrictModel):
    """Code-owned rule metadata for deterministic availability decisions."""

    rule_name: str = Field(description="Stable rule identifier.")
    applies_to: DataAvailabilityTarget = Field(description="Artifact family governed by the rule.")
    market: MarketName = Field(description="Market scope used by the rule.")
    timezone: str = Field(description="IANA timezone used to evaluate the rule.")
    requires_publication_time: bool = Field(
        description="Whether the rule requires a publication timestamp to resolve availability."
    )
    same_day_policy: SameDayAvailabilityPolicy = Field(
        description="High-level same-day versus next-session policy for the rule."
    )
    delay_minutes: int = Field(
        default=0,
        ge=0,
        description="Optional additional delay in minutes before the item becomes available.",
    )
    buffer_minutes: int = Field(
        default=0,
        ge=0,
        description="Optional downstream safety buffer in minutes.",
    )
    notes: list[str] = Field(default_factory=list, description="Explicit rule notes.")

    @model_validator(mode="after")
    def validate_rule(self) -> DataAvailabilityRule:
        """Require timezone validity and a non-empty rule name."""

        if not self.rule_name:
            raise ValueError("rule_name must be non-empty.")
        _assert_valid_timezone(self.timezone, field_name="timezone")
        return self


class AvailabilityWindow(StrictModel):
    """Resolved downstream availability window for one artifact."""

    available_from: datetime = Field(
        description="UTC time when the artifact becomes usable downstream."
    )
    available_until: datetime | None = Field(
        default=None,
        description="UTC time when the artifact should no longer be treated as valid.",
    )
    availability_basis: AvailabilityBasis = Field(
        description="Basis used to justify the availability window."
    )
    publication_timing: PublicationTiming | None = Field(
        default=None,
        description="Source-level publication timing that informed the window when applicable.",
    )
    market_session: MarketSession | None = Field(
        default=None,
        description="Market session classification used to resolve the window when applicable.",
    )
    rule_name: str | None = Field(
        default=None,
        description="Timing rule used to resolve the window when applicable.",
    )

    @model_validator(mode="after")
    def validate_window(self) -> AvailabilityWindow:
        """Require ordered availability bounds."""

        if self.available_until is not None and self.available_until < self.available_from:
            raise ValueError("available_until must be greater than or equal to available_from.")
        return self


class DecisionCutoff(StrictModel):
    """Decision-time cutoff used to judge point-in-time availability."""

    decision_cutoff_id: str = Field(description="Stable decision-cutoff identifier.")
    market: MarketName = Field(description="Market scope used by the cutoff.")
    timezone: str = Field(description="IANA timezone used by the cutoff.")
    decision_time: datetime = Field(description="UTC time when the workflow made a decision.")
    decision_session_kind: MarketSessionKind = Field(
        description="Market session kind active at the decision time."
    )
    eligible_information_time: datetime = Field(
        description="Latest UTC time that information could have become available to participate."
    )
    rule_name: str = Field(description="Timing rule used to build the cutoff.")
    rationale: str = Field(description="Short explanation of why the cutoff is valid.")
    provenance: ProvenanceRecord = Field(description="Traceability for the cutoff.")

    @model_validator(mode="after")
    def validate_cutoff(self) -> DecisionCutoff:
        """Require valid timezone metadata and ordered cutoff times."""

        _assert_valid_timezone(self.timezone, field_name="timezone")
        if self.eligible_information_time > self.decision_time:
            raise ValueError(
                "eligible_information_time must be less than or equal to decision_time."
            )
        return self


class TimingAnomaly(TimestampedModel):
    """Structured timing anomaly that should remain visible to operators and tests."""

    timing_anomaly_id: str = Field(description="Canonical timing-anomaly identifier.")
    target_type: str = Field(description="Artifact family affected by the anomaly.")
    target_id: str = Field(description="Identifier of the artifact affected by the anomaly.")
    anomaly_kind: TimingAnomalyKind = Field(description="Structured anomaly classification.")
    blocking: bool = Field(description="Whether the anomaly should block decision-time usage.")
    message: str = Field(description="Human-readable explanation of the anomaly.")
    event_time: datetime | None = Field(default=None, description="Observed event time when present.")
    publication_time: datetime | None = Field(
        default=None, description="Observed publication time when present."
    )
    internal_available_at: datetime | None = Field(
        default=None,
        description="Observed internal availability time when present.",
    )
    decision_time: datetime | None = Field(
        default=None, description="Observed decision time when relevant."
    )
    ingested_at: datetime | None = Field(default=None, description="Observed ingestion time when relevant.")
    retrieved_at: datetime | None = Field(
        default=None, description="Observed retrieval time when relevant."
    )
    provenance: ProvenanceRecord = Field(description="Traceability for anomaly detection.")

    @model_validator(mode="after")
    def validate_anomaly(self) -> TimingAnomaly:
        """Require visible target linkage and message text."""

        if not self.target_type:
            raise ValueError("target_type must be non-empty.")
        if not self.target_id:
            raise ValueError("target_id must be non-empty.")
        if not self.message:
            raise ValueError("message must be non-empty.")
        return self


__all__ = [
    "AvailabilityBasis",
    "AvailabilityWindow",
    "DataAvailabilityRule",
    "DataAvailabilityTarget",
    "DecisionCutoff",
    "MarketCalendarEvent",
    "MarketCalendarEventKind",
    "MarketName",
    "MarketSession",
    "MarketSessionKind",
    "PublicationTiming",
    "SameDayAvailabilityPolicy",
    "TimingAnomaly",
    "TimingAnomalyKind",
]
