from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from libraries.schemas import (
    ConstraintResult,
    ConstraintSet,
    ConstructionDecision,
    PortfolioSelectionSummary,
    PositionSizingRationale,
    ProposalRejectionReason,
    RiskCheckStatus,
    SelectionConflict,
    SelectionRule,
)
from libraries.schemas.base import ProvenanceRecord

FIXED_NOW = datetime(2026, 3, 22, 10, 0, tzinfo=UTC)


def test_selection_rule_requires_name_stage_and_description() -> None:
    with pytest.raises(ValidationError):
        SelectionRule(
            selection_rule_id="selrule_test",
            rule_name="",
            rule_stage="candidate_intake",
            description="Directional signals only.",
            active=True,
            notes=[],
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_constraint_result_requires_unit_when_numeric_values_exist() -> None:
    with pytest.raises(ValidationError):
        ConstraintResult(
            constraint_result_id="cresult_test",
            constraint_set_id="constraintset_test",
            subject_type="candidate_signal",
            subject_id="sig_test",
            portfolio_constraint_id="constraint_test",
            status=RiskCheckStatus.FAIL,
            binding=True,
            observed_value=1600.0,
            limit_value=1500.0,
            headroom_value=-100.0,
            unit=None,
            message="Gross limit breached.",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_position_sizing_rationale_requires_final_weight_not_above_base_or_max() -> None:
    with pytest.raises(ValidationError):
        PositionSizingRationale(
            position_sizing_rationale_id="psize_test",
            position_idea_id="idea_test",
            signal_id="sig_test",
            base_weight_bps=300,
            final_weight_bps=400,
            max_weight_bps=350,
            sizing_rule_name="base_weight_from_signal_maturity",
            binding_constraint_ids=[],
            assumptions=[],
            summary="Invalid sizing rationale.",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_rejected_construction_decision_requires_explicit_rejection_reasons() -> None:
    with pytest.raises(ValidationError):
        ConstructionDecision(
            construction_decision_id="cdecision_test",
            portfolio_selection_summary_id="psummary_test",
            company_id="co_test",
            signal_id="sig_test",
            decision_outcome="rejected",
            position_idea_id=None,
            position_sizing_rationale_id=None,
            selection_rule_ids=["selrule_test"],
            constraint_result_ids=[],
            proposal_rejection_reasons=[],
            assumptions=[],
            summary="Rejected candidate.",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_portfolio_selection_summary_requires_rule_ids_and_summary() -> None:
    with pytest.raises(ValidationError):
        PortfolioSelectionSummary(
            portfolio_selection_summary_id="psummary_test",
            portfolio_proposal_id="proposal_test",
            company_id="co_test",
            constraint_set_id="constraintset_test",
            selection_rule_ids=[],
            construction_decision_ids=[],
            selection_conflict_ids=[],
            candidate_signal_ids=[],
            included_signal_ids=[],
            included_position_idea_ids=[],
            rejected_signal_ids=[],
            binding_constraint_ids=[],
            assumptions=[],
            summary="",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_selection_conflict_requires_multiple_candidates() -> None:
    with pytest.raises(ValidationError):
        SelectionConflict(
            selection_conflict_id="sconflict_test",
            portfolio_selection_summary_id="psummary_test",
            company_id="co_test",
            conflict_kind="same_company_candidate_competition",
            candidate_signal_ids=["sig_test"],
            resolved_in_favor_of_signal_id=None,
            summary="One-candidate conflict is invalid.",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_constraint_set_and_rejection_reason_validate_visible_fields() -> None:
    constraint_set = ConstraintSet(
        constraint_set_id="constraintset_test",
        portfolio_proposal_id="proposal_test",
        portfolio_constraint_ids=["constraint_test"],
        selection_rule_ids=["selrule_test"],
        assumptions=["flat_start_turnover_assumption"],
        summary="Applied one deterministic rule set.",
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    rejection_reason = ProposalRejectionReason(
        reason_code="portfolio_constraint_breach",
        message="Projected gross exposure breached the hard limit.",
        blocking=True,
        related_constraint_ids=["constraint_test"],
        related_artifact_ids=["cresult_test"],
    )

    assert constraint_set.portfolio_proposal_id == "proposal_test"
    assert rejection_reason.reason_code == "portfolio_constraint_breach"


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(processing_time=FIXED_NOW)
