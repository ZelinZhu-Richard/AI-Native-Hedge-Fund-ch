from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    DailyPaperSummary,
    OutcomeAttribution,
    PaperPositionState,
    PaperPositionStateStatus,
    PnLPlaceholder,
    PositionSide,
    RiskWarningRelevance,
    ThesisAssessment,
    TradeOutcome,
)
from libraries.schemas.base import ProvenanceRecord

FIXED_NOW = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)


def test_complete_pnl_placeholder_requires_prices_and_pnl_values() -> None:
    with pytest.raises(ValidationError):
        PnLPlaceholder(
            entry_reference_price_usd=None,
            current_or_exit_price_usd=105.0,
            unrealized_pnl_usd=30.0,
            realized_pnl_usd=None,
            complete=True,
            calculation_basis="side_aware_reference_mark",
            notes=[],
        )


def test_terminal_paper_position_state_requires_closed_at() -> None:
    with pytest.raises(ValidationError):
        PaperPositionState(
            paper_position_state_id="ppos_test",
            paper_trade_id="trade_test",
            portfolio_proposal_id="proposal_test",
            position_idea_id="idea_test",
            signal_id="sig_test",
            company_id="co_test",
            symbol="TEST",
            side=PositionSide.LONG,
            state=PaperPositionStateStatus.CLOSED,
            opened_at=FIXED_NOW,
            closed_at=None,
            quantity=10.0,
            entry_reference_price_usd=100.0,
            latest_reference_price_usd=105.0,
            latest_pnl_placeholder=None,
            latest_lifecycle_event_id=None,
            latest_ledger_entry_id=None,
            review_followup_ids=[],
            trade_outcome_ids=[],
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_daily_paper_summary_counts_must_match_position_lists() -> None:
    with pytest.raises(ValidationError):
        DailyPaperSummary(
            daily_paper_summary_id="pday_test",
            summary_date=date(2026, 3, 22),
            open_position_state_ids=["ppos_open"],
            closed_position_state_ids=[],
            cancelled_position_state_ids=[],
            lifecycle_event_ids=[],
            trade_outcome_ids=[],
            open_review_followup_ids=[],
            open_position_count=0,
            closed_position_count=0,
            cancelled_position_count=0,
            aggregate_pnl_placeholder=None,
            notes=[],
            summary="Mismatched counts should fail.",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_trade_outcome_and_outcome_attribution_validate_required_linkage() -> None:
    outcome = TradeOutcome(
        trade_outcome_id="tout_test",
        paper_position_state_id="ppos_test",
        paper_trade_id="trade_test",
        thesis_assessment=ThesisAssessment.HELD,
        risk_warning_relevance=RiskWarningRelevance.NOT_OBSERVED,
        assumption_notes=["Reference-price-only outcome assessment."],
        learning_notes=["Keep the research summary concise."],
        pnl_placeholder=None,
        summary="Outcome recorded for test coverage.",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    attribution = OutcomeAttribution(
        outcome_attribution_id="oattr_test",
        trade_outcome_id=outcome.trade_outcome_id,
        paper_position_state_id="ppos_test",
        paper_trade_id="trade_test",
        portfolio_proposal_id="proposal_test",
        position_idea_id="idea_test",
        signal_id="sig_test",
        research_artifact_ids=["brief_test"],
        feature_ids=["feat_test"],
        portfolio_selection_summary_id="psummary_test",
        construction_decision_id="cdecision_test",
        position_sizing_rationale_id="psize_test",
        risk_check_ids=["risk_test"],
        review_decision_ids=["review_test"],
        review_note_ids=["rnote_test"],
        strategy_to_paper_mapping_id="spmap_test",
        reconciliation_report_id="rreport_test",
        summary="Outcome linked back through the research and proposal chain.",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    assert outcome.thesis_assessment is ThesisAssessment.HELD
    assert attribution.signal_id == "sig_test"


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
