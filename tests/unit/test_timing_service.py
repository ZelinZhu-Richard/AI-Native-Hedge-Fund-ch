from __future__ import annotations

from datetime import UTC, datetime, timedelta

from libraries.schemas import (
    DataLayer,
    DocumentStatus,
    MarketSessionKind,
    NewsItem,
    ProvenanceRecord,
    PublicationTiming,
    SourceReference,
    SourceType,
    TimingAnomalyKind,
)
from libraries.time import FrozenClock
from services.timing import TimingService

FIXED_NOW = datetime(2026, 3, 25, 15, 0, tzinfo=UTC)


def test_classify_market_session_handles_pre_market_regular_after_hours_and_closed() -> None:
    service = TimingService(clock=FrozenClock(FIXED_NOW))

    assert (
        service.classify_market_session(
            timestamp=datetime(2026, 3, 20, 12, 0, tzinfo=UTC)
        ).session_kind
        is MarketSessionKind.PRE_MARKET
    )
    assert (
        service.classify_market_session(
            timestamp=datetime(2026, 3, 20, 15, 0, tzinfo=UTC)
        ).session_kind
        is MarketSessionKind.REGULAR
    )
    assert (
        service.classify_market_session(
            timestamp=datetime(2026, 3, 20, 22, 0, tzinfo=UTC)
        ).session_kind
        is MarketSessionKind.AFTER_HOURS
    )
    assert (
        service.classify_market_session(
            timestamp=datetime(2026, 3, 21, 15, 0, tzinfo=UTC)
        ).session_kind
        is MarketSessionKind.CLOSED
    )


def test_document_timing_allows_pre_market_same_day_and_after_hours_next_session() -> None:
    service = TimingService(clock=FrozenClock(FIXED_NOW))

    pre_market_document = _news_document(
        document_id="doc_pre",
        published_at=datetime(2026, 3, 18, 12, 15, tzinfo=UTC),
    )
    pre_market_timing, pre_market_window, pre_market_anomalies = service.build_document_timing(
        document=pre_market_document
    )
    assert pre_market_timing is not None
    assert pre_market_window is not None
    assert pre_market_timing.internal_available_at == datetime(2026, 3, 18, 13, 30, tzinfo=UTC)
    assert pre_market_window.available_from == datetime(2026, 3, 18, 13, 30, tzinfo=UTC)
    assert pre_market_anomalies == []

    after_hours_document = _news_document(
        document_id="doc_after",
        published_at=datetime(2026, 3, 18, 22, 35, tzinfo=UTC),
    )
    after_hours_timing, after_hours_window, after_hours_anomalies = (
        service.build_document_timing(document=after_hours_document)
    )
    assert after_hours_timing is not None
    assert after_hours_window is not None
    assert after_hours_timing.internal_available_at == datetime(2026, 3, 19, 13, 30, tzinfo=UTC)
    assert after_hours_window.available_from == datetime(2026, 3, 19, 13, 30, tzinfo=UTC)
    assert after_hours_anomalies == []


def test_price_bar_close_and_decision_cutoff_use_bar_close() -> None:
    service = TimingService(clock=FrozenClock(FIXED_NOW))
    bar_time = datetime(2026, 3, 20, 20, 0, tzinfo=UTC)

    availability_window = service.build_price_bar_availability(bar_time=bar_time)
    decision_cutoff = service.build_decision_cutoff(decision_time=bar_time)

    assert availability_window.available_from == bar_time
    assert decision_cutoff.decision_time == bar_time
    assert service.is_available_by(
        availability_window=availability_window,
        decision_cutoff=decision_cutoff,
    )


def test_build_source_reference_timing_and_missing_publication_are_explicit() -> None:
    service = TimingService(clock=FrozenClock(FIXED_NOW))

    source_reference = SourceReference(
        source_reference_id="src_ok",
        source_type=SourceType.NEWSWIRE,
        external_id="news:ok",
        uri="https://example.com/news/ok",
        title="Ok",
        publisher="Example",
        content_hash="hash",
        published_at=datetime(2026, 3, 18, 12, 15, tzinfo=UTC),
        retrieved_at=datetime(2026, 3, 18, 12, 20, tzinfo=UTC),
        effective_at=None,
        publication_timing=None,
        license=None,
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    timing, anomalies = service.build_source_reference_timing(source_reference=source_reference)
    assert timing == PublicationTiming(
        event_time=None,
        publication_time=datetime(2026, 3, 18, 12, 15, tzinfo=UTC),
        internal_available_at=datetime(2026, 3, 18, 12, 15, tzinfo=UTC),
        source_timezone="UTC",
        normalized_timezone="UTC",
        rule_name="source_reference_immediate_visibility",
        notes=["Source visibility is treated as immediate for normalized source metadata."],
    )
    assert anomalies == []

    missing_publication = source_reference.model_copy(
        update={"source_reference_id": "src_missing", "published_at": None}
    )
    missing_timing, missing_anomalies = service.build_source_reference_timing(
        source_reference=missing_publication
    )
    assert missing_timing is None
    assert [anomaly.anomaly_kind for anomaly in missing_anomalies] == [
        TimingAnomalyKind.MISSING_PUBLICATION_TIMESTAMP
    ]


def test_validate_timezone_name_and_document_missing_publication_record_anomalies() -> None:
    service = TimingService(clock=FrozenClock(FIXED_NOW))
    assert [anomaly.anomaly_kind for anomaly in service.validate_timezone_name("Bad/Timezone")] == [
        TimingAnomalyKind.INVALID_TIMEZONE
    ]

    document_timing, availability_window, anomalies = service.build_document_timing(
        document=_news_document(document_id="doc_missing", published_at=None)
    )
    assert document_timing is None
    assert availability_window is None
    assert [anomaly.anomaly_kind for anomaly in anomalies] == [
        TimingAnomalyKind.MISSING_PUBLICATION_TIMESTAMP
    ]


def _news_document(*, document_id: str, published_at: datetime | None) -> NewsItem:
    ingested_at = (
        published_at + timedelta(minutes=15)
        if published_at is not None
        else datetime(2026, 3, 18, 12, 30, tzinfo=UTC)
    )
    return NewsItem(
        document_id=document_id,
        company_id="co_apex",
        title="Apex launches monitoring update",
        source_reference_id=f"src_{document_id}",
        external_id=f"news:{document_id}",
        data_layer=DataLayer.NORMALIZED,
        language="en",
        storage_uri=None,
        content_hash="hash",
        source_published_at=published_at,
        effective_at=published_at,
        publication_timing=None,
        ingested_at=ingested_at,
        processed_at=FIXED_NOW,
        status=DocumentStatus.NORMALIZED,
        tags=[],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
        publisher="Example Newswire",
        author_names=["Analyst"],
        headline="Apex launches monitoring update",
        summary="Apex expands its industrial monitoring suite.",
        relevance_score=None,
        embargo_lifted_at=None,
    )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
