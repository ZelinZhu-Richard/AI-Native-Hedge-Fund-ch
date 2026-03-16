from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    DataLayer,
    Document,
    DocumentKind,
    DocumentStatus,
    Feature,
    FeatureStatus,
    PositionSide,
    PriceSeriesMetadata,
    PriceSeriesStatus,
    ProvenanceRecord,
    Signal,
    SignalStatus,
    SourceReference,
    SourceType,
)
from libraries.time import utc_now


def test_document_schema_accepts_valid_payload() -> None:
    now = utc_now()
    document = Document(
        document_id="doc_test",
        kind=DocumentKind.DOCUMENT,
        company_id="co_test",
        title="Test Document",
        source_reference_id="src_test",
        data_layer=DataLayer.NORMALIZED,
        language="en",
        storage_uri="s3://bucket/doc.txt",
        content_hash="abc123",
        source_published_at=now,
        effective_at=now,
        ingested_at=now,
        processed_at=now,
        status=DocumentStatus.NORMALIZED,
        provenance=ProvenanceRecord(
            source_reference_ids=["src_test"],
            processing_time=now,
        ),
        created_at=now,
        updated_at=now,
    )

    assert document.document_id == "doc_test"
    assert document.status == DocumentStatus.NORMALIZED


def test_feature_requires_exactly_one_value() -> None:
    now = utc_now()

    with pytest.raises(ValidationError):
        Feature(
            feature_id="feat_test",
            name="test_feature",
            family="quality",
            entity_id="co_test",
            company_id="co_test",
            data_layer=DataLayer.DERIVED,
            definition="A test feature.",
            as_of_date=date(2026, 3, 15),
            available_at=now,
            status=FeatureStatus.COMPUTED,
            numeric_value=1.0,
            text_value="invalid",
            provenance=ProvenanceRecord(processing_time=now),
            created_at=now,
            updated_at=now,
        )


def test_document_schema_rejects_naive_datetimes() -> None:
    naive_now = datetime(2026, 3, 16, 12, 0)

    with pytest.raises(ValidationError):
        Document(
            document_id="doc_test",
            kind=DocumentKind.DOCUMENT,
            company_id="co_test",
            title="Naive Timestamp Document",
            source_reference_id="src_test",
            data_layer=DataLayer.NORMALIZED,
            language="en",
            storage_uri="s3://bucket/doc.txt",
            content_hash="abc123",
            source_published_at=naive_now,
            effective_at=naive_now,
            ingested_at=naive_now,
            processed_at=naive_now,
            status=DocumentStatus.NORMALIZED,
            provenance=ProvenanceRecord(processing_time=naive_now),
            created_at=naive_now,
            updated_at=naive_now,
        )


def test_signal_rejects_expiry_before_effective_time() -> None:
    now = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)

    with pytest.raises(ValidationError):
        Signal(
            signal_id="sig_test",
            company_id="co_test",
            hypothesis_id="hyp_test",
            signal_family="quality",
            direction=PositionSide.LONG,
            thesis_summary="Invalid signal window.",
            feature_ids=["feat_test"],
            component_scores=[],
            primary_score=0.75,
            effective_at=now,
            expires_at=now.replace(hour=11),
            status=SignalStatus.CANDIDATE,
            provenance=ProvenanceRecord(processing_time=now),
            created_at=now,
            updated_at=now,
        )


def test_source_reference_rejects_retrieval_before_publication() -> None:
    now = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)

    with pytest.raises(ValidationError):
        SourceReference(
            source_reference_id="src_test",
            source_type=SourceType.NEWSWIRE,
            external_id="news:1",
            uri="https://news.example.com/item",
            title="Invalid Source Reference",
            publisher="Example News",
            content_hash="abc123",
            published_at=now,
            retrieved_at=now.replace(hour=11),
            effective_at=now,
            license=None,
            provenance=ProvenanceRecord(processing_time=now),
            created_at=now,
            updated_at=now,
        )


def test_price_series_metadata_rejects_invalid_date_range() -> None:
    now = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)

    with pytest.raises(ValidationError):
        PriceSeriesMetadata(
            price_series_metadata_id="pxmeta_test",
            company_id="co_test",
            symbol="TEST",
            exchange="NASDAQ",
            currency="USD",
            frequency="daily",
            timezone="America/New_York",
            dataset_name="sample_prices",
            source_reference_id="src_test",
            vendor_symbol="TEST.O",
            first_price_date=date(2026, 3, 16),
            last_price_date=date(2026, 3, 15),
            status=PriceSeriesStatus.PLACEHOLDER,
            provenance=ProvenanceRecord(processing_time=now),
            created_at=now,
            updated_at=now,
        )
