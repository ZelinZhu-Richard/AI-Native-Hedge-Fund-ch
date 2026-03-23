from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import Field

from libraries.core import load_local_models
from libraries.schemas import (
    AssumptionMismatch,
    AuditLog,
    AvailabilityMismatch,
    ConstraintResult,
    ConstraintSet,
    ConstructionDecision,
    CostModel,
    CounterHypothesis,
    EvidenceAssessment,
    ExecutionTimingRule,
    FillAssumption,
    Hypothesis,
    PaperTrade,
    PortfolioAttribution,
    PortfolioProposal,
    PortfolioSelectionSummary,
    PositionAttribution,
    PositionIdea,
    PositionSizingRationale,
    RealismWarning,
    ReconciliationReport,
    ResearchBrief,
    ReviewAssignment,
    ReviewDecision,
    ReviewNote,
    ReviewQueueItem,
    ReviewTargetType,
    SelectionConflict,
    Signal,
    StrategyToPaperMapping,
    StressTestResult,
    StressTestRun,
    StrictModel,
)
from libraries.schemas.base import TimestampedModel

T = TypeVar("T", bound=TimestampedModel)


class LoadedReviewWorkspace(StrictModel):
    """Typed bundle of persisted artifacts used to build review queue state and context."""

    research_briefs_by_id: dict[str, ResearchBrief] = Field(default_factory=dict)
    hypotheses_by_id: dict[str, Hypothesis] = Field(default_factory=dict)
    counter_hypotheses_by_id: dict[str, CounterHypothesis] = Field(default_factory=dict)
    evidence_assessments_by_id: dict[str, EvidenceAssessment] = Field(default_factory=dict)
    signals_by_id: dict[str, Signal] = Field(default_factory=dict)
    portfolio_proposals_by_id: dict[str, PortfolioProposal] = Field(default_factory=dict)
    paper_trades_by_id: dict[str, PaperTrade] = Field(default_factory=dict)
    position_ideas_by_id: dict[str, PositionIdea] = Field(default_factory=dict)
    constraint_sets_by_id: dict[str, ConstraintSet] = Field(default_factory=dict)
    constraint_results_by_id: dict[str, ConstraintResult] = Field(default_factory=dict)
    position_sizing_rationales_by_id: dict[str, PositionSizingRationale] = Field(default_factory=dict)
    construction_decisions_by_id: dict[str, ConstructionDecision] = Field(default_factory=dict)
    selection_conflicts_by_id: dict[str, SelectionConflict] = Field(default_factory=dict)
    portfolio_selection_summaries_by_id: dict[str, PortfolioSelectionSummary] = Field(
        default_factory=dict
    )
    portfolio_attributions_by_id: dict[str, PortfolioAttribution] = Field(default_factory=dict)
    position_attributions_by_id: dict[str, PositionAttribution] = Field(default_factory=dict)
    stress_test_runs_by_id: dict[str, StressTestRun] = Field(default_factory=dict)
    stress_test_results_by_id: dict[str, StressTestResult] = Field(default_factory=dict)
    execution_timing_rules_by_id: dict[str, ExecutionTimingRule] = Field(default_factory=dict)
    fill_assumptions_by_id: dict[str, FillAssumption] = Field(default_factory=dict)
    cost_models_by_id: dict[str, CostModel] = Field(default_factory=dict)
    strategy_to_paper_mappings_by_id: dict[str, StrategyToPaperMapping] = Field(default_factory=dict)
    reconciliation_reports_by_id: dict[str, ReconciliationReport] = Field(default_factory=dict)
    assumption_mismatches_by_id: dict[str, AssumptionMismatch] = Field(default_factory=dict)
    availability_mismatches_by_id: dict[str, AvailabilityMismatch] = Field(default_factory=dict)
    realism_warnings_by_id: dict[str, RealismWarning] = Field(default_factory=dict)
    queue_items_by_target_key: dict[str, ReviewQueueItem] = Field(default_factory=dict)
    review_notes_by_id: dict[str, ReviewNote] = Field(default_factory=dict)
    review_notes_by_target_key: dict[str, list[ReviewNote]] = Field(default_factory=dict)
    review_decisions_by_id: dict[str, ReviewDecision] = Field(default_factory=dict)
    review_decisions_by_target_key: dict[str, list[ReviewDecision]] = Field(default_factory=dict)
    review_assignments_by_id: dict[str, ReviewAssignment] = Field(default_factory=dict)
    audit_logs_by_target_key: dict[str, list[AuditLog]] = Field(default_factory=dict)


def load_review_workspace(
    *,
    research_root: Path,
    signal_root: Path,
    portfolio_root: Path,
    review_root: Path,
    audit_root: Path,
    portfolio_analysis_root: Path | None = None,
    reconciliation_root: Path | None = None,
) -> LoadedReviewWorkspace:
    """Load persisted reviewable artifacts and review metadata."""

    research_briefs = _load_models(research_root / "research_briefs", ResearchBrief)
    hypotheses = _load_models(research_root / "hypotheses", Hypothesis)
    counter_hypotheses = _load_models(research_root / "counter_hypotheses", CounterHypothesis)
    evidence_assessments = _load_models(research_root / "evidence_assessments", EvidenceAssessment)
    signals = _load_models(signal_root / "signals", Signal)
    portfolio_proposals = _load_models(portfolio_root / "portfolio_proposals", PortfolioProposal)
    paper_trades = _load_models(portfolio_root / "paper_trades", PaperTrade)
    position_ideas = _load_models(portfolio_root / "position_ideas", PositionIdea)
    constraint_sets = _load_models(portfolio_root / "constraint_sets", ConstraintSet)
    constraint_results = _load_models(portfolio_root / "constraint_results", ConstraintResult)
    position_sizing_rationales = _load_models(
        portfolio_root / "position_sizing_rationales", PositionSizingRationale
    )
    construction_decisions = _load_models(
        portfolio_root / "construction_decisions", ConstructionDecision
    )
    selection_conflicts = _load_models(portfolio_root / "selection_conflicts", SelectionConflict)
    portfolio_selection_summaries = _load_models(
        portfolio_root / "portfolio_selection_summaries", PortfolioSelectionSummary
    )
    portfolio_attributions = (
        _load_models(portfolio_analysis_root / "portfolio_attributions", PortfolioAttribution)
        if portfolio_analysis_root is not None
        else []
    )
    position_attributions = (
        _load_models(portfolio_analysis_root / "position_attributions", PositionAttribution)
        if portfolio_analysis_root is not None
        else []
    )
    stress_test_runs = (
        _load_models(portfolio_analysis_root / "stress_test_runs", StressTestRun)
        if portfolio_analysis_root is not None
        else []
    )
    stress_test_results = (
        _load_models(portfolio_analysis_root / "stress_test_results", StressTestResult)
        if portfolio_analysis_root is not None
        else []
    )
    execution_timing_rules = (
        _load_models(reconciliation_root / "execution_timing_rules", ExecutionTimingRule)
        if reconciliation_root is not None
        else []
    )
    fill_assumptions = (
        _load_models(reconciliation_root / "fill_assumptions", FillAssumption)
        if reconciliation_root is not None
        else []
    )
    cost_models = (
        _load_models(reconciliation_root / "cost_models", CostModel)
        if reconciliation_root is not None
        else []
    )
    strategy_to_paper_mappings = (
        _load_models(reconciliation_root / "strategy_to_paper_mappings", StrategyToPaperMapping)
        if reconciliation_root is not None
        else []
    )
    reconciliation_reports = (
        _load_models(reconciliation_root / "reconciliation_reports", ReconciliationReport)
        if reconciliation_root is not None
        else []
    )
    assumption_mismatches = (
        _load_models(reconciliation_root / "assumption_mismatches", AssumptionMismatch)
        if reconciliation_root is not None
        else []
    )
    availability_mismatches = (
        _load_models(reconciliation_root / "availability_mismatches", AvailabilityMismatch)
        if reconciliation_root is not None
        else []
    )
    realism_warnings = (
        _load_models(reconciliation_root / "realism_warnings", RealismWarning)
        if reconciliation_root is not None
        else []
    )
    queue_items = _load_models(review_root / "queue_items", ReviewQueueItem)
    review_notes = _load_models(review_root / "review_notes", ReviewNote)
    review_assignments = _load_models(review_root / "review_assignments", ReviewAssignment)
    review_decisions = _load_review_decisions(review_root=review_root, portfolio_root=portfolio_root)
    audit_logs = _load_models(audit_root / "audit_logs", AuditLog)

    return LoadedReviewWorkspace(
        research_briefs_by_id={brief.research_brief_id: brief for brief in research_briefs},
        hypotheses_by_id={hypothesis.hypothesis_id: hypothesis for hypothesis in hypotheses},
        counter_hypotheses_by_id={
            counter_hypothesis.counter_hypothesis_id: counter_hypothesis
            for counter_hypothesis in counter_hypotheses
        },
        evidence_assessments_by_id={
            assessment.evidence_assessment_id: assessment for assessment in evidence_assessments
        },
        signals_by_id={signal.signal_id: signal for signal in signals},
        portfolio_proposals_by_id={
            proposal.portfolio_proposal_id: proposal for proposal in portfolio_proposals
        },
        paper_trades_by_id={paper_trade.paper_trade_id: paper_trade for paper_trade in paper_trades},
        position_ideas_by_id={idea.position_idea_id: idea for idea in position_ideas},
        constraint_sets_by_id={
            constraint_set.constraint_set_id: constraint_set for constraint_set in constraint_sets
        },
        constraint_results_by_id={
            constraint_result.constraint_result_id: constraint_result
            for constraint_result in constraint_results
        },
        position_sizing_rationales_by_id={
            rationale.position_sizing_rationale_id: rationale
            for rationale in position_sizing_rationales
        },
        construction_decisions_by_id={
            decision.construction_decision_id: decision for decision in construction_decisions
        },
        selection_conflicts_by_id={
            conflict.selection_conflict_id: conflict for conflict in selection_conflicts
        },
        portfolio_selection_summaries_by_id={
            summary.portfolio_selection_summary_id: summary
            for summary in portfolio_selection_summaries
        },
        portfolio_attributions_by_id={
            attribution.portfolio_attribution_id: attribution
            for attribution in portfolio_attributions
        },
        position_attributions_by_id={
            attribution.position_attribution_id: attribution
            for attribution in position_attributions
        },
        stress_test_runs_by_id={
            stress_test_run.stress_test_run_id: stress_test_run
            for stress_test_run in stress_test_runs
        },
        stress_test_results_by_id={
            stress_test_result.stress_test_result_id: stress_test_result
            for stress_test_result in stress_test_results
        },
        execution_timing_rules_by_id={
            rule.execution_timing_rule_id: rule for rule in execution_timing_rules
        },
        fill_assumptions_by_id={
            assumption.fill_assumption_id: assumption for assumption in fill_assumptions
        },
        cost_models_by_id={cost_model.cost_model_id: cost_model for cost_model in cost_models},
        strategy_to_paper_mappings_by_id={
            mapping.strategy_to_paper_mapping_id: mapping for mapping in strategy_to_paper_mappings
        },
        reconciliation_reports_by_id={
            report.reconciliation_report_id: report for report in reconciliation_reports
        },
        assumption_mismatches_by_id={
            mismatch.assumption_mismatch_id: mismatch for mismatch in assumption_mismatches
        },
        availability_mismatches_by_id={
            mismatch.availability_mismatch_id: mismatch for mismatch in availability_mismatches
        },
        realism_warnings_by_id={warning.realism_warning_id: warning for warning in realism_warnings},
        queue_items_by_target_key={
            target_key(item.target_type, item.target_id): item for item in queue_items
        },
        review_notes_by_id={note.review_note_id: note for note in review_notes},
        review_notes_by_target_key=_group_by_target(review_notes),
        review_decisions_by_id={
            review_decision.review_decision_id: review_decision for review_decision in review_decisions
        },
        review_decisions_by_target_key=_group_by_target(review_decisions),
        review_assignments_by_id={
            assignment.review_assignment_id: assignment for assignment in review_assignments
        },
        audit_logs_by_target_key=_group_audit_logs_by_target(audit_logs),
    )


def target_key(target_type: ReviewTargetType | str, target_id: str) -> str:
    """Create a stable target key for review metadata lookup."""

    resolved_target_type = target_type.value if isinstance(target_type, ReviewTargetType) else target_type
    return f"{resolved_target_type}::{target_id}"


def load_review_queue_items(review_root: Path) -> list[ReviewQueueItem]:
    """Load persisted review queue items."""

    return _load_models(review_root / "queue_items", ReviewQueueItem)


def _load_review_decisions(*, review_root: Path, portfolio_root: Path) -> list[ReviewDecision]:
    """Load review decisions from the generic review root and the legacy portfolio location."""

    primary = {
        decision.review_decision_id: decision
        for decision in _load_models(review_root / "review_decisions", ReviewDecision)
    }
    for decision in _load_models(portfolio_root / "review_decisions", ReviewDecision):
        primary.setdefault(decision.review_decision_id, decision)
    return list(primary.values())


def _load_models(directory: Path, model_cls: type[T]) -> list[T]:
    """Load JSON models from one category directory."""

    return load_local_models(directory, model_cls)


TReviewArtifact = TypeVar("TReviewArtifact", ReviewNote, ReviewDecision)


def _group_by_target(models: list[TReviewArtifact]) -> dict[str, list[TReviewArtifact]]:
    """Group target-scoped review artifacts by target type and identifier."""

    grouped: dict[str, list[TReviewArtifact]] = {}
    for model in models:
        key = target_key(model.target_type, model.target_id)
        grouped.setdefault(key, []).append(model)
    for target_models in grouped.values():
        target_models.sort(key=lambda model: model.created_at)
    return grouped


def _group_audit_logs_by_target(audit_logs: list[AuditLog]) -> dict[str, list[AuditLog]]:
    """Group audit logs by target type and identifier."""

    grouped: dict[str, list[AuditLog]] = {}
    for audit_log in audit_logs:
        key = target_key(audit_log.target_type, audit_log.target_id)
        grouped.setdefault(key, []).append(audit_log)
    for target_logs in grouped.values():
        target_logs.sort(key=lambda audit_log: audit_log.occurred_at, reverse=True)
    return grouped
