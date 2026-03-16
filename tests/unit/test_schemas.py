from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    DataLayer,
    Document,
    DocumentKind,
    DocumentStatus,
    Feature,
    FeatureStatus,
    ProvenanceRecord,
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
