from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime

from libraries.core import build_provenance
from libraries.schemas import (
    AssumptionMismatch,
    AssumptionMismatchKind,
    AvailabilityMismatch,
    AvailabilityMismatchKind,
    CostModel,
    ExecutionAssumption,
    ExecutionTimingRule,
    FillAssumption,
    PaperTrade,
    PortfolioProposal,
    PriceSourceKind,
    QuantityBasis,
    RealismWarning,
    RealismWarningKind,
    Severity,
    Signal,
    StrategyToPaperMapping,
    TimingAnchor,
    WorkflowScope,
)
from libraries.time import Clock, ensure_utc
from libraries.utils import make_canonical_id
from services.timing.calendar import next_us_equities_open


def build_backtest_execution_timing_rule(
    *,
    company_id: str,
    backtest_run_id: str,
    execution_assumption: ExecutionAssumption,
    clock: Clock,
    workflow_run_id: str,
    source_reference_ids: list[str],
) -> ExecutionTimingRule:
    """Build the explicit backtest-side timing rule."""

    now = clock.now()
    return ExecutionTimingRule(
        execution_timing_rule_id=make_canonical_id("xtrule", "backtest", backtest_run_id),
        workflow_scope=WorkflowScope.BACKTEST,
        rule_name="day24_backtest_daily_close_to_next_open",
        decision_anchor=TimingAnchor.SIGNAL_DECISION_CLOSE,
        eligibility_anchor=TimingAnchor.SIGNAL_ELIGIBILITY_TIME,
        execution_anchor=TimingAnchor.NEXT_SESSION_OPEN,
        requires_human_approval=False,
        execution_lag_bars=execution_assumption.execution_lag_bars,
        signal_availability_buffer_minutes=execution_assumption.signal_availability_buffer_minutes,
        notes=[
            "Backtest decisions are anchored to daily close timestamps.",
            "Execution is delayed to the next-session open using the configured lag.",
        ],
        provenance=build_provenance(
            clock=clock,
            transformation_name="day24_backtest_execution_timing_rule",
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=[
                backtest_run_id,
                execution_assumption.execution_assumption_id,
                company_id,
            ],
            workflow_run_id=workflow_run_id,
        ),
        created_at=now,
        updated_at=now,
    )


def build_backtest_fill_assumption(
    *,
    company_id: str,
    backtest_run_id: str,
    execution_assumption: ExecutionAssumption,
    clock: Clock,
    workflow_run_id: str,
    source_reference_ids: list[str],
) -> FillAssumption:
    """Build the explicit backtest-side fill assumption."""

    now = clock.now()
    return FillAssumption(
        fill_assumption_id=make_canonical_id("filla", "backtest", backtest_run_id),
        workflow_scope=WorkflowScope.BACKTEST,
        price_source_kind=PriceSourceKind.SYNTHETIC_NEXT_BAR_OPEN,
        quantity_basis=QuantityBasis.UNIT_POSITION,
        fill_delay_description=(
            f"Execute at next-session open after {execution_assumption.execution_lag_bars} daily bar(s)."
        ),
        notes=[
            "Backtest fills use synthetic next-bar open prices.",
            "Unit-position sizing is used instead of proposal notional sizing.",
        ],
        provenance=build_provenance(
            clock=clock,
            transformation_name="day24_backtest_fill_assumption",
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=[
                backtest_run_id,
                execution_assumption.execution_assumption_id,
                company_id,
            ],
            workflow_run_id=workflow_run_id,
        ),
        created_at=now,
        updated_at=now,
    )


def build_backtest_cost_model(
    *,
    company_id: str,
    backtest_run_id: str,
    execution_assumption: ExecutionAssumption,
    clock: Clock,
    workflow_run_id: str,
    source_reference_ids: list[str],
) -> CostModel:
    """Build the explicit backtest-side cost model."""

    now = clock.now()
    return CostModel(
        cost_model_id=make_canonical_id("cmodel", "backtest", backtest_run_id),
        workflow_scope=WorkflowScope.BACKTEST,
        transaction_cost_bps=execution_assumption.transaction_cost_bps,
        slippage_bps=execution_assumption.slippage_bps,
        estimate_only=True,
        notes=[
            "Backtest transaction costs and slippage are fixed basis-point assumptions.",
            "The model is deterministic and not microstructure-aware.",
        ],
        provenance=build_provenance(
            clock=clock,
            transformation_name="day24_backtest_cost_model",
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=[
                backtest_run_id,
                execution_assumption.execution_assumption_id,
                company_id,
            ],
            workflow_run_id=workflow_run_id,
        ),
        created_at=now,
        updated_at=now,
    )


def build_backtest_realism_warnings(
    *,
    backtest_run_id: str,
    company_id: str,
    clock: Clock,
    workflow_run_id: str,
    source_reference_ids: list[str],
) -> list[RealismWarning]:
    """Build explicit realism warnings attached to the backtest path."""

    return [
        _warning(
            warning_kind=RealismWarningKind.SYNTHETIC_PRICE_FIXTURE,
            severity=Severity.HIGH,
            target_id=backtest_run_id,
            message="Backtest uses a synthetic price fixture rather than market-grade execution data.",
            related_artifact_ids=[backtest_run_id, company_id],
            clock=clock,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
        ),
        _warning(
            warning_kind=RealismWarningKind.UNIT_POSITION_SIMPLIFICATION,
            severity=Severity.MEDIUM,
            target_id=backtest_run_id,
            message="Backtest uses unit-position sizing rather than proposal notional sizing.",
            related_artifact_ids=[backtest_run_id, company_id],
            clock=clock,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
        ),
        _warning(
            warning_kind=RealismWarningKind.FIXED_BPS_COSTS,
            severity=Severity.MEDIUM,
            target_id=backtest_run_id,
            message="Backtest transaction costs and slippage are fixed basis-point assumptions.",
            related_artifact_ids=[backtest_run_id, company_id],
            clock=clock,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
        ),
        _warning(
            warning_kind=RealismWarningKind.NO_INTRADAY_MICROSTRUCTURE,
            severity=Severity.MEDIUM,
            target_id=backtest_run_id,
            message="Backtest does not model intraday liquidity, queue position, or order-book microstructure.",
            related_artifact_ids=[backtest_run_id, company_id],
            clock=clock,
            workflow_run_id=workflow_run_id,
            source_reference_ids=source_reference_ids,
        ),
    ]


def build_paper_execution_timing_rule(
    *,
    portfolio_proposal: PortfolioProposal,
    trade_batch_id: str,
    clock: Clock,
    workflow_run_id: str,
) -> ExecutionTimingRule:
    """Build the explicit paper-side timing rule."""

    now = clock.now()
    return ExecutionTimingRule(
        execution_timing_rule_id=make_canonical_id("xtrule", "paper", trade_batch_id),
        workflow_scope=WorkflowScope.PAPER_TRADING,
        rule_name="day24_paper_trade_review_gated_candidate_generation",
        decision_anchor=TimingAnchor.PROPOSAL_AS_OF_TIME,
        eligibility_anchor=TimingAnchor.PROPOSAL_AS_OF_TIME,
        execution_anchor=TimingAnchor.NO_AUTOMATIC_EXECUTION,
        requires_human_approval=True,
        execution_lag_bars=None,
        signal_availability_buffer_minutes=None,
        notes=[
            "Portfolio proposal as_of_time is the research decision anchor for paper-trade candidate creation.",
            "Paper-trade candidates are generated at submitted_at but are not executed automatically.",
            "Human approval is required before any downstream simulated execution step.",
        ],
        provenance=build_provenance(
            clock=clock,
            transformation_name="day24_paper_execution_timing_rule",
            source_reference_ids=portfolio_proposal.provenance.source_reference_ids,
            upstream_artifact_ids=[
                portfolio_proposal.portfolio_proposal_id,
                *[idea.position_idea_id for idea in portfolio_proposal.position_ideas],
            ],
            workflow_run_id=workflow_run_id,
        ),
        created_at=now,
        updated_at=now,
    )


def build_paper_fill_assumption(
    *,
    portfolio_proposal: PortfolioProposal,
    proposed_trades: Sequence[PaperTrade],
    trade_batch_id: str,
    clock: Clock,
    workflow_run_id: str,
) -> FillAssumption:
    """Build the explicit paper-side fill assumption."""

    any_reference_price = any(
        trade.assumed_reference_price_usd is not None for trade in proposed_trades
    )
    any_quantity = any(trade.quantity is not None for trade in proposed_trades)
    price_source_kind = (
        PriceSourceKind.ASSUMED_REFERENCE_PRICE
        if any_reference_price
        else PriceSourceKind.NO_PRICE_MATERIALIZED
    )
    quantity_basis = (
        QuantityBasis.NOTIONAL_DIVIDED_BY_REFERENCE_PRICE
        if any_quantity
        else QuantityBasis.NOT_MATERIALIZED
    )
    now = clock.now()
    return FillAssumption(
        fill_assumption_id=make_canonical_id("filla", "paper", trade_batch_id),
        workflow_scope=WorkflowScope.PAPER_TRADING,
        price_source_kind=price_source_kind,
        quantity_basis=quantity_basis,
        fill_delay_description="No automatic fill is produced in Day 24; submitted trades remain review-facing candidates.",
        notes=[
            (
                "Assumed reference prices were supplied by the caller for quantity materialization."
                if any_reference_price
                else "No reference prices were supplied, so quantity was not materialized."
            ),
            "Paper-trade candidates do not yet flow into a simulated fill engine.",
        ],
        provenance=build_provenance(
            clock=clock,
            transformation_name="day24_paper_fill_assumption",
            source_reference_ids=portfolio_proposal.provenance.source_reference_ids,
            upstream_artifact_ids=[
                portfolio_proposal.portfolio_proposal_id,
                *[trade.paper_trade_id for trade in proposed_trades],
            ],
            workflow_run_id=workflow_run_id,
        ),
        created_at=now,
        updated_at=now,
    )


def build_paper_cost_model(
    *,
    portfolio_proposal: PortfolioProposal,
    proposed_trades: Sequence[PaperTrade],
    trade_batch_id: str,
    clock: Clock,
    workflow_run_id: str,
) -> CostModel:
    """Build the explicit paper-side cost model."""

    slippage_bps = _uniform_value([trade.slippage_bps_estimate for trade in proposed_trades])
    now = clock.now()
    return CostModel(
        cost_model_id=make_canonical_id("cmodel", "paper", trade_batch_id),
        workflow_scope=WorkflowScope.PAPER_TRADING,
        transaction_cost_bps=None,
        slippage_bps=slippage_bps,
        estimate_only=True,
        notes=[
            "Paper-trade costs remain estimate-only and do not drive a fill simulator.",
            "Transaction costs are not modeled separately in the Day 24 paper path.",
        ],
        provenance=build_provenance(
            clock=clock,
            transformation_name="day24_paper_cost_model",
            source_reference_ids=portfolio_proposal.provenance.source_reference_ids,
            upstream_artifact_ids=[
                portfolio_proposal.portfolio_proposal_id,
                *[trade.paper_trade_id for trade in proposed_trades],
            ],
            workflow_run_id=workflow_run_id,
        ),
        created_at=now,
        updated_at=now,
    )


def build_paper_realism_warnings(
    *,
    portfolio_proposal: PortfolioProposal,
    proposed_trades: Sequence[PaperTrade],
    clock: Clock,
    workflow_run_id: str,
) -> list[RealismWarning]:
    """Build explicit realism warnings attached to the paper path."""

    related_artifact_ids = [
        portfolio_proposal.portfolio_proposal_id,
        *[trade.paper_trade_id for trade in proposed_trades],
    ]
    warnings = [
        _warning(
            warning_kind=RealismWarningKind.NO_PAPER_FILL_SIMULATION,
            severity=Severity.HIGH,
            target_id=portfolio_proposal.portfolio_proposal_id,
            message="Paper-trade candidate generation does not simulate fills automatically.",
            related_artifact_ids=related_artifact_ids,
            clock=clock,
            workflow_run_id=workflow_run_id,
            source_reference_ids=portfolio_proposal.provenance.source_reference_ids,
        ),
        _warning(
            warning_kind=RealismWarningKind.ESTIMATE_ONLY_PAPER_COST_MODEL,
            severity=Severity.MEDIUM,
            target_id=portfolio_proposal.portfolio_proposal_id,
            message="Paper-side slippage and costs remain estimate-only and are not execution-grade.",
            related_artifact_ids=related_artifact_ids,
            clock=clock,
            workflow_run_id=workflow_run_id,
            source_reference_ids=portfolio_proposal.provenance.source_reference_ids,
        ),
    ]
    if any(trade.assumed_reference_price_usd is not None for trade in proposed_trades):
        warnings.append(
            _warning(
                warning_kind=RealismWarningKind.MANUAL_REFERENCE_PRICE,
                severity=Severity.MEDIUM,
                target_id=portfolio_proposal.portfolio_proposal_id,
                message="Paper-trade quantities depend on manually supplied reference prices.",
                related_artifact_ids=related_artifact_ids,
                clock=clock,
                workflow_run_id=workflow_run_id,
                source_reference_ids=portfolio_proposal.provenance.source_reference_ids,
            )
        )
    else:
        warnings.append(
            _warning(
                warning_kind=RealismWarningKind.MISSING_REFERENCE_PRICE,
                severity=Severity.MEDIUM,
                target_id=portfolio_proposal.portfolio_proposal_id,
                message="No reference prices were supplied, so paper-trade quantities were not materialized.",
                related_artifact_ids=related_artifact_ids,
                clock=clock,
                workflow_run_id=workflow_run_id,
                source_reference_ids=portfolio_proposal.provenance.source_reference_ids,
            )
        )
    return warnings


def build_approval_delay_warning(
    *,
    portfolio_proposal: PortfolioProposal,
    backtest_run_id: str | None,
    paper_trades: Sequence[PaperTrade],
    clock: Clock,
    workflow_run_id: str,
) -> RealismWarning:
    """Build an explicit warning when human approval delay is not represented in backtests."""

    return _warning(
        warning_kind=RealismWarningKind.APPROVAL_DELAY_UNMODELED,
        severity=Severity.HIGH,
        target_id=portfolio_proposal.portfolio_proposal_id,
        message="Human approval delay is not represented in the backtest execution path.",
        related_artifact_ids=[
            portfolio_proposal.portfolio_proposal_id,
            *([backtest_run_id] if backtest_run_id is not None else []),
            *[trade.paper_trade_id for trade in paper_trades],
        ],
        clock=clock,
        workflow_run_id=workflow_run_id,
        source_reference_ids=portfolio_proposal.provenance.source_reference_ids,
    )


def build_strategy_to_paper_mapping(
    *,
    company_id: str,
    backtest_run_id: str | None,
    portfolio_proposal: PortfolioProposal,
    paper_trades: Sequence[PaperTrade],
    signal_ids: list[str],
    matched_signal_family: str | None,
    matched_ablation_view: str | None,
    backtest_execution_timing_rule: ExecutionTimingRule | None,
    paper_execution_timing_rule: ExecutionTimingRule,
    backtest_fill_assumption: FillAssumption | None,
    paper_fill_assumption: FillAssumption,
    backtest_cost_model: CostModel | None,
    paper_cost_model: CostModel,
    notes: list[str],
    clock: Clock,
    workflow_run_id: str,
    source_reference_ids: list[str],
) -> StrategyToPaperMapping:
    """Build the parent mapping artifact for one comparison."""

    now = clock.now()
    return StrategyToPaperMapping(
        strategy_to_paper_mapping_id=make_canonical_id(
            "stpm",
            company_id,
            portfolio_proposal.portfolio_proposal_id,
            backtest_run_id or "no_backtest",
        ),
        company_id=company_id,
        backtest_run_id=backtest_run_id,
        portfolio_proposal_id=portfolio_proposal.portfolio_proposal_id,
        paper_trade_ids=[trade.paper_trade_id for trade in paper_trades],
        position_idea_ids=[idea.position_idea_id for idea in portfolio_proposal.position_ideas],
        signal_ids=signal_ids,
        matched_signal_family=matched_signal_family,
        matched_ablation_view=matched_ablation_view,
        backtest_execution_timing_rule_id=(
            backtest_execution_timing_rule.execution_timing_rule_id
            if backtest_execution_timing_rule is not None
            else None
        ),
        paper_execution_timing_rule_id=paper_execution_timing_rule.execution_timing_rule_id,
        backtest_fill_assumption_id=(
            backtest_fill_assumption.fill_assumption_id
            if backtest_fill_assumption is not None
            else None
        ),
        paper_fill_assumption_id=paper_fill_assumption.fill_assumption_id,
        backtest_cost_model_id=(
            backtest_cost_model.cost_model_id if backtest_cost_model is not None else None
        ),
        paper_cost_model_id=paper_cost_model.cost_model_id,
        notes=notes,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day24_strategy_to_paper_mapping",
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=[
                portfolio_proposal.portfolio_proposal_id,
                *[trade.paper_trade_id for trade in paper_trades],
                *( [backtest_run_id] if backtest_run_id is not None else [] ),
            ],
            workflow_run_id=workflow_run_id,
            notes=notes,
        ),
        created_at=now,
        updated_at=now,
    )


def detect_assumption_mismatches(
    *,
    company_id: str,
    mapping: StrategyToPaperMapping,
    backtest_execution_timing_rule: ExecutionTimingRule | None,
    paper_execution_timing_rule: ExecutionTimingRule,
    backtest_fill_assumption: FillAssumption | None,
    paper_fill_assumption: FillAssumption,
    backtest_cost_model: CostModel | None,
    paper_cost_model: CostModel,
    clock: Clock,
    workflow_run_id: str,
    source_reference_ids: list[str],
) -> list[AssumptionMismatch]:
    """Detect structured assumption mismatches between backtest and paper paths."""

    if backtest_execution_timing_rule is None or backtest_fill_assumption is None or backtest_cost_model is None:
        return []
    mismatches: list[AssumptionMismatch] = []
    if backtest_execution_timing_rule.execution_anchor is not paper_execution_timing_rule.execution_anchor:
        mismatches.append(
            _assumption_mismatch(
                mismatch_kind=AssumptionMismatchKind.EXECUTION_ANCHOR_MISMATCH,
                company_id=company_id,
                mapping=mapping,
                backtest_value_repr=backtest_execution_timing_rule.execution_anchor.value,
                paper_value_repr=paper_execution_timing_rule.execution_anchor.value,
                severity=Severity.HIGH,
                blocking=False,
                message="Backtest executes at next-session open while paper trading remains review-gated with no automatic execution anchor.",
                clock=clock,
                workflow_run_id=workflow_run_id,
                source_reference_ids=source_reference_ids,
            )
        )
    if (backtest_execution_timing_rule.execution_lag_bars or 0) != 0:
        mismatches.append(
            _assumption_mismatch(
                mismatch_kind=AssumptionMismatchKind.LAG_MISMATCH,
                company_id=company_id,
                mapping=mapping,
                backtest_value_repr=str(backtest_execution_timing_rule.execution_lag_bars),
                paper_value_repr="none",
                severity=Severity.MEDIUM,
                blocking=False,
                message="Backtest models an explicit bar-lag while paper-trade candidate generation does not yet model an execution lag.",
                clock=clock,
                workflow_run_id=workflow_run_id,
                source_reference_ids=source_reference_ids,
            )
        )
    if (
        backtest_cost_model.transaction_cost_bps != paper_cost_model.transaction_cost_bps
        or backtest_cost_model.slippage_bps != paper_cost_model.slippage_bps
    ):
        mismatches.append(
            _assumption_mismatch(
                mismatch_kind=AssumptionMismatchKind.COST_MODEL_MISMATCH,
                company_id=company_id,
                mapping=mapping,
                backtest_value_repr=(
                    f"transaction_cost_bps={backtest_cost_model.transaction_cost_bps},"
                    f"slippage_bps={backtest_cost_model.slippage_bps}"
                ),
                paper_value_repr=(
                    f"transaction_cost_bps={paper_cost_model.transaction_cost_bps},"
                    f"slippage_bps={paper_cost_model.slippage_bps}"
                ),
                severity=Severity.MEDIUM,
                blocking=False,
                message="Backtest and paper workflows do not share the same explicit cost model.",
                clock=clock,
                workflow_run_id=workflow_run_id,
                source_reference_ids=source_reference_ids,
            )
        )
    if backtest_fill_assumption.price_source_kind is not paper_fill_assumption.price_source_kind:
        mismatches.append(
            _assumption_mismatch(
                mismatch_kind=AssumptionMismatchKind.FILL_PRICE_BASIS_MISMATCH,
                company_id=company_id,
                mapping=mapping,
                backtest_value_repr=backtest_fill_assumption.price_source_kind.value,
                paper_value_repr=paper_fill_assumption.price_source_kind.value,
                severity=Severity.HIGH,
                blocking=False,
                message="Backtest uses synthetic next-bar open prices while paper trades use caller-supplied or missing reference prices.",
                clock=clock,
                workflow_run_id=workflow_run_id,
                source_reference_ids=source_reference_ids,
            )
        )
    if backtest_fill_assumption.quantity_basis is not paper_fill_assumption.quantity_basis:
        mismatches.append(
            _assumption_mismatch(
                mismatch_kind=AssumptionMismatchKind.QUANTITY_BASIS_MISMATCH,
                company_id=company_id,
                mapping=mapping,
                backtest_value_repr=backtest_fill_assumption.quantity_basis.value,
                paper_value_repr=paper_fill_assumption.quantity_basis.value,
                severity=Severity.MEDIUM,
                blocking=False,
                message="Backtest unit-position sizing does not match paper-trade notional or unmateralized quantity handling.",
                clock=clock,
                workflow_run_id=workflow_run_id,
                source_reference_ids=source_reference_ids,
            )
        )
    if backtest_execution_timing_rule.requires_human_approval is not paper_execution_timing_rule.requires_human_approval:
        mismatches.append(
            _assumption_mismatch(
                mismatch_kind=AssumptionMismatchKind.APPROVAL_REQUIREMENT_MISMATCH,
                company_id=company_id,
                mapping=mapping,
                backtest_value_repr=str(backtest_execution_timing_rule.requires_human_approval).lower(),
                paper_value_repr=str(paper_execution_timing_rule.requires_human_approval).lower(),
                severity=Severity.HIGH,
                blocking=False,
                message="Paper trading requires explicit human approval while backtests do not model that delay.",
                clock=clock,
                workflow_run_id=workflow_run_id,
                source_reference_ids=source_reference_ids,
            )
        )
    return mismatches


def detect_availability_mismatches(
    *,
    company_id: str,
    mapping: StrategyToPaperMapping,
    portfolio_proposal: PortfolioProposal,
    paper_trades: Sequence[PaperTrade],
    signals_by_id: Mapping[str, Signal],
    backtest_run_decision_cutoff_time: datetime | None,
    proposal_review_decided_at: datetime | None,
    clock: Clock,
    workflow_run_id: str,
    source_reference_ids: list[str],
) -> list[AvailabilityMismatch]:
    """Detect structured timing mismatches between compared workflows."""

    mismatches: list[AvailabilityMismatch] = []
    signal_effective_times = [
        ensure_utc(signal.effective_at)
        for signal_id in mapping.signal_ids
        if (signal := signals_by_id.get(signal_id)) is not None
    ]
    latest_signal_effective_at = max(signal_effective_times, default=None)
    if latest_signal_effective_at is not None and ensure_utc(portfolio_proposal.as_of_time) < latest_signal_effective_at:
        mismatches.append(
            _availability_mismatch(
                mismatch_kind=AvailabilityMismatchKind.PROPOSAL_BEFORE_SIGNAL_EFFECTIVE_AT,
                company_id=company_id,
                mapping=mapping,
                required_time=latest_signal_effective_at,
                observed_time=ensure_utc(portfolio_proposal.as_of_time),
                severity=Severity.CRITICAL,
                blocking=True,
                message="Portfolio proposal as_of_time precedes the effective time of its selected signal set.",
                clock=clock,
                workflow_run_id=workflow_run_id,
                source_reference_ids=source_reference_ids,
            )
        )
    for trade in paper_trades:
        position_signal_id = next(
            (
                idea.signal_id
                for idea in portfolio_proposal.position_ideas
                if idea.position_idea_id == trade.position_idea_id
            ),
            None,
        )
        signal = signals_by_id.get(position_signal_id) if position_signal_id is not None else None
        if signal is None:
            continue
        signal_effective_at = ensure_utc(signal.effective_at)
        submitted_at = ensure_utc(trade.submitted_at)
        if submitted_at < signal_effective_at:
            mismatches.append(
                _availability_mismatch(
                    mismatch_kind=AvailabilityMismatchKind.TRADE_SUBMITTED_BEFORE_SIGNAL_EFFECTIVE_AT,
                    company_id=company_id,
                    mapping=mapping,
                    required_time=signal_effective_at,
                    observed_time=submitted_at,
                    severity=Severity.HIGH,
                    blocking=True,
                    message="Paper-trade submission preceded the effective time of the linked signal.",
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                )
            )
    if proposal_review_decided_at is not None:
        earliest_backtest_execution = next_us_equities_open(
            timestamp=ensure_utc(portfolio_proposal.as_of_time).replace(tzinfo=UTC),
        )
        if ensure_utc(proposal_review_decided_at) > earliest_backtest_execution:
            mismatches.append(
                _availability_mismatch(
                    mismatch_kind=AvailabilityMismatchKind.APPROVAL_AFTER_BACKTEST_EXECUTION_WINDOW,
                    company_id=company_id,
                    mapping=mapping,
                    required_time=earliest_backtest_execution,
                    observed_time=ensure_utc(proposal_review_decided_at),
                    severity=Severity.HIGH,
                    blocking=False,
                    message="Human approval occurred after the earliest backtest-style execution window.",
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                    source_reference_ids=source_reference_ids,
                )
            )
    if (
        latest_signal_effective_at is not None
        and backtest_run_decision_cutoff_time is not None
        and latest_signal_effective_at > ensure_utc(backtest_run_decision_cutoff_time)
    ):
        mismatches.append(
            _availability_mismatch(
                mismatch_kind=AvailabilityMismatchKind.BACKTEST_TIMING_INCONSISTENCY,
                company_id=company_id,
                mapping=mapping,
                required_time=latest_signal_effective_at,
                observed_time=ensure_utc(backtest_run_decision_cutoff_time),
                severity=Severity.HIGH,
                blocking=True,
                message="Mapped signal effective time exceeds the recorded backtest decision cutoff window.",
                clock=clock,
                workflow_run_id=workflow_run_id,
                source_reference_ids=source_reference_ids,
            )
        )
    return mismatches


def highest_severity(
    *,
    mismatches: Sequence[AssumptionMismatch | AvailabilityMismatch],
    warnings: Sequence[RealismWarning],
) -> Severity:
    """Return the highest observed severity across mismatches and warnings."""

    severities = [item.severity for item in [*mismatches, *warnings]]
    if not severities:
        return Severity.INFO
    return max(severities, key=_severity_rank)


def build_reconciliation_summary(
    *,
    mismatches: Sequence[AssumptionMismatch | AvailabilityMismatch],
    warnings: Sequence[RealismWarning],
) -> str:
    """Build a compact reconciliation summary string."""

    return (
        f"{len(mismatches)} mismatch(es), {len(warnings)} realism warning(s), "
        f"highest_severity={highest_severity(mismatches=mismatches, warnings=warnings).value}."
    )


def _assumption_mismatch(
    *,
    mismatch_kind: AssumptionMismatchKind,
    company_id: str,
    mapping: StrategyToPaperMapping,
    backtest_value_repr: str,
    paper_value_repr: str,
    severity: Severity,
    blocking: bool,
    message: str,
    clock: Clock,
    workflow_run_id: str,
    source_reference_ids: list[str],
) -> AssumptionMismatch:
    now = clock.now()
    return AssumptionMismatch(
        assumption_mismatch_id=make_canonical_id(
            "amismatch",
            company_id,
            mapping.strategy_to_paper_mapping_id,
            mismatch_kind.value,
        ),
        mismatch_kind=mismatch_kind,
        backtest_value_repr=backtest_value_repr,
        paper_value_repr=paper_value_repr,
        severity=severity,
        blocking=blocking,
        message=message,
        related_artifact_ids=[
            mapping.strategy_to_paper_mapping_id,
            mapping.portfolio_proposal_id,
            *( [mapping.backtest_run_id] if mapping.backtest_run_id is not None else [] ),
            *mapping.paper_trade_ids,
        ],
        provenance=build_provenance(
            clock=clock,
            transformation_name="day24_assumption_mismatch_detection",
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=[
                mapping.strategy_to_paper_mapping_id,
                mapping.portfolio_proposal_id,
                *( [mapping.backtest_run_id] if mapping.backtest_run_id is not None else [] ),
            ],
            workflow_run_id=workflow_run_id,
        ),
        created_at=now,
        updated_at=now,
    )


def _availability_mismatch(
    *,
    mismatch_kind: AvailabilityMismatchKind,
    company_id: str,
    mapping: StrategyToPaperMapping,
    required_time: datetime | None,
    observed_time: datetime | None,
    severity: Severity,
    blocking: bool,
    message: str,
    clock: Clock,
    workflow_run_id: str,
    source_reference_ids: list[str],
) -> AvailabilityMismatch:
    now = clock.now()
    return AvailabilityMismatch(
        availability_mismatch_id=make_canonical_id(
            "vmismatch",
            company_id,
            mapping.strategy_to_paper_mapping_id,
            mismatch_kind.value,
        ),
        mismatch_kind=mismatch_kind,
        required_time=required_time,
        observed_time=observed_time,
        severity=severity,
        blocking=blocking,
        message=message,
        related_artifact_ids=[
            mapping.strategy_to_paper_mapping_id,
            mapping.portfolio_proposal_id,
            *( [mapping.backtest_run_id] if mapping.backtest_run_id is not None else [] ),
            *mapping.paper_trade_ids,
        ],
        provenance=build_provenance(
            clock=clock,
            transformation_name="day24_availability_mismatch_detection",
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=[
                mapping.strategy_to_paper_mapping_id,
                mapping.portfolio_proposal_id,
                *( [mapping.backtest_run_id] if mapping.backtest_run_id is not None else [] ),
            ],
            workflow_run_id=workflow_run_id,
        ),
        created_at=now,
        updated_at=now,
    )


def _warning(
    *,
    warning_kind: RealismWarningKind,
    severity: Severity,
    target_id: str,
    message: str,
    related_artifact_ids: list[str],
    clock: Clock,
    workflow_run_id: str,
    source_reference_ids: list[str],
) -> RealismWarning:
    now = clock.now()
    return RealismWarning(
        realism_warning_id=make_canonical_id("rwarn", target_id, warning_kind.value),
        warning_kind=warning_kind,
        severity=severity,
        message=message,
        related_artifact_ids=related_artifact_ids,
        provenance=build_provenance(
            clock=clock,
            transformation_name="day24_realism_warning",
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=related_artifact_ids,
            workflow_run_id=workflow_run_id,
        ),
        created_at=now,
        updated_at=now,
    )


def _severity_rank(severity: Severity) -> int:
    order = {
        Severity.INFO: 0,
        Severity.LOW: 1,
        Severity.MEDIUM: 2,
        Severity.HIGH: 3,
        Severity.CRITICAL: 4,
    }
    return order[severity]


def _uniform_value(values: Sequence[float | None]) -> float | None:
    non_null = [value for value in values if value is not None]
    if not non_null:
        return None
    if len(set(non_null)) == 1:
        return non_null[0]
    return max(non_null)
