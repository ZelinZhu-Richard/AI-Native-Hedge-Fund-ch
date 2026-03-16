from __future__ import annotations

from datetime import UTC, datetime

from libraries.schemas import (
    DocumentKind,
    PositionIdea,
    PositionIdeaStatus,
    PositionSide,
    ProvenanceRecord,
)
from libraries.time import FrozenClock
from services.ingestion import DocumentIngestionRequest, IngestionService
from services.paper_execution import PaperExecutionService, PaperTradeProposalRequest


def test_ingestion_service_imports_and_accepts_request() -> None:
    fixed_now = datetime(2026, 3, 16, 14, 30, tzinfo=UTC)
    service = IngestionService(clock=FrozenClock(fixed_now))
    request = DocumentIngestionRequest(
        source_reference_id="src_test",
        document_kind=DocumentKind.FILING,
        title="Sample Filing",
        raw_text="sample payload",
        requested_by="unit_test",
    )

    response = service.ingest_document(request)

    assert response.status == "queued"
    assert response.document_id.startswith("doc_")
    assert response.queued_at == fixed_now


def test_paper_execution_ignores_flat_position_ideas() -> None:
    fixed_now = datetime(2026, 3, 16, 14, 30, tzinfo=UTC)
    service = PaperExecutionService(clock=FrozenClock(fixed_now))
    idea = PositionIdea(
        position_idea_id="idea_test",
        company_id="co_test",
        signal_id="sig_test",
        symbol="TEST",
        instrument_type="equity",
        side=PositionSide.FLAT,
        thesis_summary="No expression should be created for flat views.",
        entry_conditions=[],
        exit_conditions=[],
        target_horizon="quarterly",
        proposed_weight_bps=0,
        max_weight_bps=100,
        evidence_span_ids=[],
        status=PositionIdeaStatus.DRAFT,
        provenance=ProvenanceRecord(processing_time=fixed_now),
        created_at=fixed_now,
        updated_at=fixed_now,
    )

    response = service.propose_trades(
        PaperTradeProposalRequest(
            portfolio_proposal_id="proposal_test",
            position_ideas=[idea],
            requested_by="unit_test",
        )
    )

    assert response.proposed_trades == []
