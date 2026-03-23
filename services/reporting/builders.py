from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Protocol

from libraries.core import build_provenance
from libraries.schemas import (
    AlertRecord,
    DailySystemReport,
    Experiment,
    ExperimentMetric,
    ExperimentScorecard,
    FailureCase,
    HealthCheckStatus,
    PaperTrade,
    PortfolioAttribution,
    PortfolioProposal,
    PortfolioSelectionSummary,
    ProposalScorecard,
    QualityDecision,
    RealismWarning,
    ReconciliationReport,
    ReportingAudience,
    ReportingContext,
    ResearchBrief,
    ResearchSummary,
    ReviewQueueItem,
    ReviewQueueStatus,
    ReviewQueueSummary,
    RiskCheck,
    RiskCheckStatus,
    RiskSummary,
    RobustnessCheck,
    RunSummary,
    ScorecardMeasure,
    ServiceStatus,
    StressTestResult,
    StressTestRun,
    SystemCapabilitySummary,
    ValidationGate,
)
from libraries.schemas.base import ProvenanceRecord, Severity
from libraries.schemas.paper_ledger import DailyPaperSummary, ReviewFollowup, ReviewFollowupStatus
from libraries.schemas.portfolio_construction import ConstructionDecision, PositionSizingRationale
from libraries.schemas.research import (
    CounterHypothesis,
    EvaluationReport,
    EvaluationStatus,
    EvidenceAssessment,
    EvidenceGrade,
    Hypothesis,
    ResearchReviewStatus,
    ResearchValidationStatus,
)
from libraries.time import Clock
from services.monitoring.summaries import dedupe_preserve_order


class _ProvenancedArtifact(Protocol):
    provenance: ProvenanceRecord


def build_research_summary(
    *,
    research_summary_id: str,
    research_brief: ResearchBrief,
    hypothesis: Hypothesis | None,
    counter_hypothesis: CounterHypothesis | None,
    evidence_assessment: EvidenceAssessment | None,
    validation_gates: list[ValidationGate],
    clock: Clock,
    requested_by: str,
) -> tuple[ResearchSummary, ReportingContext, list[str]]:
    """Build a grounded research summary from persisted research artifacts."""

    source_artifact_ids = dedupe_preserve_order(
        [
            research_brief.research_brief_id,
            research_brief.hypothesis_id,
            research_brief.counter_hypothesis_id,
            research_brief.evidence_assessment_id,
            *( [hypothesis.hypothesis_id] if hypothesis is not None else [] ),
            *( [counter_hypothesis.counter_hypothesis_id] if counter_hypothesis is not None else [] ),
            *( [evidence_assessment.evidence_assessment_id] if evidence_assessment is not None else [] ),
        ]
    )
    warning_artifact_ids = dedupe_preserve_order(
        [
            *(
                [research_brief.research_brief_id]
                if research_brief.review_status is not ResearchReviewStatus.APPROVED_FOR_FEATURE_WORK
                or research_brief.validation_status is not ResearchValidationStatus.VALIDATED
                else []
            ),
            *(
                [hypothesis.hypothesis_id]
                if hypothesis is not None
                and (
                    hypothesis.review_status is not ResearchReviewStatus.APPROVED_FOR_FEATURE_WORK
                    or hypothesis.validation_status is not ResearchValidationStatus.VALIDATED
                )
                else []
            ),
            *(
                [counter_hypothesis.counter_hypothesis_id]
                if counter_hypothesis is not None
                and (
                    counter_hypothesis.review_status
                    is not ResearchReviewStatus.APPROVED_FOR_FEATURE_WORK
                    or counter_hypothesis.validation_status
                    is not ResearchValidationStatus.VALIDATED
                )
                else []
            ),
            *(
                [evidence_assessment.evidence_assessment_id]
                if evidence_assessment is not None
                and (
                    evidence_assessment.review_status
                    is not ResearchReviewStatus.APPROVED_FOR_FEATURE_WORK
                    or evidence_assessment.validation_status
                    is not ResearchValidationStatus.VALIDATED
                    or evidence_assessment.grade in {EvidenceGrade.WEAK, EvidenceGrade.INSUFFICIENT}
                )
                else []
            ),
            *[gate.validation_gate_id for gate in validation_gates if gate.decision is not QualityDecision.PASS],
        ]
    )
    refusal_artifact_ids = _refusal_gate_ids(validation_gates)
    key_findings = dedupe_preserve_order(
        [
            research_brief.core_hypothesis,
            research_brief.context_summary,
            *( [evidence_assessment.support_summary] if evidence_assessment is not None else [] ),
            research_brief.counter_hypothesis_summary,
        ]
    )
    uncertainty_notes = dedupe_preserve_order(
        [
            research_brief.uncertainty_summary,
            *(
                [
                    f"confidence={research_brief.confidence.confidence:.2f}",
                    f"uncertainty={research_brief.confidence.uncertainty:.2f}",
                    *(
                        [research_brief.confidence.rationale]
                        if research_brief.confidence.rationale is not None
                        else []
                    ),
                ]
                if research_brief.confidence is not None
                else []
            ),
            *(hypothesis.uncertainties if hypothesis is not None else []),
            *(counter_hypothesis.unresolved_questions if counter_hypothesis is not None else []),
            *(evidence_assessment.contradiction_notes if evidence_assessment is not None else []),
        ]
    )
    missing_information = dedupe_preserve_order(
        [
            *(evidence_assessment.key_gaps if evidence_assessment is not None else []),
            *(counter_hypothesis.missing_evidence if counter_hypothesis is not None else []),
            *(
                ["hypothesis_missing"]
                if hypothesis is None
                else []
            ),
            *(
                ["counter_hypothesis_missing"]
                if counter_hypothesis is None
                else []
            ),
            *(
                ["evidence_assessment_missing"]
                if evidence_assessment is None
                else []
            ),
        ]
    )
    notes = [
        f"supporting_evidence_links={len(research_brief.supporting_evidence_links)}",
        f"warning_artifacts={len(warning_artifact_ids)}",
    ]
    context = build_reporting_context(
        audience=ReportingAudience.RESEARCHER,
        subject_type="research_brief",
        subject_id=research_brief.research_brief_id,
        source_artifact_ids=source_artifact_ids,
        warning_artifact_ids=warning_artifact_ids,
        refusal_or_quarantine_artifact_ids=refusal_artifact_ids,
        missing_inputs=missing_information,
        notes=notes,
    )
    summary = (
        f"Research summary for `{research_brief.title}` keeps the hypothesis, critique, and evidence grade visible. "
        f"Warnings={len(warning_artifact_ids)} missing_items={len(missing_information)}."
    )
    research_summary = ResearchSummary(
        research_summary_id=research_summary_id,
        research_brief_id=research_brief.research_brief_id,
        company_id=research_brief.company_id,
        hypothesis_id=hypothesis.hypothesis_id if hypothesis is not None else None,
        counter_hypothesis_id=(
            counter_hypothesis.counter_hypothesis_id if counter_hypothesis is not None else None
        ),
        evidence_assessment_id=(
            evidence_assessment.evidence_assessment_id if evidence_assessment is not None else None
        ),
        source_artifact_ids=source_artifact_ids,
        warning_artifact_ids=warning_artifact_ids,
        refusal_or_quarantine_artifact_ids=refusal_artifact_ids,
        key_findings=key_findings,
        uncertainty_notes=uncertainty_notes,
        missing_information=missing_information,
        summary=summary,
        provenance=_build_report_provenance(
            clock=clock,
            transformation_name="reporting_research_summary",
            source_models=[research_brief, hypothesis, counter_hypothesis, evidence_assessment],
            upstream_artifact_ids=[*source_artifact_ids, *warning_artifact_ids, *refusal_artifact_ids],
            notes=[f"requested_by={requested_by}"],
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    return research_summary, context, notes


def build_risk_summary(
    *,
    risk_summary_id: str,
    portfolio_proposal: PortfolioProposal,
    risk_checks: list[RiskCheck],
    stress_test_results: list[StressTestResult],
    validation_gates: list[ValidationGate],
    reconciliation_report: ReconciliationReport | None,
    clock: Clock,
    requested_by: str,
) -> tuple[RiskSummary, ReportingContext, list[str]]:
    """Build a grounded risk summary for one proposal."""

    blocking_findings = [check.message for check in risk_checks if check.blocking]
    warnings = dedupe_preserve_order(
        [
            *[
                check.message
                for check in risk_checks
                if check.status is not RiskCheckStatus.PASS and not check.blocking
            ],
            *[
                result.summary
                for result in stress_test_results
                if result.status is not RiskCheckStatus.PASS
            ],
            *[
                "; ".join(gate.notes) or f"validation_gate={gate.gate_name}"
                for gate in validation_gates
                if gate.decision is not QualityDecision.PASS
            ],
            *(
                [reconciliation_report.summary]
                if reconciliation_report is not None
                and not reconciliation_report.internally_consistent
                else []
            ),
        ]
    )
    source_artifact_ids = dedupe_preserve_order(
        [
            portfolio_proposal.portfolio_proposal_id,
            *[check.risk_check_id for check in risk_checks],
            *[result.stress_test_result_id for result in stress_test_results],
            *[gate.validation_gate_id for gate in validation_gates],
            *(
                [reconciliation_report.reconciliation_report_id]
                if reconciliation_report is not None
                else []
            ),
        ]
    )
    warning_artifact_ids = dedupe_preserve_order(
        [
            *[
                check.risk_check_id
                for check in risk_checks
                if check.status is not RiskCheckStatus.PASS
            ],
            *[
                result.stress_test_result_id
                for result in stress_test_results
                if result.status is not RiskCheckStatus.PASS
            ],
            *[gate.validation_gate_id for gate in validation_gates if gate.decision is not QualityDecision.PASS],
            *(
                [reconciliation_report.reconciliation_report_id]
                if reconciliation_report is not None and not reconciliation_report.internally_consistent
                else []
            ),
        ]
    )
    missing_information = dedupe_preserve_order(
        [
            *(
                ["stress_test_results_missing"]
                if not stress_test_results
                else []
            ),
            *(
                ["validation_gate_missing"]
                if not validation_gates
                else []
            ),
            *(
                ["reconciliation_report_missing"]
                if reconciliation_report is None
                else []
            ),
        ]
    )
    refusal_artifact_ids = _refusal_gate_ids(validation_gates)
    notes = [
        f"risk_checks={len(risk_checks)}",
        f"stress_results={len(stress_test_results)}",
    ]
    context = build_reporting_context(
        audience=ReportingAudience.REVIEWER,
        subject_type="portfolio_proposal",
        subject_id=portfolio_proposal.portfolio_proposal_id,
        source_artifact_ids=source_artifact_ids,
        warning_artifact_ids=warning_artifact_ids,
        refusal_or_quarantine_artifact_ids=refusal_artifact_ids,
        missing_inputs=missing_information,
        notes=notes,
    )
    summary = (
        f"Risk summary for proposal `{portfolio_proposal.name}` captures "
        f"{len(blocking_findings)} blocking findings and {len(warnings)} warnings."
    )
    risk_summary = RiskSummary(
        risk_summary_id=risk_summary_id,
        portfolio_proposal_id=portfolio_proposal.portfolio_proposal_id,
        risk_check_ids=[check.risk_check_id for check in risk_checks],
        stress_test_result_ids=[result.stress_test_result_id for result in stress_test_results],
        validation_gate_ids=[gate.validation_gate_id for gate in validation_gates],
        reconciliation_report_id=(
            reconciliation_report.reconciliation_report_id if reconciliation_report is not None else None
        ),
        source_artifact_ids=source_artifact_ids,
        warning_artifact_ids=warning_artifact_ids,
        blocking_findings=blocking_findings,
        warnings=warnings,
        missing_information=missing_information,
        summary=summary,
        provenance=_build_report_provenance(
            clock=clock,
            transformation_name="reporting_risk_summary",
            source_models=[portfolio_proposal, *risk_checks, *stress_test_results, *validation_gates],
            upstream_artifact_ids=[*source_artifact_ids, *warning_artifact_ids, *refusal_artifact_ids],
            notes=[f"requested_by={requested_by}"],
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    return risk_summary, context, notes


def build_review_queue_summary(
    *,
    review_queue_summary_id: str,
    queue_items: list[ReviewQueueItem],
    clock: Clock,
    requested_by: str,
) -> tuple[ReviewQueueSummary, ReportingContext, list[str]]:
    """Build a grounded summary of the current review queue."""

    counts_by_target_type: dict[str, int] = {}
    counts_by_queue_status: dict[str, int] = {}
    escalated_item_ids: list[str] = []
    unassigned_item_ids: list[str] = []
    attention_required_item_ids: list[str] = []
    for item in queue_items:
        counts_by_target_type[item.target_type.value] = counts_by_target_type.get(item.target_type.value, 0) + 1
        counts_by_queue_status[item.queue_status.value] = counts_by_queue_status.get(item.queue_status.value, 0) + 1
        if item.escalation_status.value != "none":
            escalated_item_ids.append(item.review_queue_item_id)
        if item.review_assignment_id is None:
            unassigned_item_ids.append(item.review_queue_item_id)
        if (
            item.action_recommendation.blocking_reasons
            or item.action_recommendation.warnings
            or item.queue_status is ReviewQueueStatus.AWAITING_REVISION
            or item.escalation_status.value != "none"
        ):
            attention_required_item_ids.append(item.review_queue_item_id)

    source_artifact_ids = [item.review_queue_item_id for item in queue_items]
    warning_artifact_ids = dedupe_preserve_order(
        [*escalated_item_ids, *attention_required_item_ids, *unassigned_item_ids]
    )
    missing_information: list[str] = []
    notes = [
        f"queue_items={len(queue_items)}",
        f"attention_required_items={len(attention_required_item_ids)}",
    ]
    context = build_reporting_context(
        audience=ReportingAudience.OPERATOR,
        subject_type="review_queue",
        subject_id="review_queue_snapshot",
        source_artifact_ids=source_artifact_ids,
        warning_artifact_ids=warning_artifact_ids,
        refusal_or_quarantine_artifact_ids=[],
        missing_inputs=missing_information,
        notes=notes,
    )
    summary = (
        f"Review queue snapshot contains {len(queue_items)} items with "
        f"{len(attention_required_item_ids)} attention-bearing entries."
    )
    queue_summary = ReviewQueueSummary(
        review_queue_summary_id=review_queue_summary_id,
        queue_item_ids=source_artifact_ids,
        counts_by_target_type=counts_by_target_type,
        counts_by_queue_status=counts_by_queue_status,
        escalated_item_ids=dedupe_preserve_order(escalated_item_ids),
        unassigned_item_ids=dedupe_preserve_order(unassigned_item_ids),
        attention_required_item_ids=dedupe_preserve_order(attention_required_item_ids),
        source_artifact_ids=source_artifact_ids,
        warning_artifact_ids=warning_artifact_ids,
        missing_information=missing_information,
        summary=summary,
        provenance=_build_report_provenance(
            clock=clock,
            transformation_name="reporting_review_queue_summary",
            source_models=queue_items,
            upstream_artifact_ids=[*source_artifact_ids, *warning_artifact_ids],
            notes=[f"requested_by={requested_by}"],
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    return queue_summary, context, notes


def build_experiment_scorecard(
    *,
    experiment_scorecard_id: str,
    experiment: Experiment,
    evaluation_report: EvaluationReport | None,
    experiment_metrics: list[ExperimentMetric],
    failure_cases: list[FailureCase],
    robustness_checks: list[RobustnessCheck],
    realism_warnings: list[RealismWarning],
    validation_gates: list[ValidationGate],
    clock: Clock,
    requested_by: str,
) -> tuple[ExperimentScorecard, ReportingContext, list[str]]:
    """Build a grounded experiment scorecard."""

    measures = [
        ScorecardMeasure(
            measure_name="experiment_metadata_integrity",
            measure_basis="Validation-gate outcomes attached to experiment creation.",
            status=_status_from_validation_gates(validation_gates),
            linked_artifact_ids=[experiment.experiment_id, *[gate.validation_gate_id for gate in validation_gates]] or [experiment.experiment_id],
            notes=[
                "No experiment metadata validation gate was recorded."
                if not validation_gates
                else f"validation_gates={len(validation_gates)}"
            ],
        ),
        ScorecardMeasure(
            measure_name="evaluation_coverage",
            measure_basis="Presence and overall status of the structured evaluation report.",
            status=_status_from_evaluation_report(evaluation_report),
            linked_artifact_ids=[experiment.experiment_id, *( [evaluation_report.evaluation_report_id] if evaluation_report is not None else [] )],
            notes=[
                "Evaluation report is missing."
                if evaluation_report is None
                else f"overall_status={evaluation_report.overall_status.value}"
            ],
        ),
        ScorecardMeasure(
            measure_name="failure_case_pressure",
            measure_basis="Blocking and non-blocking failure cases attached to the experiment evaluation.",
            status=_status_from_failures(failure_cases),
            linked_artifact_ids=[experiment.experiment_id, *[failure.failure_case_id for failure in failure_cases]],
            notes=[f"failure_case_count={len(failure_cases)}"],
        ),
        ScorecardMeasure(
            measure_name="robustness_pressure",
            measure_basis="Warn and fail robustness checks attached to the experiment evaluation.",
            status=_status_from_robustness_checks(robustness_checks),
            linked_artifact_ids=[experiment.experiment_id, *[check.robustness_check_id for check in robustness_checks]],
            notes=[f"robustness_check_count={len(robustness_checks)}"],
        ),
        ScorecardMeasure(
            measure_name="execution_realism_gap",
            measure_basis="Explicit realism warnings recorded for the compared backtest or paper path.",
            status=_status_from_warning_count(len(realism_warnings)),
            linked_artifact_ids=[experiment.experiment_id, *[warning.realism_warning_id for warning in realism_warnings]],
            notes=[f"realism_warning_count={len(realism_warnings)}"],
        ),
    ]
    source_artifact_ids = dedupe_preserve_order(
        [
            experiment.experiment_id,
            *( [evaluation_report.evaluation_report_id] if evaluation_report is not None else [] ),
            *[metric.experiment_metric_id for metric in experiment_metrics],
            *[failure.failure_case_id for failure in failure_cases],
            *[check.robustness_check_id for check in robustness_checks],
            *[warning.realism_warning_id for warning in realism_warnings],
            *[gate.validation_gate_id for gate in validation_gates],
        ]
    )
    warning_artifact_ids = dedupe_preserve_order(
        [
            *[failure.failure_case_id for failure in failure_cases],
            *[
                check.robustness_check_id
                for check in robustness_checks
                if check.status in {EvaluationStatus.WARN, EvaluationStatus.FAIL}
            ],
            *[warning.realism_warning_id for warning in realism_warnings],
            *[gate.validation_gate_id for gate in validation_gates if gate.decision is not QualityDecision.PASS],
            *(
                [evaluation_report.evaluation_report_id]
                if evaluation_report is not None
                and evaluation_report.overall_status in {EvaluationStatus.WARN, EvaluationStatus.FAIL}
                else []
            ),
        ]
    )
    missing_information = dedupe_preserve_order(
        [
            *(
                ["evaluation_report_missing"]
                if evaluation_report is None
                else []
            ),
            *(
                ["experiment_metrics_missing"]
                if not experiment_metrics
                else []
            ),
            *(
                ["validation_gate_missing"]
                if not validation_gates
                else []
            ),
        ]
    )
    refusal_artifact_ids = _refusal_gate_ids(validation_gates)
    notes = [
        f"measures={len(measures)}",
        f"warning_artifacts={len(warning_artifact_ids)}",
    ]
    context = build_reporting_context(
        audience=ReportingAudience.RESEARCHER,
        subject_type="experiment",
        subject_id=experiment.experiment_id,
        source_artifact_ids=source_artifact_ids,
        warning_artifact_ids=warning_artifact_ids,
        refusal_or_quarantine_artifact_ids=refusal_artifact_ids,
        missing_inputs=missing_information,
        notes=notes,
    )
    summary = (
        f"Experiment scorecard for `{experiment.name}` exposes {len(measures)} explicit measures, "
        f"{len(warning_artifact_ids)} warnings, and {len(missing_information)} missing-information flags."
    )
    scorecard = ExperimentScorecard(
        experiment_scorecard_id=experiment_scorecard_id,
        experiment_id=experiment.experiment_id,
        evaluation_report_id=evaluation_report.evaluation_report_id if evaluation_report is not None else None,
        experiment_metric_ids=[metric.experiment_metric_id for metric in experiment_metrics],
        failure_case_ids=[failure.failure_case_id for failure in failure_cases],
        robustness_check_ids=[check.robustness_check_id for check in robustness_checks],
        realism_warning_ids=[warning.realism_warning_id for warning in realism_warnings],
        validation_gate_ids=[gate.validation_gate_id for gate in validation_gates],
        measures=measures,
        warning_artifact_ids=warning_artifact_ids,
        source_artifact_ids=source_artifact_ids,
        missing_information=missing_information,
        summary=summary,
        provenance=_build_report_provenance(
            clock=clock,
            transformation_name="reporting_experiment_scorecard",
            source_models=[experiment, evaluation_report, *experiment_metrics, *failure_cases, *robustness_checks, *realism_warnings, *validation_gates],
            upstream_artifact_ids=[*source_artifact_ids, *warning_artifact_ids, *refusal_artifact_ids],
            notes=[f"requested_by={requested_by}"],
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    return scorecard, context, notes


def build_proposal_scorecard(
    *,
    proposal_scorecard_id: str,
    portfolio_proposal: PortfolioProposal,
    portfolio_selection_summary: PortfolioSelectionSummary | None,
    construction_decisions: list[ConstructionDecision],
    position_sizing_rationales: list[PositionSizingRationale],
    portfolio_attribution: PortfolioAttribution | None,
    stress_test_run: StressTestRun | None,
    stress_test_results: list[StressTestResult],
    risk_checks: list[RiskCheck],
    validation_gates: list[ValidationGate],
    reconciliation_report: ReconciliationReport | None,
    realism_warnings: list[RealismWarning],
    paper_trades: list[PaperTrade],
    clock: Clock,
    requested_by: str,
) -> tuple[ProposalScorecard, ReportingContext, list[str]]:
    """Build a grounded proposal scorecard."""

    measures = [
        ScorecardMeasure(
            measure_name="construction_traceability",
            measure_basis="Presence of construction summary, decisions, and sizing rationales.",
            status=(
                HealthCheckStatus.PASS
                if portfolio_selection_summary is not None and construction_decisions and position_sizing_rationales
                else HealthCheckStatus.WARN
            ),
            linked_artifact_ids=[
                portfolio_proposal.portfolio_proposal_id,
                *(
                    [portfolio_selection_summary.portfolio_selection_summary_id]
                    if portfolio_selection_summary is not None
                    else []
                ),
                *[decision.construction_decision_id for decision in construction_decisions],
                *[rationale.position_sizing_rationale_id for rationale in position_sizing_rationales],
            ] or [portfolio_proposal.portfolio_proposal_id],
            notes=[
                f"construction_decisions={len(construction_decisions)}",
                f"sizing_rationales={len(position_sizing_rationales)}",
            ],
        ),
        ScorecardMeasure(
            measure_name="risk_check_pressure",
            measure_basis="Blocking and non-blocking proposal risk checks.",
            status=_status_from_risk_checks(risk_checks),
            linked_artifact_ids=[
                portfolio_proposal.portfolio_proposal_id,
                *[check.risk_check_id for check in risk_checks],
            ],
            notes=[f"risk_checks={len(risk_checks)}"],
        ),
        ScorecardMeasure(
            measure_name="stress_fragility",
            measure_basis="Current stress-test result statuses and severities.",
            status=_status_from_stress_results(stress_test_results),
            linked_artifact_ids=[
                portfolio_proposal.portfolio_proposal_id,
                *( [stress_test_run.stress_test_run_id] if stress_test_run is not None else [] ),
                *[result.stress_test_result_id for result in stress_test_results],
            ],
            notes=[f"stress_test_results={len(stress_test_results)}"],
        ),
        ScorecardMeasure(
            measure_name="reconciliation_alignment",
            measure_basis="Backtest-to-paper reconciliation consistency and realism warnings.",
            status=_status_from_reconciliation(reconciliation_report, realism_warnings),
            linked_artifact_ids=[
                portfolio_proposal.portfolio_proposal_id,
                *( [reconciliation_report.reconciliation_report_id] if reconciliation_report is not None else [] ),
                *[warning.realism_warning_id for warning in realism_warnings],
            ] or [portfolio_proposal.portfolio_proposal_id],
            notes=[
                "Reconciliation report is missing."
                if reconciliation_report is None
                else f"internally_consistent={reconciliation_report.internally_consistent}"
            ],
        ),
        ScorecardMeasure(
            measure_name="paper_trade_materialization",
            measure_basis="Paper-trade candidates plus downstream validation outcomes.",
            status=_status_from_paper_trade_readiness(paper_trades, validation_gates),
            linked_artifact_ids=[
                portfolio_proposal.portfolio_proposal_id,
                *[trade.paper_trade_id for trade in paper_trades],
                *[gate.validation_gate_id for gate in validation_gates],
            ] or [portfolio_proposal.portfolio_proposal_id],
            notes=[f"paper_trades={len(paper_trades)}"],
        ),
    ]
    blocking_findings = [check.message for check in risk_checks if check.blocking]
    warnings = dedupe_preserve_order(
        [
            *[
                check.message
                for check in risk_checks
                if check.status is not RiskCheckStatus.PASS and not check.blocking
            ],
            *[
                result.summary
                for result in stress_test_results
                if result.status is not RiskCheckStatus.PASS
            ],
            *(
                [reconciliation_report.summary]
                if reconciliation_report is not None and not reconciliation_report.internally_consistent
                else []
            ),
            *[
                "; ".join(gate.notes) or f"validation_gate={gate.gate_name}"
                for gate in validation_gates
                if gate.decision is not QualityDecision.PASS
            ],
        ]
    )
    source_artifact_ids = dedupe_preserve_order(
        [
            portfolio_proposal.portfolio_proposal_id,
            *( [portfolio_selection_summary.portfolio_selection_summary_id] if portfolio_selection_summary is not None else [] ),
            *( [portfolio_attribution.portfolio_attribution_id] if portfolio_attribution is not None else [] ),
            *( [stress_test_run.stress_test_run_id] if stress_test_run is not None else [] ),
            *[decision.construction_decision_id for decision in construction_decisions],
            *[rationale.position_sizing_rationale_id for rationale in position_sizing_rationales],
            *[check.risk_check_id for check in risk_checks],
            *[result.stress_test_result_id for result in stress_test_results],
            *[trade.paper_trade_id for trade in paper_trades],
            *[gate.validation_gate_id for gate in validation_gates],
            *( [reconciliation_report.reconciliation_report_id] if reconciliation_report is not None else [] ),
            *[warning.realism_warning_id for warning in realism_warnings],
        ]
    )
    warning_artifact_ids = dedupe_preserve_order(
        [
            *[
                check.risk_check_id
                for check in risk_checks
                if check.status is not RiskCheckStatus.PASS
            ],
            *[
                result.stress_test_result_id
                for result in stress_test_results
                if result.status is not RiskCheckStatus.PASS
            ],
            *[warning.realism_warning_id for warning in realism_warnings],
            *[gate.validation_gate_id for gate in validation_gates if gate.decision is not QualityDecision.PASS],
            *(
                [reconciliation_report.reconciliation_report_id]
                if reconciliation_report is not None and not reconciliation_report.internally_consistent
                else []
            ),
        ]
    )
    missing_information = dedupe_preserve_order(
        [
            *(
                ["construction_summary_missing"]
                if portfolio_selection_summary is None
                else []
            ),
            *(
                ["portfolio_attribution_missing"]
                if portfolio_attribution is None
                else []
            ),
            *(
                ["stress_test_run_missing"]
                if stress_test_run is None or not stress_test_results
                else []
            ),
            *(
                ["reconciliation_report_missing"]
                if reconciliation_report is None
                else []
            ),
            *(
                ["paper_trade_candidates_missing"]
                if not paper_trades
                else []
            ),
        ]
    )
    refusal_artifact_ids = _refusal_gate_ids(validation_gates)
    notes = [
        f"measures={len(measures)}",
        f"paper_trades={len(paper_trades)}",
    ]
    context = build_reporting_context(
        audience=ReportingAudience.REVIEWER,
        subject_type="portfolio_proposal",
        subject_id=portfolio_proposal.portfolio_proposal_id,
        source_artifact_ids=source_artifact_ids,
        warning_artifact_ids=warning_artifact_ids,
        refusal_or_quarantine_artifact_ids=refusal_artifact_ids,
        missing_inputs=missing_information,
        notes=notes,
    )
    summary = (
        f"Proposal scorecard for `{portfolio_proposal.name}` exposes {len(measures)} measures, "
        f"{len(blocking_findings)} blocking findings, and {len(warnings)} warnings."
    )
    proposal_scorecard = ProposalScorecard(
        proposal_scorecard_id=proposal_scorecard_id,
        portfolio_proposal_id=portfolio_proposal.portfolio_proposal_id,
        portfolio_selection_summary_id=(
            portfolio_selection_summary.portfolio_selection_summary_id
            if portfolio_selection_summary is not None
            else None
        ),
        portfolio_attribution_id=(
            portfolio_attribution.portfolio_attribution_id
            if portfolio_attribution is not None
            else None
        ),
        stress_test_run_id=stress_test_run.stress_test_run_id if stress_test_run is not None else None,
        reconciliation_report_id=(
            reconciliation_report.reconciliation_report_id
            if reconciliation_report is not None
            else None
        ),
        risk_check_ids=[check.risk_check_id for check in risk_checks],
        validation_gate_ids=[gate.validation_gate_id for gate in validation_gates],
        construction_decision_ids=[decision.construction_decision_id for decision in construction_decisions],
        position_sizing_rationale_ids=[
            rationale.position_sizing_rationale_id for rationale in position_sizing_rationales
        ],
        stress_test_result_ids=[result.stress_test_result_id for result in stress_test_results],
        paper_trade_ids=[trade.paper_trade_id for trade in paper_trades],
        measures=measures,
        blocking_findings=blocking_findings,
        warnings=warnings,
        source_artifact_ids=source_artifact_ids,
        warning_artifact_ids=warning_artifact_ids,
        missing_information=missing_information,
        summary=summary,
        provenance=_build_report_provenance(
            clock=clock,
            transformation_name="reporting_proposal_scorecard",
            source_models=[
                portfolio_proposal,
                portfolio_selection_summary,
                portfolio_attribution,
                stress_test_run,
                *construction_decisions,
                *position_sizing_rationales,
                *risk_checks,
                *stress_test_results,
                *paper_trades,
                *validation_gates,
                reconciliation_report,
                *realism_warnings,
            ],
            upstream_artifact_ids=[*source_artifact_ids, *warning_artifact_ids, *refusal_artifact_ids],
            notes=[f"requested_by={requested_by}"],
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    return proposal_scorecard, context, notes


def build_daily_system_report(
    *,
    daily_system_report_id: str,
    report_date: date,
    run_summaries: list[RunSummary],
    alert_records: list[AlertRecord],
    service_statuses: list[ServiceStatus],
    review_queue_summary: ReviewQueueSummary | None,
    daily_paper_summaries: list[DailyPaperSummary],
    review_followups: list[ReviewFollowup],
    proposal_scorecards: list[ProposalScorecard],
    experiment_scorecards: list[ExperimentScorecard],
    clock: Clock,
    requested_by: str,
) -> tuple[DailySystemReport, ReportingContext, list[str]]:
    """Build an operator-facing daily system report."""

    open_followups = [
        followup for followup in review_followups if followup.status is ReviewFollowupStatus.OPEN
    ]
    source_artifact_ids = dedupe_preserve_order(
        [
            *[summary.run_summary_id for summary in run_summaries],
            *[alert.alert_record_id for alert in alert_records],
            *( [review_queue_summary.review_queue_summary_id] if review_queue_summary is not None else [] ),
            *[summary.daily_paper_summary_id for summary in daily_paper_summaries],
            *[followup.review_followup_id for followup in open_followups],
            *[scorecard.proposal_scorecard_id for scorecard in proposal_scorecards],
            *[scorecard.experiment_scorecard_id for scorecard in experiment_scorecards],
        ]
    )
    warning_artifact_ids = dedupe_preserve_order(
        [
            *[alert.alert_record_id for alert in alert_records],
            *[summary.run_summary_id for summary in run_summaries if summary.status.value in {"failed", "partial", "attention_required"}],
            *[followup.review_followup_id for followup in open_followups],
            *[
                scorecard.proposal_scorecard_id
                for scorecard in proposal_scorecards
                if scorecard.warning_artifact_ids or scorecard.blocking_findings
            ],
            *[
                scorecard.experiment_scorecard_id
                for scorecard in experiment_scorecards
                if scorecard.warning_artifact_ids
            ],
        ]
    )
    notable_failures = dedupe_preserve_order(
        [
            *[
                message
                for summary in run_summaries
                for message in summary.failure_messages
            ],
            *[alert.message for alert in alert_records],
        ]
    )[:10]
    attention_reasons = dedupe_preserve_order(
        [
            *[
                reason
                for summary in run_summaries
                for reason in summary.attention_reasons
            ],
            *[
                followup.summary
                for followup in open_followups
            ],
        ]
    )[:10]
    missing_information = dedupe_preserve_order(
        [
            *(
                ["review_queue_summary_missing"]
                if review_queue_summary is None
                else []
            ),
            *(
                ["daily_paper_summary_missing"]
                if not daily_paper_summaries
                else []
            ),
            *(
                ["proposal_scorecards_missing"]
                if not proposal_scorecards
                else []
            ),
            *(
                ["experiment_scorecards_missing"]
                if not experiment_scorecards
                else []
            ),
        ]
    )
    notes = [
        f"run_summaries={len(run_summaries)}",
        f"alerts={len(alert_records)}",
        f"open_followups={len(open_followups)}",
    ]
    context = build_reporting_context(
        audience=ReportingAudience.OPERATOR,
        subject_type="daily_system_report",
        subject_id=report_date.isoformat(),
        source_artifact_ids=source_artifact_ids,
        warning_artifact_ids=warning_artifact_ids,
        refusal_or_quarantine_artifact_ids=[],
        missing_inputs=missing_information,
        notes=notes,
    )
    summary = (
        f"Daily system report for {report_date.isoformat()} surfaces "
        f"{len(alert_records)} alerts, {len(open_followups)} open followups, "
        f"and {len(attention_reasons)} attention reasons."
    )
    report = DailySystemReport(
        daily_system_report_id=daily_system_report_id,
        report_date=report_date,
        run_summary_ids=[summary.run_summary_id for summary in run_summaries],
        alert_record_ids=[alert.alert_record_id for alert in alert_records],
        service_statuses=service_statuses,
        review_queue_summary_id=(
            review_queue_summary.review_queue_summary_id if review_queue_summary is not None else None
        ),
        daily_paper_summary_ids=[summary.daily_paper_summary_id for summary in daily_paper_summaries],
        open_review_followup_ids=[followup.review_followup_id for followup in open_followups],
        proposal_scorecard_ids=[scorecard.proposal_scorecard_id for scorecard in proposal_scorecards],
        experiment_scorecard_ids=[scorecard.experiment_scorecard_id for scorecard in experiment_scorecards],
        source_artifact_ids=source_artifact_ids,
        notable_failures=notable_failures,
        attention_reasons=attention_reasons,
        missing_information=missing_information,
        summary=summary,
        provenance=_build_report_provenance(
            clock=clock,
            transformation_name="reporting_daily_system_report",
            source_models=[
                *run_summaries,
                *alert_records,
                review_queue_summary,
                *daily_paper_summaries,
                *open_followups,
                *proposal_scorecards,
                *experiment_scorecards,
            ],
            upstream_artifact_ids=[*source_artifact_ids, *warning_artifact_ids],
            notes=[f"requested_by={requested_by}"],
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    return report, context, notes


def build_system_capability_summary(
    *,
    system_capability_summary_id: str,
    capability_name: str,
    service_names: list[str],
    recent_run_summaries: list[RunSummary],
    alert_records: list[AlertRecord],
    evidence_artifact_ids: list[str],
    current_limitations: list[str],
    maturity_notes: list[str],
    clock: Clock,
    requested_by: str,
) -> tuple[SystemCapabilitySummary, ReportingContext, list[str]]:
    """Build a grounded subsystem capability summary."""

    source_artifact_ids = dedupe_preserve_order(
        [
            *evidence_artifact_ids,
            *[summary.run_summary_id for summary in recent_run_summaries],
            *[alert.alert_record_id for alert in alert_records],
        ]
    )
    warning_artifact_ids = dedupe_preserve_order(
        [
            *[summary.run_summary_id for summary in recent_run_summaries if summary.status.value in {"failed", "partial", "attention_required"}],
            *[alert.alert_record_id for alert in alert_records],
        ]
    )
    notes = [
        f"services={len(service_names)}",
        f"run_summaries={len(recent_run_summaries)}",
    ]
    context = build_reporting_context(
        audience=ReportingAudience.SYSTEM,
        subject_type="system_capability",
        subject_id=capability_name,
        source_artifact_ids=source_artifact_ids,
        warning_artifact_ids=warning_artifact_ids,
        refusal_or_quarantine_artifact_ids=[],
        missing_inputs=[],
        notes=notes,
    )
    summary = (
        f"Capability summary for `{capability_name}` reflects {len(service_names)} services "
        f"and {len(warning_artifact_ids)} warning-bearing artifacts."
    )
    capability_summary = SystemCapabilitySummary(
        system_capability_summary_id=system_capability_summary_id,
        capability_name=capability_name,
        service_names=service_names,
        evidence_artifact_ids=evidence_artifact_ids,
        recent_run_summary_ids=[summary.run_summary_id for summary in recent_run_summaries],
        alert_record_ids=[alert.alert_record_id for alert in alert_records],
        current_limitations=current_limitations,
        maturity_notes=maturity_notes,
        source_artifact_ids=source_artifact_ids,
        warning_artifact_ids=warning_artifact_ids,
        summary=summary,
        provenance=_build_report_provenance(
            clock=clock,
            transformation_name="reporting_system_capability_summary",
            source_models=[*recent_run_summaries, *alert_records],
            upstream_artifact_ids=[*source_artifact_ids, *warning_artifact_ids],
            notes=[f"requested_by={requested_by}"],
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    return capability_summary, context, notes


def build_reporting_context(
    *,
    audience: ReportingAudience,
    subject_type: str,
    subject_id: str,
    source_artifact_ids: list[str],
    warning_artifact_ids: list[str],
    refusal_or_quarantine_artifact_ids: list[str],
    missing_inputs: list[str],
    notes: list[str],
) -> ReportingContext:
    """Build a derived reporting context bundle."""

    return ReportingContext(
        audience=audience,
        subject_type=subject_type,
        subject_id=subject_id,
        source_artifact_ids=dedupe_preserve_order(source_artifact_ids),
        warning_artifact_ids=dedupe_preserve_order(warning_artifact_ids),
        refusal_or_quarantine_artifact_ids=dedupe_preserve_order(refusal_or_quarantine_artifact_ids),
        missing_inputs=dedupe_preserve_order(missing_inputs),
        notes=notes,
    )


def _build_report_provenance(
    *,
    clock: Clock,
    transformation_name: str,
    source_models: Iterable[object | None],
    upstream_artifact_ids: list[str],
    notes: list[str],
) -> ProvenanceRecord:
    """Build provenance for one reporting artifact."""

    return build_provenance(
        clock=clock,
        transformation_name=transformation_name,
        source_reference_ids=_collect_source_reference_ids(source_models),
        upstream_artifact_ids=dedupe_preserve_order(upstream_artifact_ids),
        notes=notes,
    )


def _collect_source_reference_ids(models: Iterable[object | None]) -> list[str]:
    source_reference_ids: list[str] = []
    for model in models:
        if model is None or not hasattr(model, "provenance"):
            continue
        provenance = getattr(model, "provenance", None)
        if provenance is None:
            continue
        source_reference_ids.extend(provenance.source_reference_ids)
    return dedupe_preserve_order(source_reference_ids)


def _refusal_gate_ids(validation_gates: list[ValidationGate]) -> list[str]:
    return [
        gate.validation_gate_id
        for gate in validation_gates
        if gate.decision in {QualityDecision.REFUSE, QualityDecision.QUARANTINE}
    ]


def _status_from_validation_gates(validation_gates: list[ValidationGate]) -> HealthCheckStatus:
    if any(gate.decision in {QualityDecision.REFUSE, QualityDecision.QUARANTINE} for gate in validation_gates):
        return HealthCheckStatus.FAIL
    if any(gate.decision is QualityDecision.WARN for gate in validation_gates):
        return HealthCheckStatus.WARN
    return HealthCheckStatus.PASS


def _status_from_evaluation_report(
    evaluation_report: EvaluationReport | None,
) -> HealthCheckStatus:
    if evaluation_report is None:
        return HealthCheckStatus.WARN
    if evaluation_report.overall_status is EvaluationStatus.FAIL:
        return HealthCheckStatus.FAIL
    if evaluation_report.overall_status in {EvaluationStatus.WARN, EvaluationStatus.NOT_EVALUATED}:
        return HealthCheckStatus.WARN
    return HealthCheckStatus.PASS


def _status_from_failures(failure_cases: list[FailureCase]) -> HealthCheckStatus:
    if any(case.blocking or case.severity in {Severity.HIGH, Severity.CRITICAL} for case in failure_cases):
        return HealthCheckStatus.FAIL
    if failure_cases:
        return HealthCheckStatus.WARN
    return HealthCheckStatus.PASS


def _status_from_robustness_checks(robustness_checks: list[RobustnessCheck]) -> HealthCheckStatus:
    if any(check.status is EvaluationStatus.FAIL for check in robustness_checks):
        return HealthCheckStatus.FAIL
    if any(check.status in {EvaluationStatus.WARN, EvaluationStatus.NOT_EVALUATED} for check in robustness_checks):
        return HealthCheckStatus.WARN
    return HealthCheckStatus.PASS


def _status_from_warning_count(warning_count: int) -> HealthCheckStatus:
    if warning_count > 0:
        return HealthCheckStatus.WARN
    return HealthCheckStatus.PASS


def _status_from_risk_checks(risk_checks: list[RiskCheck]) -> HealthCheckStatus:
    if any(check.blocking or check.status is RiskCheckStatus.FAIL for check in risk_checks):
        return HealthCheckStatus.FAIL
    if any(check.status is RiskCheckStatus.WARN for check in risk_checks):
        return HealthCheckStatus.WARN
    return HealthCheckStatus.PASS


def _status_from_stress_results(stress_test_results: list[StressTestResult]) -> HealthCheckStatus:
    if any(result.status is RiskCheckStatus.FAIL for result in stress_test_results):
        return HealthCheckStatus.FAIL
    if any(result.status is RiskCheckStatus.WARN for result in stress_test_results):
        return HealthCheckStatus.WARN
    if not stress_test_results:
        return HealthCheckStatus.WARN
    return HealthCheckStatus.PASS


def _status_from_reconciliation(
    reconciliation_report: ReconciliationReport | None,
    realism_warnings: list[RealismWarning],
) -> HealthCheckStatus:
    if reconciliation_report is None:
        return HealthCheckStatus.WARN
    if not reconciliation_report.internally_consistent:
        if reconciliation_report.highest_severity in {Severity.HIGH, Severity.CRITICAL}:
            return HealthCheckStatus.FAIL
        return HealthCheckStatus.WARN
    if realism_warnings:
        return HealthCheckStatus.WARN
    return HealthCheckStatus.PASS


def _status_from_paper_trade_readiness(
    paper_trades: list[PaperTrade],
    validation_gates: list[ValidationGate],
) -> HealthCheckStatus:
    if any(gate.decision in {QualityDecision.REFUSE, QualityDecision.QUARANTINE} for gate in validation_gates):
        return HealthCheckStatus.FAIL
    if not paper_trades:
        return HealthCheckStatus.WARN
    if any(gate.decision is QualityDecision.WARN for gate in validation_gates):
        return HealthCheckStatus.WARN
    return HealthCheckStatus.PASS
