from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from libraries.schemas import (
    DocumentKind,
    EvidenceSearchResult,
    MemoryScope,
    ResearchArtifactReference,
    RetrievalContext,
    RetrievalQuery,
    RetrievalResult,
)
from libraries.schemas.base import ProvenanceRecord

FIXED_NOW = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)


def test_retrieval_query_rejects_inverted_time_window() -> None:
    with pytest.raises(ValueError, match="time_end"):
        RetrievalQuery(
            retrieval_query_id="rqry_test",
            scopes=[MemoryScope.HYPOTHESIS],
            time_start=FIXED_NOW,
            time_end=FIXED_NOW.replace(hour=11),
            limit=10,
        )


def test_evidence_search_result_requires_stored_evidence_reference(tmp_path: Path) -> None:
    artifact_path = tmp_path / "evidence.json"
    artifact_path.write_text("{}", encoding="utf-8")
    non_evidence_reference = ResearchArtifactReference(
        research_artifact_reference_id="rref_test",
        scope=MemoryScope.HYPOTHESIS,
        artifact_type="Hypothesis",
        artifact_id="hyp_test",
        storage_uri=artifact_path.resolve().as_uri(),
        company_id="co_test",
        document_id="doc_test",
        document_kind=DocumentKind.NEWS_ITEM,
        primary_timestamp=FIXED_NOW,
        title="Test hypothesis",
        summary="Test summary",
        source_reference_ids=["src_test"],
        provenance=ProvenanceRecord(
            source_reference_ids=["src_test"],
            processing_time=FIXED_NOW,
        ),
    )

    with pytest.raises(ValueError, match="artifact_reference.scope == evidence"):
        EvidenceSearchResult(
            evidence_search_result_id="erslt_test",
            artifact_reference=non_evidence_reference,
            quote="Quoted evidence text.",
            source_reference_id="src_test",
            document_id="doc_test",
            document_kind=DocumentKind.NEWS_ITEM,
            rank=1,
            matched_fields=["scope"],
            provenance=ProvenanceRecord(
                source_reference_ids=["src_test"],
                processing_time=FIXED_NOW,
            ),
        )


def test_retrieval_context_supports_explicit_empty_results() -> None:
    query = RetrievalQuery(
        retrieval_query_id="rqry_empty",
        scopes=[MemoryScope.EVIDENCE, MemoryScope.HYPOTHESIS],
        limit=5,
    )

    context = RetrievalContext(
        query=query,
        results=[],
        evidence_results=[],
        notes=["No matching artifacts were found."],
        semantic_retrieval_used=False,
    )

    assert context.results == []
    assert context.evidence_results == []
    assert context.semantic_retrieval_used is False
    assert context.notes == ["No matching artifacts were found."]


def test_retrieval_result_preserves_real_artifact_reference(tmp_path: Path) -> None:
    artifact_path = tmp_path / "memo.json"
    artifact_path.write_text("{}", encoding="utf-8")
    reference = ResearchArtifactReference(
        research_artifact_reference_id="rref_memo",
        scope=MemoryScope.MEMO,
        artifact_type="Memo",
        artifact_id="memo_test",
        storage_uri=artifact_path.resolve().as_uri(),
        company_id="co_test",
        document_id=None,
        document_kind=None,
        primary_timestamp=FIXED_NOW,
        title="Test memo",
        summary="Test summary",
        source_reference_ids=["src_test"],
        provenance=ProvenanceRecord(
            source_reference_ids=["src_test"],
            processing_time=FIXED_NOW,
        ),
    )

    result = RetrievalResult(
        retrieval_result_id="rrslt_memo",
        artifact_reference=reference,
        scope=MemoryScope.MEMO,
        rank=1,
        matched_fields=["scope", "artifact_type"],
        snippet="Test summary",
        score=2.0,
        provenance=ProvenanceRecord(
            source_reference_ids=["src_test"],
            processing_time=FIXED_NOW,
        ),
    )

    assert result.artifact_reference.storage_uri == artifact_path.resolve().as_uri()
    assert result.scope is MemoryScope.MEMO
