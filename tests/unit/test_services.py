from __future__ import annotations

from datetime import UTC, datetime

from libraries.schemas import (
    DocumentKind,
    PortfolioExposureSummary,
    PortfolioProposal,
    PortfolioProposalStatus,
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
        selection_reason="Flat views should not turn into paper trades.",
        entry_conditions=[],
        exit_conditions=[],
        target_horizon="quarterly",
        proposed_weight_bps=0,
        max_weight_bps=100,
        evidence_span_ids=["esp_test"],
        supporting_evidence_link_ids=["sel_test"],
        research_artifact_ids=["hyp_test"],
        review_decision_ids=[],
        status=PositionIdeaStatus.DRAFT,
        provenance=ProvenanceRecord(processing_time=fixed_now),
        created_at=fixed_now,
        updated_at=fixed_now,
    )
    proposal = PortfolioProposal(
        portfolio_proposal_id="proposal_test",
        name="Test Proposal",
        as_of_time=fixed_now,
        generated_at=fixed_now,
        target_nav_usd=1_000_000.0,
        position_ideas=[idea],
        constraints=[],
        risk_checks=[],
        exposure_summary=PortfolioExposureSummary(
            portfolio_exposure_summary_id="pexpo_test",
            gross_exposure_bps=0,
            net_exposure_bps=0,
            long_exposure_bps=0,
            short_exposure_bps=0,
            cash_buffer_bps=10_000,
            position_count=1,
            turnover_bps_assumption=0,
            provenance=ProvenanceRecord(processing_time=fixed_now),
            created_at=fixed_now,
            updated_at=fixed_now,
        ),
        blocking_issues=[],
        review_decision_ids=[],
        review_required=True,
        status=PortfolioProposalStatus.APPROVED,
        summary="Flat-only proposal for unit testing.",
        provenance=ProvenanceRecord(processing_time=fixed_now),
        created_at=fixed_now,
        updated_at=fixed_now,
    )

    response = service.propose_trades(
        PaperTradeProposalRequest(
            portfolio_proposal=proposal,
            requested_by="unit_test",
        )
    )

    assert response.proposed_trades == []
