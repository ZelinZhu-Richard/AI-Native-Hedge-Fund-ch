from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    AblationView,
    DataLayer,
    DerivedArtifactValidationStatus,
    Document,
    DocumentKind,
    DocumentStatus,
    Feature,
    FeatureDefinition,
    FeatureFamily,
    FeatureLineage,
    FeatureStatus,
    FeatureValue,
    FeatureValueType,
    PriceSeriesMetadata,
    PriceSeriesStatus,
    ProvenanceRecord,
    ResearchStance,
    Signal,
    SignalLineage,
    SignalScore,
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


def test_feature_value_requires_exactly_one_value() -> None:
    now = utc_now()

    with pytest.raises(ValidationError):
        FeatureValue(
            feature_value_id="fval_test",
            feature_definition_id="fdef_test",
            as_of_date=date(2026, 3, 15),
            available_at=now,
            numeric_value=1.0,
            text_value="invalid",
            provenance=ProvenanceRecord(processing_time=now),
            created_at=now,
            updated_at=now,
        )


def test_feature_requires_matching_definition_ids() -> None:
    now = utc_now()

    with pytest.raises(ValidationError):
        Feature(
            feature_id="feat_test",
            entity_id="co_test",
            company_id="co_test",
            data_layer=DataLayer.DERIVED,
            feature_definition=FeatureDefinition(
                feature_definition_id="fdef_test",
                name="support_grade_score",
                family=FeatureFamily.TEXT_DERIVED,
                value_type=FeatureValueType.NUMERIC,
                description="A test feature.",
                ablation_views=[AblationView.TEXT_ONLY],
                status=FeatureStatus.PROVISIONAL,
                validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
                provenance=ProvenanceRecord(processing_time=now),
                created_at=now,
                updated_at=now,
            ),
            feature_value=FeatureValue(
                feature_value_id="fval_test",
                feature_definition_id="fdef_other",
                as_of_date=date(2026, 3, 15),
                available_at=now,
                numeric_value=1.0,
                provenance=ProvenanceRecord(processing_time=now),
                created_at=now,
                updated_at=now,
            ),
            status=FeatureStatus.PROVISIONAL,
            validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
            lineage=FeatureLineage(
                feature_lineage_id="flin_test",
                hypothesis_id="hyp_test",
                counter_hypothesis_id="chyp_test",
                evidence_assessment_id="eass_test",
                research_brief_id="rbrief_test",
                supporting_evidence_link_ids=["sel_test"],
                source_document_ids=["doc_test"],
                created_at=now,
                updated_at=now,
            ),
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
            stance=ResearchStance.POSITIVE,
            ablation_view=AblationView.TEXT_ONLY,
            thesis_summary="Invalid signal window.",
            feature_ids=["feat_test"],
            component_scores=[
                SignalScore(
                    signal_score_id="sscore_test",
                    metric_name="support_grade_component",
                    value=0.5,
                    scale_min=0.0,
                    scale_max=1.0,
                    validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
                    source_feature_ids=["feat_test"],
                    assumptions=["Unit test score."],
                    provenance=ProvenanceRecord(processing_time=now),
                    created_at=now,
                    updated_at=now,
                )
            ],
            primary_score=0.75,
            effective_at=now,
            expires_at=now.replace(hour=11),
            status=SignalStatus.CANDIDATE,
            validation_status=DerivedArtifactValidationStatus.UNVALIDATED,
            lineage=SignalLineage(
                signal_lineage_id="slin_test",
                feature_ids=["feat_test"],
                feature_definition_ids=["fdef_test"],
                feature_value_ids=["fval_test"],
                research_artifact_ids=["hyp_test", "eass_test", "rbrief_test"],
                supporting_evidence_link_ids=["sel_test"],
                input_families=[FeatureFamily.TEXT_DERIVED],
                created_at=now,
                updated_at=now,
            ),
            assumptions=["Unit test signal."],
            uncertainties=["Unit test uncertainty."],
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
