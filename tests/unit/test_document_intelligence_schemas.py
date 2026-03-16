from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    ClaimType,
    DocumentSegment,
    EvidenceSpan,
    ExtractedClaim,
    ProvenanceRecord,
    SegmentKind,
)


def test_document_segment_rejects_inverted_offsets() -> None:
    now = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)

    with pytest.raises(ValidationError):
        DocumentSegment(
            document_segment_id="seg_test",
            parsed_document_text_id="pdoc_test",
            document_id="doc_test",
            source_reference_id="src_test",
            parent_segment_id=None,
            segment_kind=SegmentKind.PARAGRAPH,
            sequence_index=0,
            label="paragraph",
            speaker=None,
            text="bad",
            start_char=10,
            end_char=5,
            provenance=ProvenanceRecord(
                source_reference_ids=["src_test"],
                transformation_name="unit_test",
                processing_time=now,
            ),
            created_at=now,
            updated_at=now,
        )


def test_segment_linked_evidence_span_requires_offsets() -> None:
    now = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)

    with pytest.raises(ValidationError):
        EvidenceSpan(
            evidence_span_id="evd_test",
            source_reference_id="src_test",
            document_id="doc_test",
            segment_id="seg_test",
            text="Exact sentence.",
            start_char=None,
            end_char=None,
            page_number=None,
            speaker=None,
            captured_at=now,
            confidence=None,
            provenance=ProvenanceRecord(
                source_reference_ids=["src_test"],
                transformation_name="unit_test",
                processing_time=now,
            ),
            created_at=now,
            updated_at=now,
        )


def test_extracted_claim_requires_evidence_span_ids() -> None:
    now = datetime(2026, 3, 16, 12, 0, tzinfo=UTC)

    with pytest.raises(ValidationError):
        ExtractedClaim(
            extracted_claim_id="claim_test",
            document_id="doc_test",
            source_reference_id="src_test",
            company_id="co_test",
            segment_id="seg_test",
            statement="Revenue increased.",
            evidence_span_ids=[],
            speaker=None,
            confidence=None,
            claim_type=ClaimType.FINANCIAL_RESULT,
            provenance=ProvenanceRecord(
                source_reference_ids=["src_test"],
                transformation_name="unit_test",
                processing_time=now,
            ),
            created_at=now,
            updated_at=now,
        )
