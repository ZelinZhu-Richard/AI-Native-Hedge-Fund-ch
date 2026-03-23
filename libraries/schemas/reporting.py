from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import Field, model_validator

from libraries.schemas.base import ProvenanceRecord, StrictModel, TimestampedModel
from libraries.schemas.system import HealthCheckStatus, ServiceStatus


class ReportingAudience(StrEnum):
    """Primary audience for one derived report or scorecard."""

    OPERATOR = "operator"
    RESEARCHER = "researcher"
    REVIEWER = "reviewer"
    SYSTEM = "system"


class ScorecardMeasure(StrictModel):
    """Explicit measured dimension included in a grounded scorecard."""

    measure_name: str = Field(description="Stable measure name.")
    measure_basis: str = Field(description="Explicit basis used to derive the measure.")
    status: HealthCheckStatus = Field(description="Outcome classification for the measure.")
    linked_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts directly supporting the measure.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Interpretation notes or caveats for the measure.",
    )

    @model_validator(mode="after")
    def validate_measure(self) -> ScorecardMeasure:
        """Require explicit basis text and linked artifacts."""

        if not self.measure_name:
            raise ValueError("measure_name must be non-empty.")
        if not self.measure_basis:
            raise ValueError("measure_basis must be non-empty.")
        if not self.linked_artifact_ids:
            raise ValueError("linked_artifact_ids must contain at least one artifact identifier.")
        return self


class ReportingContext(StrictModel):
    """Derived grounding context explaining what one report was built from."""

    audience: ReportingAudience = Field(description="Primary audience for the report.")
    subject_type: str = Field(description="Type of entity summarized by the report.")
    subject_id: str = Field(description="Identifier of the entity summarized by the report.")
    source_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts used as source truth for the report.",
    )
    warning_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Warning-bearing artifacts surfaced by the report.",
    )
    refusal_or_quarantine_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Validation-gate artifacts reflecting refusal or quarantine outcomes.",
    )
    missing_inputs: list[str] = Field(
        default_factory=list,
        description="Required or useful inputs that were missing while building the report.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional grounding notes for the report.",
    )

    @model_validator(mode="after")
    def validate_context(self) -> ReportingContext:
        """Require explicit subject linkage."""

        if not self.subject_type:
            raise ValueError("subject_type must be non-empty.")
        if not self.subject_id:
            raise ValueError("subject_id must be non-empty.")
        return self


class ResearchSummary(TimestampedModel):
    """Grounded summary of one research brief and its immediate support artifacts."""

    research_summary_id: str = Field(description="Canonical research-summary identifier.")
    research_brief_id: str = Field(description="Research-brief identifier summarized by the report.")
    company_id: str = Field(description="Covered company identifier.")
    hypothesis_id: str | None = Field(
        default=None,
        description="Primary hypothesis identifier when available.",
    )
    counter_hypothesis_id: str | None = Field(
        default=None,
        description="Primary counter-hypothesis identifier when available.",
    )
    evidence_assessment_id: str | None = Field(
        default=None,
        description="Evidence-assessment identifier when available.",
    )
    source_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts directly summarized by the report.",
    )
    warning_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Warning-bearing artifacts that should stay visible to the audience.",
    )
    refusal_or_quarantine_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Validation-gate artifacts reflecting refusal or quarantine outcomes when present.",
    )
    key_findings: list[str] = Field(
        default_factory=list,
        description="Grounded research findings surfaced from the underlying artifacts.",
    )
    uncertainty_notes: list[str] = Field(
        default_factory=list,
        description="Explicit uncertainty or confidence caveats.",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Important missing evidence or incomplete context.",
    )
    summary: str = Field(description="Concise grounded summary for the brief.")
    provenance: ProvenanceRecord = Field(description="Traceability for the research summary.")

    @model_validator(mode="after")
    def validate_summary(self) -> ResearchSummary:
        """Require explicit linkage and non-empty summary text."""

        if not self.research_brief_id:
            raise ValueError("research_brief_id must be non-empty.")
        if not self.company_id:
            raise ValueError("company_id must be non-empty.")
        if not self.source_artifact_ids:
            raise ValueError("source_artifact_ids must contain at least one artifact identifier.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class RiskSummary(TimestampedModel):
    """Grounded risk summary for one portfolio proposal."""

    risk_summary_id: str = Field(description="Canonical risk-summary identifier.")
    portfolio_proposal_id: str = Field(description="Portfolio-proposal identifier summarized.")
    risk_check_ids: list[str] = Field(
        default_factory=list,
        description="Risk-check identifiers included in the summary.",
    )
    stress_test_result_ids: list[str] = Field(
        default_factory=list,
        description="Stress-test result identifiers included in the summary.",
    )
    validation_gate_ids: list[str] = Field(
        default_factory=list,
        description="Validation-gate identifiers included in the summary.",
    )
    reconciliation_report_id: str | None = Field(
        default=None,
        description="Reconciliation-report identifier when present.",
    )
    source_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts directly supporting the summary.",
    )
    warning_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Warning-bearing artifacts that should stay visible to the audience.",
    )
    blocking_findings: list[str] = Field(
        default_factory=list,
        description="Explicit blocking findings for the proposal.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-blocking warnings surfaced by the summary.",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Important missing or incomplete risk context.",
    )
    summary: str = Field(description="Concise grounded risk summary.")
    provenance: ProvenanceRecord = Field(description="Traceability for the risk summary.")

    @model_validator(mode="after")
    def validate_risk_summary(self) -> RiskSummary:
        """Require explicit proposal linkage and non-empty summary text."""

        if not self.portfolio_proposal_id:
            raise ValueError("portfolio_proposal_id must be non-empty.")
        if not self.source_artifact_ids:
            raise ValueError("source_artifact_ids must contain at least one artifact identifier.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class ReviewQueueSummary(TimestampedModel):
    """Snapshot-style summary of the current operator review queue."""

    review_queue_summary_id: str = Field(description="Canonical review-queue summary identifier.")
    queue_item_ids: list[str] = Field(
        default_factory=list,
        description="Queue-item identifiers included in the summary snapshot.",
    )
    counts_by_target_type: dict[str, int] = Field(
        default_factory=dict,
        description="Counts keyed by review target type.",
    )
    counts_by_queue_status: dict[str, int] = Field(
        default_factory=dict,
        description="Counts keyed by review queue status.",
    )
    escalated_item_ids: list[str] = Field(
        default_factory=list,
        description="Queue-item identifiers currently escalated.",
    )
    unassigned_item_ids: list[str] = Field(
        default_factory=list,
        description="Queue-item identifiers without an active assignee.",
    )
    attention_required_item_ids: list[str] = Field(
        default_factory=list,
        description="Queue-item identifiers requiring explicit operator attention.",
    )
    source_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Underlying queue-item identifiers summarized by the report.",
    )
    warning_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Queue items or related artifacts carrying visible warnings.",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Missing queue metadata that limited summary quality.",
    )
    summary: str = Field(description="Concise grounded queue summary.")
    provenance: ProvenanceRecord = Field(description="Traceability for the review-queue summary.")

    @model_validator(mode="after")
    def validate_queue_summary(self) -> ReviewQueueSummary:
        """Require non-negative counts and summary text."""

        if any(count < 0 for count in self.counts_by_target_type.values()):
            raise ValueError("counts_by_target_type values must be non-negative.")
        if any(count < 0 for count in self.counts_by_queue_status.values()):
            raise ValueError("counts_by_queue_status values must be non-negative.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class ExperimentScorecard(TimestampedModel):
    """Explicit scorecard summarizing experiment and evaluation state."""

    experiment_scorecard_id: str = Field(description="Canonical experiment-scorecard identifier.")
    experiment_id: str = Field(description="Experiment identifier summarized by the scorecard.")
    evaluation_report_id: str | None = Field(
        default=None,
        description="Evaluation-report identifier when one exists.",
    )
    experiment_metric_ids: list[str] = Field(
        default_factory=list,
        description="Experiment-metric identifiers summarized by the scorecard.",
    )
    failure_case_ids: list[str] = Field(
        default_factory=list,
        description="Failure-case identifiers surfaced by the scorecard.",
    )
    robustness_check_ids: list[str] = Field(
        default_factory=list,
        description="Robustness-check identifiers surfaced by the scorecard.",
    )
    realism_warning_ids: list[str] = Field(
        default_factory=list,
        description="Realism-warning identifiers surfaced by the scorecard.",
    )
    validation_gate_ids: list[str] = Field(
        default_factory=list,
        description="Validation-gate identifiers surfaced by the scorecard.",
    )
    measures: list[ScorecardMeasure] = Field(
        default_factory=list,
        description="Explicit measures included in the scorecard.",
    )
    warning_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Warning-bearing artifacts that should remain visible.",
    )
    source_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts directly supporting the scorecard.",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Missing evaluation or experiment context.",
    )
    summary: str = Field(description="Concise grounded experiment summary.")
    provenance: ProvenanceRecord = Field(description="Traceability for the experiment scorecard.")

    @model_validator(mode="after")
    def validate_experiment_scorecard(self) -> ExperimentScorecard:
        """Require explicit experiment linkage and at least one measure."""

        if not self.experiment_id:
            raise ValueError("experiment_id must be non-empty.")
        if not self.measures:
            raise ValueError("measures must contain at least one scorecard measure.")
        if not self.source_artifact_ids:
            raise ValueError("source_artifact_ids must contain at least one artifact identifier.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class ProposalScorecard(TimestampedModel):
    """Explicit scorecard summarizing one portfolio proposal."""

    proposal_scorecard_id: str = Field(description="Canonical proposal-scorecard identifier.")
    portfolio_proposal_id: str = Field(description="Portfolio-proposal identifier summarized.")
    portfolio_selection_summary_id: str | None = Field(
        default=None,
        description="Portfolio-selection summary identifier when available.",
    )
    portfolio_attribution_id: str | None = Field(
        default=None,
        description="Portfolio-attribution identifier when available.",
    )
    stress_test_run_id: str | None = Field(
        default=None,
        description="Stress-test run identifier when available.",
    )
    reconciliation_report_id: str | None = Field(
        default=None,
        description="Reconciliation-report identifier when available.",
    )
    risk_check_ids: list[str] = Field(
        default_factory=list,
        description="Risk-check identifiers surfaced by the scorecard.",
    )
    validation_gate_ids: list[str] = Field(
        default_factory=list,
        description="Validation-gate identifiers surfaced by the scorecard.",
    )
    construction_decision_ids: list[str] = Field(
        default_factory=list,
        description="Construction-decision identifiers surfaced by the scorecard.",
    )
    position_sizing_rationale_ids: list[str] = Field(
        default_factory=list,
        description="Position-sizing rationale identifiers surfaced by the scorecard.",
    )
    stress_test_result_ids: list[str] = Field(
        default_factory=list,
        description="Stress-test result identifiers surfaced by the scorecard.",
    )
    paper_trade_ids: list[str] = Field(
        default_factory=list,
        description="Paper-trade identifiers linked to the proposal when present.",
    )
    measures: list[ScorecardMeasure] = Field(
        default_factory=list,
        description="Explicit measures included in the scorecard.",
    )
    blocking_findings: list[str] = Field(
        default_factory=list,
        description="Blocking findings carried into the scorecard.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-blocking warnings carried into the scorecard.",
    )
    source_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts directly supporting the scorecard.",
    )
    warning_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Warning-bearing artifacts that should remain visible.",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Missing risk, stress, or downstream context.",
    )
    summary: str = Field(description="Concise grounded proposal summary.")
    provenance: ProvenanceRecord = Field(description="Traceability for the proposal scorecard.")

    @model_validator(mode="after")
    def validate_proposal_scorecard(self) -> ProposalScorecard:
        """Require explicit proposal linkage and at least one measure."""

        if not self.portfolio_proposal_id:
            raise ValueError("portfolio_proposal_id must be non-empty.")
        if not self.measures:
            raise ValueError("measures must contain at least one scorecard measure.")
        if not self.source_artifact_ids:
            raise ValueError("source_artifact_ids must contain at least one artifact identifier.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class DailySystemReport(TimestampedModel):
    """Operator-facing daily report grounded in monitoring, queue, and paper-book state."""

    daily_system_report_id: str = Field(description="Canonical daily-system-report identifier.")
    report_date: date = Field(description="Date summarized by the report.")
    run_summary_ids: list[str] = Field(
        default_factory=list,
        description="Recent run-summary identifiers included in the report.",
    )
    alert_record_ids: list[str] = Field(
        default_factory=list,
        description="Open or recent alert-record identifiers included in the report.",
    )
    service_statuses: list[ServiceStatus] = Field(
        default_factory=list,
        description="Current derived service-status snapshots included in the report.",
    )
    review_queue_summary_id: str | None = Field(
        default=None,
        description="Review-queue summary identifier included in the report when available.",
    )
    daily_paper_summary_ids: list[str] = Field(
        default_factory=list,
        description="Daily paper-summary identifiers included in the report.",
    )
    open_review_followup_ids: list[str] = Field(
        default_factory=list,
        description="Open paper-ledger review-followup identifiers included in the report.",
    )
    proposal_scorecard_ids: list[str] = Field(
        default_factory=list,
        description="Proposal-scorecard identifiers included in the report.",
    )
    experiment_scorecard_ids: list[str] = Field(
        default_factory=list,
        description="Experiment-scorecard identifiers included in the report.",
    )
    source_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts directly supporting the report.",
    )
    notable_failures: list[str] = Field(
        default_factory=list,
        description="Concise notable failures highlighted for operators.",
    )
    attention_reasons: list[str] = Field(
        default_factory=list,
        description="Visible attention reasons highlighted for operators.",
    )
    missing_information: list[str] = Field(
        default_factory=list,
        description="Missing data or incomplete coverage for the report.",
    )
    summary: str = Field(description="Concise grounded daily system summary.")
    provenance: ProvenanceRecord = Field(description="Traceability for the daily system report.")

    @model_validator(mode="after")
    def validate_daily_report(self) -> DailySystemReport:
        """Require a date-scoped summary."""

        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class SystemCapabilitySummary(TimestampedModel):
    """Grounded capability snapshot for one subsystem or workflow family."""

    system_capability_summary_id: str = Field(
        description="Canonical system-capability-summary identifier."
    )
    capability_name: str = Field(description="Capability or subsystem name summarized.")
    service_names: list[str] = Field(
        default_factory=list,
        description="Registered services contributing to the capability.",
    )
    evidence_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts demonstrating current capability behavior.",
    )
    recent_run_summary_ids: list[str] = Field(
        default_factory=list,
        description="Recent run-summary identifiers informing the snapshot.",
    )
    alert_record_ids: list[str] = Field(
        default_factory=list,
        description="Alert identifiers informing the snapshot.",
    )
    current_limitations: list[str] = Field(
        default_factory=list,
        description="Important current limitations that should stay visible.",
    )
    maturity_notes: list[str] = Field(
        default_factory=list,
        description="Explicit maturity or coverage notes for the capability.",
    )
    source_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts directly supporting the summary.",
    )
    warning_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Warning-bearing artifacts that should remain visible.",
    )
    summary: str = Field(description="Concise grounded capability summary.")
    provenance: ProvenanceRecord = Field(description="Traceability for the capability summary.")

    @model_validator(mode="after")
    def validate_capability_summary(self) -> SystemCapabilitySummary:
        """Require explicit capability naming and summary text."""

        if not self.capability_name:
            raise ValueError("capability_name must be non-empty.")
        if not self.service_names:
            raise ValueError("service_names must contain at least one service.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self
