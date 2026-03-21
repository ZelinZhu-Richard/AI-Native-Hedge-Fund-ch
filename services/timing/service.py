from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field

from libraries.core import build_provenance
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ArtifactStorageLocation,
    AvailabilityBasis,
    AvailabilityWindow,
    DataAvailabilityRule,
    DecisionCutoff,
    Document,
    EarningsCall,
    MarketCalendarEvent,
    MarketName,
    MarketSession,
    MarketSessionKind,
    PublicationTiming,
    SourceReference,
    StrictModel,
    TimingAnomaly,
    TimingAnomalyKind,
)
from libraries.time import ensure_utc
from libraries.utils import make_canonical_id, make_prefixed_id
from services.timing.calendar import classify_us_equities_session, next_us_equities_open
from services.timing.rules import (
    TIMING_RULES,
    US_EQUITIES_TIMEZONE,
    daily_price_bar_close_rule,
    derived_feature_from_inputs_rule,
    derived_signal_from_features_rule,
    public_document_daily_equity_rule,
)
from services.timing.storage import LocalTimingArtifactStore


class PersistTimingAnomaliesResponse(StrictModel):
    """Structured result from persisting timing anomalies."""

    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)


class TimingService(BaseService):
    """Resolve conservative point-in-time availability and timing anomalies."""

    capability_name = "timing"
    capability_description = "Normalizes publication timing, market sessions, decision cutoffs, and timing anomalies."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["SourceReference", "Document", "Feature", "Signal", "decision timestamps"],
            produces=["PublicationTiming", "AvailabilityWindow", "DecisionCutoff", "TimingAnomaly"],
            api_routes=[],
        )

    def rule(self, rule_name: str) -> DataAvailabilityRule:
        """Return one code-owned timing rule by name."""

        try:
            return TIMING_RULES[rule_name]()
        except KeyError as exc:
            raise ValueError(f"Unknown timing rule `{rule_name}`.") from exc

    def classify_market_session(
        self,
        *,
        timestamp: datetime,
        market: MarketName = MarketName.US_EQUITIES,
        overrides: list[MarketCalendarEvent] | None = None,
    ) -> MarketSession:
        """Classify one timestamp into a supported market session bucket."""

        if market is not MarketName.US_EQUITIES:
            raise ValueError(f"Unsupported market scope `{market.value}`.")
        return classify_us_equities_session(timestamp=timestamp, overrides=overrides)

    def build_source_reference_timing(
        self,
        *,
        source_reference: SourceReference,
    ) -> tuple[PublicationTiming | None, list[TimingAnomaly]]:
        """Build source-level publication timing conservatively."""

        anomalies: list[TimingAnomaly] = []
        if source_reference.published_at is None:
            anomalies.append(
                self._anomaly(
                    target_type="source_reference",
                    target_id=source_reference.source_reference_id,
                    anomaly_kind=TimingAnomalyKind.MISSING_PUBLICATION_TIMESTAMP,
                    blocking=False,
                    message="Source reference is missing a publication timestamp.",
                    ingested_at=source_reference.created_at,
                    retrieved_at=source_reference.retrieved_at,
                )
            )
            return None, anomalies
        if source_reference.retrieved_at is not None and source_reference.retrieved_at < source_reference.published_at:
            anomalies.append(
                self._anomaly(
                    target_type="source_reference",
                    target_id=source_reference.source_reference_id,
                    anomaly_kind=TimingAnomalyKind.RETRIEVED_BEFORE_PUBLICATION,
                    blocking=False,
                    message="Source retrieval time precedes the recorded publication timestamp.",
                    publication_time=source_reference.published_at,
                    retrieved_at=source_reference.retrieved_at,
                )
            )
        publication_timing = PublicationTiming(
            event_time=None,
            publication_time=source_reference.published_at,
            internal_available_at=source_reference.published_at,
            source_timezone="UTC",
            normalized_timezone="UTC",
            rule_name="source_reference_immediate_visibility",
            notes=["Source visibility is treated as immediate for normalized source metadata."],
        )
        return publication_timing, anomalies

    def build_document_timing(
        self,
        *,
        document: Document,
        source_reference: SourceReference | None = None,
        overrides: list[MarketCalendarEvent] | None = None,
    ) -> tuple[PublicationTiming | None, AvailabilityWindow | None, list[TimingAnomaly]]:
        """Build document publication timing and a conservative availability window."""

        publication_time = document.source_published_at
        if publication_time is None and source_reference is not None:
            publication_time = source_reference.published_at
        anomalies: list[TimingAnomaly] = []
        if publication_time is None:
            anomalies.append(
                self._anomaly(
                    target_type="document",
                    target_id=document.document_id,
                    anomaly_kind=TimingAnomalyKind.MISSING_PUBLICATION_TIMESTAMP,
                    blocking=False,
                    message="Document is missing a publication timestamp.",
                    ingested_at=document.ingested_at,
                )
            )
            return None, None, anomalies
        if document.ingested_at < publication_time:
            anomalies.append(
                self._anomaly(
                    target_type="document",
                    target_id=document.document_id,
                    anomaly_kind=TimingAnomalyKind.INGESTED_BEFORE_PUBLICATION,
                    blocking=False,
                    message="Document ingestion time precedes the recorded publication timestamp.",
                    publication_time=publication_time,
                    ingested_at=document.ingested_at,
                )
            )
        event_time = self._document_event_time(document=document)
        if event_time is not None and event_time > publication_time:
            anomalies.append(
                self._anomaly(
                    target_type="document",
                    target_id=document.document_id,
                    anomaly_kind=TimingAnomalyKind.EVENT_AFTER_PUBLICATION,
                    blocking=False,
                    message="Document event time occurs after its recorded publication timestamp.",
                    event_time=event_time,
                    publication_time=publication_time,
                )
            )

        rule = public_document_daily_equity_rule()
        availability_window = self.resolve_publication_window(
            publication_time=publication_time,
            rule=rule,
            overrides=overrides,
        )
        publication_timing = PublicationTiming(
            event_time=event_time,
            publication_time=publication_time,
            internal_available_at=availability_window.available_from,
            source_timezone="UTC",
            normalized_timezone="UTC",
            rule_name=rule.rule_name,
            notes=rule.notes,
        )
        return (
            publication_timing,
            availability_window.model_copy(update={"publication_timing": publication_timing}),
            anomalies,
        )

    def resolve_publication_window(
        self,
        *,
        publication_time: datetime,
        rule: DataAvailabilityRule,
        overrides: list[MarketCalendarEvent] | None = None,
    ) -> AvailabilityWindow:
        """Resolve a market-aware availability window from a publication timestamp."""

        publication_time = ensure_utc(publication_time)
        if rule.rule_name == public_document_daily_equity_rule().rule_name:
            session = self.classify_market_session(
                timestamp=publication_time,
                market=rule.market,
                overrides=overrides,
            )
            if session.session_kind is MarketSessionKind.PRE_MARKET:
                assert session.open_at is not None
                available_from = session.open_at
            else:
                available_from = next_us_equities_open(
                    timestamp=publication_time + timedelta(seconds=1),
                    overrides=overrides,
                )
            return AvailabilityWindow(
                available_from=available_from + timedelta(minutes=rule.delay_minutes),
                available_until=None,
                availability_basis=AvailabilityBasis.PUBLICATION_RULE,
                publication_timing=None,
                market_session=session,
                rule_name=rule.rule_name,
            )
        if rule.rule_name == daily_price_bar_close_rule().rule_name:
            session = self.classify_market_session(
                timestamp=publication_time,
                market=rule.market,
                overrides=overrides,
            )
            return AvailabilityWindow(
                available_from=publication_time,
                available_until=None,
                availability_basis=AvailabilityBasis.MARKET_DATA_CLOSE,
                publication_timing=None,
                market_session=session,
                rule_name=rule.rule_name,
            )
        raise ValueError(f"Unsupported publication-window rule `{rule.rule_name}`.")

    def derive_feature_availability(
        self,
        *,
        target_id: str,
        source_reference_ids: list[str],
        upstream_windows: list[AvailabilityWindow],
        fallback_time: datetime,
    ) -> tuple[AvailabilityWindow, list[TimingAnomaly]]:
        """Resolve feature availability from upstream windows with a compatibility fallback."""

        return self._derive_availability(
            target_type="feature_value",
            target_id=target_id,
            source_reference_ids=source_reference_ids,
            upstream_windows=upstream_windows,
            fallback_time=fallback_time,
            rule=derived_feature_from_inputs_rule(),
        )

    def derive_signal_availability(
        self,
        *,
        target_id: str,
        source_reference_ids: list[str],
        upstream_windows: list[AvailabilityWindow],
        fallback_time: datetime,
    ) -> tuple[AvailabilityWindow, list[TimingAnomaly]]:
        """Resolve signal availability from upstream feature windows with a fallback."""

        return self._derive_availability(
            target_type="signal",
            target_id=target_id,
            source_reference_ids=source_reference_ids,
            upstream_windows=upstream_windows,
            fallback_time=fallback_time,
            rule=derived_signal_from_features_rule(),
        )

    def build_price_bar_availability(
        self,
        *,
        bar_time: datetime,
        overrides: list[MarketCalendarEvent] | None = None,
    ) -> AvailabilityWindow:
        """Build the availability window for one synthetic daily price bar."""

        return self.resolve_publication_window(
            publication_time=bar_time,
            rule=daily_price_bar_close_rule(),
            overrides=overrides,
        )

    def build_decision_cutoff(
        self,
        *,
        decision_time: datetime,
        market: MarketName = MarketName.US_EQUITIES,
        overrides: list[MarketCalendarEvent] | None = None,
    ) -> DecisionCutoff:
        """Build a decision cutoff used to evaluate point-in-time eligibility."""

        session = self.classify_market_session(
            timestamp=decision_time,
            market=market,
            overrides=overrides,
        )
        return DecisionCutoff(
            decision_cutoff_id=make_canonical_id(
                "dcut",
                market.value,
                ensure_utc(decision_time).isoformat(),
            ),
            market=market,
            timezone=US_EQUITIES_TIMEZONE,
            decision_time=ensure_utc(decision_time),
            decision_session_kind=session.session_kind,
            eligible_information_time=ensure_utc(decision_time),
            rule_name=daily_price_bar_close_rule().rule_name,
            rationale="Daily exploratory backtests make decisions at the recorded price-bar close.",
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="decision_cutoff_resolution",
                source_reference_ids=[],
                upstream_artifact_ids=[make_canonical_id("dcutsrc", market.value)],
            ),
        )

    def is_available_by(
        self,
        *,
        availability_window: AvailabilityWindow,
        decision_cutoff: DecisionCutoff,
        extra_buffer_minutes: int = 0,
    ) -> bool:
        """Return whether an artifact was available by the decision cutoff."""

        adjusted_available_from = availability_window.available_from + timedelta(
            minutes=extra_buffer_minutes
        )
        if availability_window.available_until is not None and availability_window.available_until < decision_cutoff.decision_time:
            return False
        return adjusted_available_from <= decision_cutoff.eligible_information_time

    def validate_timezone_name(self, timezone_name: str) -> list[TimingAnomaly]:
        """Return anomalies for invalid timezone assumptions instead of raising."""

        try:
            ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            return [
                self._anomaly(
                    target_type="timezone",
                    target_id=timezone_name,
                    anomaly_kind=TimingAnomalyKind.INVALID_TIMEZONE,
                    blocking=False,
                    message=f"`{timezone_name}` is not a valid IANA timezone name.",
                )
            ]
        return []

    def persist_anomalies(
        self,
        *,
        anomalies: list[TimingAnomaly],
        output_root: Path,
    ) -> PersistTimingAnomaliesResponse:
        """Persist timing anomalies under the local timing root."""

        store = LocalTimingArtifactStore(root=output_root, clock=self.clock)
        storage_locations = [
            store.persist_model(
                artifact_id=anomaly.timing_anomaly_id,
                category="timing_anomalies",
                model=anomaly,
                source_reference_ids=anomaly.provenance.source_reference_ids,
            )
            for anomaly in anomalies
        ]
        return PersistTimingAnomaliesResponse(storage_locations=storage_locations)

    def _derive_availability(
        self,
        *,
        target_type: str,
        target_id: str,
        source_reference_ids: list[str],
        upstream_windows: list[AvailabilityWindow],
        fallback_time: datetime,
        rule: DataAvailabilityRule,
    ) -> tuple[AvailabilityWindow, list[TimingAnomaly]]:
        """Resolve a derived availability window from upstream inputs or a fallback."""

        if upstream_windows:
            latest_upstream = max(window.available_from for window in upstream_windows)
            if latest_upstream <= ensure_utc(fallback_time):
                return (
                    AvailabilityWindow(
                        available_from=latest_upstream,
                        available_until=None,
                        availability_basis=AvailabilityBasis.DERIVED_FROM_INPUTS,
                        publication_timing=None,
                        market_session=None,
                        rule_name=rule.rule_name,
                    ),
                    [],
                )
            return (
                AvailabilityWindow(
                    available_from=ensure_utc(fallback_time),
                    available_until=None,
                    availability_basis=AvailabilityBasis.COMPATIBILITY_FALLBACK,
                    publication_timing=None,
                    market_session=None,
                    rule_name=rule.rule_name,
                ),
                [
                    self._anomaly(
                        target_type=target_type,
                        target_id=target_id,
                        anomaly_kind=TimingAnomalyKind.UPSTREAM_AVAILABILITY_AFTER_DERIVED_ARTIFACT,
                        blocking=False,
                        message=(
                            "Upstream availability metadata was later than the derived artifact timestamp; "
                            "compatibility fallback was used."
                        ),
                        internal_available_at=latest_upstream,
                        source_reference_ids=source_reference_ids,
                    )
                ],
            )
        return (
            AvailabilityWindow(
                available_from=ensure_utc(fallback_time),
                available_until=None,
                availability_basis=AvailabilityBasis.COMPATIBILITY_FALLBACK,
                publication_timing=None,
                market_session=None,
                rule_name=rule.rule_name,
            ),
            [
                self._anomaly(
                    target_type=target_type,
                    target_id=target_id,
                    anomaly_kind=TimingAnomalyKind.MISSING_UPSTREAM_AVAILABILITY,
                    blocking=False,
                    message="Upstream availability metadata was missing; compatibility fallback was used.",
                    internal_available_at=ensure_utc(fallback_time),
                    source_reference_ids=source_reference_ids,
                )
            ],
        )

    def _document_event_time(self, *, document: Document) -> datetime | None:
        """Return a conservative document event time when one is clearly defined."""

        if isinstance(document, EarningsCall):
            return document.call_datetime
        return None

    def _anomaly(
        self,
        *,
        target_type: str,
        target_id: str,
        anomaly_kind: TimingAnomalyKind,
        blocking: bool,
        message: str,
        source_reference_ids: list[str] | None = None,
        event_time: datetime | None = None,
        publication_time: datetime | None = None,
        internal_available_at: datetime | None = None,
        decision_time: datetime | None = None,
        ingested_at: datetime | None = None,
        retrieved_at: datetime | None = None,
    ) -> TimingAnomaly:
        """Build one structured timing anomaly with standard provenance."""

        now = self.clock.now()
        return TimingAnomaly(
            timing_anomaly_id=make_prefixed_id("tanom"),
            target_type=target_type,
            target_id=target_id,
            anomaly_kind=anomaly_kind,
            blocking=blocking,
            message=message,
            event_time=ensure_utc(event_time) if event_time is not None else None,
            publication_time=ensure_utc(publication_time) if publication_time is not None else None,
            internal_available_at=(
                ensure_utc(internal_available_at) if internal_available_at is not None else None
            ),
            decision_time=ensure_utc(decision_time) if decision_time is not None else None,
            ingested_at=ensure_utc(ingested_at) if ingested_at is not None else None,
            retrieved_at=ensure_utc(retrieved_at) if retrieved_at is not None else None,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="timing_anomaly_detection",
                source_reference_ids=source_reference_ids or [],
                upstream_artifact_ids=[target_id],
            ),
            created_at=now,
            updated_at=now,
        )


__all__ = [
    "PersistTimingAnomaliesResponse",
    "TimingService",
]
