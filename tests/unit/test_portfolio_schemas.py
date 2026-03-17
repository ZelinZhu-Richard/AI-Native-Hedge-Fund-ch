from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    PaperTrade,
    PaperTradeStatus,
    PortfolioExposureSummary,
    PortfolioProposal,
    PortfolioProposalStatus,
    PositionIdea,
    PositionIdeaStatus,
    PositionSide,
    ReviewOutcome,
    RiskCheck,
    RiskCheckStatus,
    Severity,
)
from libraries.schemas.base import ProvenanceRecord
from libraries.utils import (
    paper_trade_status_from_review_outcome,
    portfolio_proposal_status_from_review_outcome,
    position_idea_status_from_review_outcome,
)

FIXED_NOW = datetime(2026, 3, 17, 12, 0, tzinfo=UTC)


def test_position_idea_requires_signal_and_evidence_linkage() -> None:
    with pytest.raises(ValidationError):
        PositionIdea(
            position_idea_id="idea_test",
            company_id="co_test",
            signal_id="",
            symbol="TEST",
            instrument_type="equity",
            side=PositionSide.LONG,
            thesis_summary="Test thesis.",
            selection_reason="Selected for test coverage.",
            entry_conditions=[],
            exit_conditions=[],
            target_horizon="next_1_4_quarters",
            proposed_weight_bps=300,
            max_weight_bps=500,
            evidence_span_ids=["esp_test"],
            supporting_evidence_link_ids=["sel_test"],
            research_artifact_ids=["hyp_test"],
            status=PositionIdeaStatus.PENDING_REVIEW,
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_portfolio_proposal_requires_exposure_summary_and_blocking_issues_alignment() -> None:
    with pytest.raises(ValidationError):
        PortfolioProposal(
            portfolio_proposal_id="proposal_test",
            name="Test Proposal",
            as_of_time=FIXED_NOW,
            generated_at=FIXED_NOW,
            target_nav_usd=1_000_000.0,
            position_ideas=[_position_idea()],
            constraints=[],
            risk_checks=[_risk_check(blocking=True)],
            exposure_summary=_exposure_summary(position_count=1),
            blocking_issues=[],
            review_required=True,
            status=PortfolioProposalStatus.PENDING_REVIEW,
            summary="One idea.",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_risk_check_rejects_blocking_pass_status() -> None:
    with pytest.raises(ValidationError):
        RiskCheck(
            risk_check_id="risk_test",
            subject_type="portfolio_proposal",
            subject_id="proposal_test",
            portfolio_constraint_id=None,
            rule_name="invalid",
            status=RiskCheckStatus.PASS,
            severity=Severity.INFO,
            blocking=True,
            observed_value=None,
            limit_value=None,
            unit=None,
            message="Invalid pass check.",
            checked_at=FIXED_NOW,
            reviewer_notes=[],
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_paper_trade_enforces_paper_only_contract() -> None:
    with pytest.raises(ValidationError):
        PaperTrade(
            paper_trade_id="trade_test",
            portfolio_proposal_id="proposal_test",
            position_idea_id="idea_test",
            symbol="TEST",
            side=PositionSide.LONG,
            execution_mode="paper_only",
            quantity=10.0,
            notional_usd=1000.0,
            assumed_reference_price_usd=None,
            time_in_force="day",
            status=PaperTradeStatus.PROPOSED,
            submitted_at=FIXED_NOW,
            requested_by="unit_test",
            review_decision_ids=[],
            execution_notes=[],
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_review_transition_helpers_map_existing_status_vocab() -> None:
    assert position_idea_status_from_review_outcome(ReviewOutcome.APPROVE) is PositionIdeaStatus.APPROVED_FOR_PORTFOLIO
    assert portfolio_proposal_status_from_review_outcome(ReviewOutcome.NEEDS_REVISION) is PortfolioProposalStatus.DRAFT
    assert paper_trade_status_from_review_outcome(ReviewOutcome.REJECT) is PaperTradeStatus.REJECTED


def _position_idea() -> PositionIdea:
    return PositionIdea(
        position_idea_id="idea_test",
        company_id="co_test",
        signal_id="sig_test",
        symbol="TEST",
        instrument_type="equity",
        side=PositionSide.LONG,
        thesis_summary="Test thesis.",
        selection_reason="Selected from a candidate signal.",
        entry_conditions=[],
        exit_conditions=[],
        target_horizon="next_1_4_quarters",
        proposed_weight_bps=300,
        max_weight_bps=500,
        evidence_span_ids=["esp_test"],
        supporting_evidence_link_ids=["sel_test"],
        research_artifact_ids=["hyp_test", "eass_test"],
        review_decision_ids=[],
        status=PositionIdeaStatus.PENDING_REVIEW,
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _risk_check(*, blocking: bool) -> RiskCheck:
    return RiskCheck(
        risk_check_id="risk_test",
        subject_type="portfolio_proposal",
        subject_id="proposal_test",
        portfolio_constraint_id="constraint_test",
        rule_name="gross_exposure_limit",
        status=RiskCheckStatus.FAIL if blocking else RiskCheckStatus.WARN,
        severity=Severity.HIGH if blocking else Severity.MEDIUM,
        blocking=blocking,
        observed_value=1600.0 if blocking else None,
        limit_value=1500.0 if blocking else None,
        unit="bps" if blocking else None,
        message="Risk check message.",
        checked_at=FIXED_NOW,
        reviewer_notes=[],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _exposure_summary(*, position_count: int) -> PortfolioExposureSummary:
    return PortfolioExposureSummary(
        portfolio_exposure_summary_id="pexpo_test",
        gross_exposure_bps=300,
        net_exposure_bps=300,
        long_exposure_bps=300,
        short_exposure_bps=0,
        cash_buffer_bps=9700,
        position_count=position_count,
        turnover_bps_assumption=300,
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
