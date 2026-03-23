from __future__ import annotations

from datetime import UTC, datetime

import pytest

from libraries.schemas import (
    AssumptionMismatch,
    AssumptionMismatchKind,
    AvailabilityMismatch,
    AvailabilityMismatchKind,
    CostModel,
    ExecutionTimingRule,
    FillAssumption,
    PriceSourceKind,
    ProvenanceRecord,
    QuantityBasis,
    RealismWarning,
    RealismWarningKind,
    ReconciliationReport,
    Severity,
    StrategyToPaperMapping,
    TimingAnchor,
    WorkflowScope,
)

FIXED_NOW = datetime(2026, 3, 22, 12, 0, tzinfo=UTC)


def _provenance() -> ProvenanceRecord:
    return ProvenanceRecord(
        source_reference_ids=["src_test"],
        upstream_artifact_ids=["artifact_test"],
        transformation_name="unit_test",
        processing_time=FIXED_NOW,
    )


def test_execution_timing_rule_requires_rule_name() -> None:
    with pytest.raises(ValueError, match="rule_name must be non-empty"):
        ExecutionTimingRule(
            execution_timing_rule_id="xtrule_test",
            workflow_scope=WorkflowScope.BACKTEST,
            rule_name="",
            decision_anchor=TimingAnchor.SIGNAL_DECISION_CLOSE,
            eligibility_anchor=TimingAnchor.SIGNAL_ELIGIBILITY_TIME,
            execution_anchor=TimingAnchor.NEXT_SESSION_OPEN,
            requires_human_approval=False,
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_fill_assumption_requires_delay_description() -> None:
    with pytest.raises(ValueError, match="fill_delay_description must be non-empty"):
        FillAssumption(
            fill_assumption_id="filla_test",
            workflow_scope=WorkflowScope.PAPER_TRADING,
            price_source_kind=PriceSourceKind.NO_PRICE_MATERIALIZED,
            quantity_basis=QuantityBasis.NOT_MATERIALIZED,
            fill_delay_description="",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_strategy_to_paper_mapping_requires_paper_side_linkage() -> None:
    with pytest.raises(ValueError, match="paper_execution_timing_rule_id must be non-empty"):
        StrategyToPaperMapping(
            strategy_to_paper_mapping_id="stpm_test",
            company_id="co_test",
            backtest_run_id="btrun_test",
            portfolio_proposal_id="proposal_test",
            paper_trade_ids=[],
            position_idea_ids=["idea_test"],
            signal_ids=["sig_test"],
            matched_signal_family="text_only_candidate_signal",
            matched_ablation_view="text_only",
            backtest_execution_timing_rule_id="xtrule_backtest",
            paper_execution_timing_rule_id="",
            backtest_fill_assumption_id="filla_backtest",
            paper_fill_assumption_id="filla_paper",
            backtest_cost_model_id="cmodel_backtest",
            paper_cost_model_id="cmodel_paper",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_reconciliation_report_requires_summary_and_mapping() -> None:
    with pytest.raises(ValueError, match="summary must be non-empty"):
        ReconciliationReport(
            reconciliation_report_id="rreport_test",
            company_id="co_test",
            strategy_to_paper_mapping_id="stpm_test",
            assumption_mismatch_ids=[],
            availability_mismatch_ids=[],
            realism_warning_ids=[],
            highest_severity=Severity.INFO,
            internally_consistent=True,
            review_required=False,
            summary="",
            provenance=_provenance(),
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )


def test_mismatch_and_warning_models_preserve_structured_fields() -> None:
    assumption_mismatch = AssumptionMismatch(
        assumption_mismatch_id="amismatch_test",
        mismatch_kind=AssumptionMismatchKind.COST_MODEL_MISMATCH,
        backtest_value_repr="transaction_cost_bps=5.0,slippage_bps=2.0",
        paper_value_repr="transaction_cost_bps=None,slippage_bps=5.0",
        severity=Severity.MEDIUM,
        blocking=False,
        message="Backtest and paper workflows do not share the same explicit cost model.",
        related_artifact_ids=["btrun_test", "proposal_test"],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    availability_mismatch = AvailabilityMismatch(
        availability_mismatch_id="vmismatch_test",
        mismatch_kind=AvailabilityMismatchKind.PROPOSAL_BEFORE_SIGNAL_EFFECTIVE_AT,
        required_time=FIXED_NOW,
        observed_time=FIXED_NOW,
        severity=Severity.CRITICAL,
        blocking=True,
        message="Portfolio proposal as_of_time precedes its signal effective time.",
        related_artifact_ids=["proposal_test", "sig_test"],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    realism_warning = RealismWarning(
        realism_warning_id="rwarn_test",
        warning_kind=RealismWarningKind.NO_PAPER_FILL_SIMULATION,
        severity=Severity.HIGH,
        message="Paper-trade candidate generation does not simulate fills automatically.",
        related_artifact_ids=["proposal_test"],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )
    cost_model = CostModel(
        cost_model_id="cmodel_test",
        workflow_scope=WorkflowScope.PAPER_TRADING,
        transaction_cost_bps=None,
        slippage_bps=5.0,
        estimate_only=True,
        notes=["estimate_only"],
        provenance=_provenance(),
        created_at=FIXED_NOW,
        updated_at=FIXED_NOW,
    )

    assert assumption_mismatch.mismatch_kind is AssumptionMismatchKind.COST_MODEL_MISMATCH
    assert availability_mismatch.blocking is True
    assert realism_warning.warning_kind is RealismWarningKind.NO_PAPER_FILL_SIMULATION
    assert cost_model.workflow_scope is WorkflowScope.PAPER_TRADING
