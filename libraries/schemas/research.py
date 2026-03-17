from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import Field, model_validator

from libraries.schemas.base import (
    AgentRunStatus,
    BacktestStatus,
    ConfidenceAssessment,
    DataLayer,
    ExperimentStatus,
    FeatureStatus,
    HypothesisStatus,
    MemoStatus,
    ProvenanceRecord,
    SignalStatus,
    TimestampedModel,
)


class ResearchStance(StrEnum):
    """Research-layer view classification, deliberately separate from trading side."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED = "mixed"
    MONITOR = "monitor"


class ResearchReviewStatus(StrEnum):
    """Human-review status for research artifacts before downstream promotion."""

    DRAFT = "draft"
    PENDING_HUMAN_REVIEW = "pending_human_review"
    REVISION_REQUESTED = "revision_requested"
    APPROVED_FOR_FEATURE_WORK = "approved_for_feature_work"
    REJECTED = "rejected"


class ResearchValidationStatus(StrEnum):
    """Validation lifecycle for research artifacts, separate from human review."""

    UNVALIDATED = "unvalidated"
    PENDING_VALIDATION = "pending_validation"
    PARTIALLY_VALIDATED = "partially_validated"
    VALIDATED = "validated"
    INVALIDATED = "invalidated"


class EvidenceLinkRole(StrEnum):
    """How an evidence link is used inside a research artifact."""

    SUPPORT = "support"
    CONTRADICT = "contradict"
    CONTEXT = "context"


class EvidenceGrade(StrEnum):
    """Strength of evidence backing a research thesis."""

    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"
    INSUFFICIENT = "insufficient"


class CritiqueKind(StrEnum):
    """Structured critique categories used by counter-hypotheses."""

    CONTRADICTORY_EVIDENCE = "contradictory_evidence"
    MISSING_EVIDENCE = "missing_evidence"
    ASSUMPTION_RISK = "assumption_risk"
    CAUSAL_GAP = "causal_gap"


class FeatureFamily(StrEnum):
    """Top-level feature families used for ablation and grouping."""

    PRICE = "price"
    FUNDAMENTALS = "fundamentals"
    TEXT_DERIVED = "text_derived"
    MACRO = "macro"


class AblationView(StrEnum):
    """Feature-set slices used for honest future ablations."""

    PRICE_ONLY = "price_only"
    FUNDAMENTALS_ONLY = "fundamentals_only"
    TEXT_ONLY = "text_only"
    COMBINED = "combined"


class DerivedArtifactValidationStatus(StrEnum):
    """Validation lifecycle for downstream feature and signal artifacts."""

    UNVALIDATED = "unvalidated"
    PENDING_VALIDATION = "pending_validation"
    PARTIALLY_VALIDATED = "partially_validated"
    VALIDATED = "validated"
    INVALIDATED = "invalidated"


class FeatureValueType(StrEnum):
    """Typed value families supported by Day 5 features."""

    NUMERIC = "numeric"
    TEXT = "text"
    BOOLEAN = "boolean"


class SupportingEvidenceLink(TimestampedModel):
    """Exact research-layer link back to one extracted evidence span."""

    supporting_evidence_link_id: str = Field(
        description="Canonical supporting-evidence link identifier."
    )
    source_reference_id: str = Field(description="Source reference that contains the evidence.")
    document_id: str = Field(description="Document that contains the evidence.")
    evidence_span_id: str = Field(description="Exact evidence span grounding the link.")
    extracted_artifact_id: str | None = Field(
        default=None,
        description="Optional upstream extracted artifact identifier such as a claim or risk factor.",
    )
    role: EvidenceLinkRole = Field(description="How the evidence is used in the research artifact.")
    quote: str = Field(description="Exact quoted text from the linked evidence span.")
    note: str | None = Field(
        default=None,
        description="Short note explaining how the evidence supports or challenges the thesis.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for how the link was assembled.")

    @model_validator(mode="after")
    def validate_quote(self) -> SupportingEvidenceLink:
        """Ensure evidence links always carry exact source text."""

        if not self.quote:
            raise ValueError("quote must be non-empty.")
        return self


class EvidenceAssessment(TimestampedModel):
    """Structured evaluation of the support and gaps for a hypothesis."""

    evidence_assessment_id: str = Field(description="Canonical evidence-assessment identifier.")
    company_id: str = Field(description="Covered company identifier.")
    hypothesis_id: str | None = Field(
        default=None,
        description="Hypothesis under review when the assessment is attached to a thesis.",
    )
    grade: EvidenceGrade = Field(description="Structured support grade.")
    supporting_evidence_link_ids: list[str] = Field(
        default_factory=list,
        description="Evidence links used as primary support.",
    )
    support_summary: str = Field(description="Short summary of what the current evidence supports.")
    key_gaps: list[str] = Field(
        default_factory=list,
        description="Important evidence gaps still preventing stronger confidence.",
    )
    contradiction_notes: list[str] = Field(
        default_factory=list,
        description="Observed contradictory or cautionary evidence notes.",
    )
    review_status: ResearchReviewStatus = Field(
        description="Human-review status for the assessment."
    )
    validation_status: ResearchValidationStatus = Field(
        description="Validation lifecycle status for the assessment."
    )
    confidence: ConfidenceAssessment | None = Field(
        default=None,
        description="Conservative confidence and uncertainty assessment for the support grade.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the evidence assessment.")

    @model_validator(mode="after")
    def validate_summary(self) -> EvidenceAssessment:
        """Require a non-empty support summary."""

        if not self.support_summary:
            raise ValueError("support_summary must be non-empty.")
        return self


class Hypothesis(TimestampedModel):
    """Forward-looking research thesis supported by explicit evidence and assumptions."""

    hypothesis_id: str = Field(description="Canonical hypothesis identifier.")
    company_id: str = Field(description="Covered company identifier.")
    title: str = Field(description="Short hypothesis title.")
    thesis: str = Field(description="Primary research thesis statement.")
    stance: ResearchStance = Field(description="Research stance implied by the thesis.")
    status: HypothesisStatus = Field(description="Hypothesis lifecycle status.")
    review_status: ResearchReviewStatus = Field(
        description="Human-review status for the hypothesis."
    )
    validation_status: ResearchValidationStatus = Field(
        description="Validation lifecycle status for the hypothesis."
    )
    time_horizon: str = Field(
        description="Qualitative time horizon, for example `next_2_4_quarters`."
    )
    catalyst: str | None = Field(default=None, description="Expected validating event if known.")
    invalidation_conditions: list[str] = Field(
        default_factory=list,
        description="Observable conditions that would invalidate the thesis.",
    )
    supporting_evidence_links: list[SupportingEvidenceLink] = Field(
        default_factory=list,
        description="Exact evidence links directly supporting the thesis.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Explicit assumptions that are not yet verified by evidence.",
    )
    uncertainties: list[str] = Field(
        default_factory=list,
        description="Material uncertainties that a reviewer should keep visible.",
    )
    validation_steps: list[str] = Field(
        default_factory=list,
        description="Concrete next checks needed before downstream promotion.",
    )
    evidence_assessment_id: str | None = Field(
        default=None,
        description="Evidence assessment associated with the hypothesis when available.",
    )
    confidence: ConfidenceAssessment | None = Field(
        default=None,
        description="Confidence and uncertainty assessment for the thesis.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the hypothesis.")

    @model_validator(mode="after")
    def validate_support(self) -> Hypothesis:
        """Require directly linked support and explicit review path."""

        if not self.supporting_evidence_links:
            raise ValueError("supporting_evidence_links must contain at least one link.")
        if not self.validation_steps:
            raise ValueError("validation_steps must contain at least one next step.")
        return self


class CounterHypothesis(TimestampedModel):
    """Adversarial counter-thesis designed to challenge a primary hypothesis honestly."""

    counter_hypothesis_id: str = Field(description="Canonical counter-hypothesis identifier.")
    hypothesis_id: str = Field(description="Primary hypothesis being challenged.")
    title: str = Field(description="Short counter-thesis title.")
    thesis: str = Field(description="Concise statement of the opposing or cautionary case.")
    critique_kinds: list[CritiqueKind] = Field(
        default_factory=list,
        description="Structured critique categories surfaced by the counter-thesis.",
    )
    supporting_evidence_links: list[SupportingEvidenceLink] = Field(
        default_factory=list,
        description="Evidence links that contradict or contextualize the thesis.",
    )
    challenged_assumptions: list[str] = Field(
        default_factory=list,
        description="Primary assumptions challenged by the critique.",
    )
    missing_evidence: list[str] = Field(
        default_factory=list,
        description="Evidence still missing before the thesis can be trusted more fully.",
    )
    causal_gaps: list[str] = Field(
        default_factory=list,
        description="Potential breaks between the cited facts and the claimed mechanism.",
    )
    unresolved_questions: list[str] = Field(
        default_factory=list,
        description="Questions still unresolved after critique.",
    )
    review_status: ResearchReviewStatus = Field(
        description="Human-review status for the counter-hypothesis."
    )
    validation_status: ResearchValidationStatus = Field(
        description="Validation lifecycle status for the counter-hypothesis."
    )
    confidence: ConfidenceAssessment | None = Field(
        default=None,
        description="Conservative confidence and uncertainty assessment for the critique.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the counter-hypothesis.")

    @model_validator(mode="after")
    def validate_critique_basis(self) -> CounterHypothesis:
        """Require concrete critique content instead of empty objection text."""

        if not self.critique_kinds:
            raise ValueError("critique_kinds must contain at least one critique category.")
        if not any(
            [
                self.supporting_evidence_links,
                self.challenged_assumptions,
                self.missing_evidence,
                self.causal_gaps,
                self.unresolved_questions,
            ]
        ):
            raise ValueError("CounterHypothesis requires at least one concrete critique basis.")
        return self


class ResearchBrief(TimestampedModel):
    """Structured memo-ready research artifact for human review."""

    research_brief_id: str = Field(description="Canonical research-brief identifier.")
    company_id: str = Field(description="Covered company identifier.")
    title: str = Field(description="Short review title for the brief.")
    context_summary: str = Field(description="Compact company and document context summary.")
    core_hypothesis: str = Field(description="Core hypothesis statement for review.")
    counter_hypothesis_summary: str = Field(
        description="Primary counter-hypothesis or critique summary."
    )
    hypothesis_id: str = Field(description="Primary hypothesis summarized in the brief.")
    counter_hypothesis_id: str = Field(
        description="Primary counter-hypothesis summarized in the brief."
    )
    evidence_assessment_id: str = Field(description="Evidence assessment backing the brief.")
    supporting_evidence_links: list[SupportingEvidenceLink] = Field(
        default_factory=list,
        description="Primary evidence links included for review.",
    )
    key_counterarguments: list[str] = Field(
        default_factory=list,
        description="Concise counterarguments or challenge points.",
    )
    confidence: ConfidenceAssessment | None = Field(
        default=None,
        description="Conservative confidence and uncertainty assessment for the brief.",
    )
    uncertainty_summary: str = Field(description="Compact summary of the open uncertainty.")
    review_status: ResearchReviewStatus = Field(
        description="Human-review status for the brief."
    )
    validation_status: ResearchValidationStatus = Field(
        description="Validation lifecycle status for the brief."
    )
    next_validation_steps: list[str] = Field(
        default_factory=list,
        description="Concrete next checks a researcher should perform.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the research brief.")

    @model_validator(mode="after")
    def validate_brief(self) -> ResearchBrief:
        """Require evidence-backed content and clear next actions."""

        if not self.supporting_evidence_links:
            raise ValueError("supporting_evidence_links must contain at least one link.")
        if not self.next_validation_steps:
            raise ValueError("next_validation_steps must contain at least one step.")
        return self


class FeatureDefinition(TimestampedModel):
    """Stable definition for a reusable candidate feature."""

    feature_definition_id: str = Field(description="Canonical feature-definition identifier.")
    name: str = Field(description="Stable feature name.")
    family: FeatureFamily = Field(description="Feature family used for grouping and ablation.")
    value_type: FeatureValueType = Field(description="Expected value type for feature values.")
    description: str = Field(description="Human-readable description of what the feature measures.")
    unit: str | None = Field(default=None, description="Optional unit for numeric values.")
    ablation_views: list[AblationView] = Field(
        default_factory=list,
        description="Ablation slices where the feature can participate.",
    )
    status: FeatureStatus = Field(description="Feature-definition lifecycle status.")
    validation_status: DerivedArtifactValidationStatus = Field(
        description="Validation lifecycle status for the feature definition."
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the feature definition.")

    @model_validator(mode="after")
    def validate_definition(self) -> FeatureDefinition:
        """Require at least one ablation view and a non-empty description."""

        if not self.description:
            raise ValueError("description must be non-empty.")
        if not self.ablation_views:
            raise ValueError("ablation_views must contain at least one value.")
        return self


class FeatureValue(TimestampedModel):
    """Point-in-time materialized value for a feature definition."""

    feature_value_id: str = Field(description="Canonical feature-value identifier.")
    feature_definition_id: str = Field(description="Feature definition that owns this value.")
    as_of_date: date = Field(description="Logical business date the feature describes.")
    available_at: datetime = Field(
        description="UTC time when the feature value becomes available downstream."
    )
    numeric_value: float | None = Field(
        default=None, description="Numeric feature value when applicable."
    )
    text_value: str | None = Field(
        default=None, description="Textual feature value when applicable."
    )
    boolean_value: bool | None = Field(
        default=None, description="Boolean feature value when applicable."
    )
    confidence: ConfidenceAssessment | None = Field(
        default=None,
        description="Conservative confidence assessment for the materialized value.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the feature value.")

    @model_validator(mode="after")
    def validate_single_value(self) -> FeatureValue:
        """Ensure exactly one feature value field is populated."""

        populated = [
            self.numeric_value is not None,
            self.text_value is not None,
            self.boolean_value is not None,
        ]
        if sum(populated) != 1:
            raise ValueError(
                "Exactly one of numeric_value, text_value, or boolean_value must be set."
            )
        return self


class FeatureLineage(TimestampedModel):
    """Exact upstream research and evidence lineage for a candidate feature."""

    feature_lineage_id: str = Field(description="Canonical feature-lineage identifier.")
    hypothesis_id: str = Field(description="Upstream hypothesis identifier.")
    counter_hypothesis_id: str = Field(description="Upstream counter-hypothesis identifier.")
    evidence_assessment_id: str = Field(description="Upstream evidence-assessment identifier.")
    research_brief_id: str = Field(description="Upstream research-brief identifier.")
    supporting_evidence_link_ids: list[str] = Field(
        default_factory=list,
        description="Supporting evidence link identifiers grounding the feature.",
    )
    source_document_ids: list[str] = Field(
        default_factory=list,
        description="Source document identifiers referenced by the lineage.",
    )

    @model_validator(mode="after")
    def validate_lineage(self) -> FeatureLineage:
        """Require exact evidence-link and document references."""

        if not self.supporting_evidence_link_ids:
            raise ValueError("supporting_evidence_link_ids must contain at least one value.")
        if not self.source_document_ids:
            raise ValueError("source_document_ids must contain at least one value.")
        return self


class Feature(TimestampedModel):
    """Primary candidate feature artifact with definition, value, and lineage."""

    feature_id: str = Field(description="Canonical feature identifier.")
    entity_id: str = Field(
        description="Entity the feature applies to, such as company or portfolio."
    )
    company_id: str | None = Field(
        default=None, description="Associated company identifier when applicable."
    )
    data_layer: DataLayer = Field(
        default=DataLayer.DERIVED,
        description="Artifact layer for the candidate feature.",
    )
    feature_definition: FeatureDefinition = Field(description="Stable feature definition.")
    feature_value: FeatureValue = Field(description="Point-in-time feature value.")
    status: FeatureStatus = Field(description="Feature lifecycle status.")
    validation_status: DerivedArtifactValidationStatus = Field(
        description="Validation lifecycle status for the feature."
    )
    lineage: FeatureLineage = Field(description="Exact upstream lineage for the feature.")
    assumptions: list[str] = Field(
        default_factory=list,
        description="Explicit assumptions required to interpret the feature responsibly.",
    )
    confidence: ConfidenceAssessment | None = Field(
        default=None,
        description="Confidence and uncertainty assessment for the feature artifact.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the feature.")

    @model_validator(mode="after")
    def validate_feature_contract(self) -> Feature:
        """Require aligned definition/value identifiers and exact lineage."""

        if self.feature_definition.feature_definition_id != self.feature_value.feature_definition_id:
            raise ValueError("Feature definition and value must reference the same definition ID.")
        return self


class SignalScore(TimestampedModel):
    """Scored component used to evaluate a signal candidate."""

    signal_score_id: str = Field(description="Canonical signal score identifier.")
    metric_name: str = Field(description="Name of the scoring metric.")
    value: float = Field(description="Raw score value.")
    scale_min: float | None = Field(
        default=None, description="Lower bound of the score scale if known."
    )
    scale_max: float | None = Field(
        default=None, description="Upper bound of the score scale if known."
    )
    validation_status: DerivedArtifactValidationStatus = Field(
        description="Validation lifecycle status for the score component."
    )
    source_feature_ids: list[str] = Field(
        default_factory=list,
        description="Feature identifiers used to compute this component.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Explicit assumptions attached to the component score.",
    )
    calibrated_probability: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional probability derived from model calibration.",
    )
    confidence: ConfidenceAssessment | None = Field(
        default=None,
        description="Confidence and uncertainty assessment for the score.",
    )
    rationale: str | None = Field(default=None, description="Short explanation for the score.")
    provenance: ProvenanceRecord = Field(description="Traceability for the score component.")

    @model_validator(mode="after")
    def validate_score_sources(self) -> SignalScore:
        """Require score components to identify their contributing features."""

        if not self.source_feature_ids:
            raise ValueError("source_feature_ids must contain at least one feature identifier.")
        return self


class SignalLineage(TimestampedModel):
    """Exact upstream lineage for a candidate signal."""

    signal_lineage_id: str = Field(description="Canonical signal-lineage identifier.")
    feature_ids: list[str] = Field(
        default_factory=list,
        description="Feature identifiers used to build the signal.",
    )
    feature_definition_ids: list[str] = Field(
        default_factory=list,
        description="Feature definition identifiers used to build the signal.",
    )
    feature_value_ids: list[str] = Field(
        default_factory=list,
        description="Feature value identifiers used to build the signal.",
    )
    research_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Upstream research artifact identifiers informing the signal.",
    )
    supporting_evidence_link_ids: list[str] = Field(
        default_factory=list,
        description="Evidence-link identifiers grounding the signal lineage.",
    )
    input_families: list[FeatureFamily] = Field(
        default_factory=list,
        description="Feature families included in the signal input mix.",
    )

    @model_validator(mode="after")
    def validate_signal_lineage(self) -> SignalLineage:
        """Require feature and evidence lineage for every signal."""

        if not self.feature_ids:
            raise ValueError("feature_ids must contain at least one feature identifier.")
        if not self.supporting_evidence_link_ids:
            raise ValueError(
                "supporting_evidence_link_ids must contain at least one evidence link identifier."
            )
        if not self.input_families:
            raise ValueError("input_families must contain at least one feature family.")
        return self


class Signal(TimestampedModel):
    """Research signal derived from features, evidence, and reviewed hypotheses."""

    signal_id: str = Field(description="Canonical signal identifier.")
    company_id: str = Field(description="Covered company identifier.")
    hypothesis_id: str = Field(description="Primary hypothesis driving the signal.")
    signal_family: str = Field(description="Stable signal family name.")
    stance: ResearchStance = Field(description="Research-layer stance implied by the signal.")
    ablation_view: AblationView = Field(description="Ablation slice used to build the signal.")
    thesis_summary: str = Field(description="Short explanation of the signal.")
    feature_ids: list[str] = Field(
        default_factory=list, description="Feature identifiers used to build the signal."
    )
    component_scores: list[SignalScore] = Field(
        default_factory=list,
        description="Supporting signal score components.",
    )
    primary_score: float = Field(description="Primary normalized score for downstream ranking.")
    effective_at: datetime = Field(description="UTC time when the signal becomes active.")
    expires_at: datetime | None = Field(default=None, description="UTC expiry time for the signal.")
    status: SignalStatus = Field(description="Signal lifecycle status.")
    validation_status: DerivedArtifactValidationStatus = Field(
        description="Validation lifecycle status for the signal."
    )
    lineage: SignalLineage = Field(description="Exact upstream lineage for the signal.")
    assumptions: list[str] = Field(
        default_factory=list,
        description="Explicit assumptions required to interpret the signal responsibly.",
    )
    uncertainties: list[str] = Field(
        default_factory=list,
        description="Open uncertainties still limiting trust in the signal.",
    )
    confidence: ConfidenceAssessment | None = Field(
        default=None,
        description="Confidence and uncertainty assessment for the signal.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the signal.")

    @model_validator(mode="after")
    def validate_signal_window(self) -> Signal:
        """Ensure a signal cannot expire before it becomes effective."""

        if not self.feature_ids:
            raise ValueError("feature_ids must contain at least one feature identifier.")
        if self.expires_at is not None and self.expires_at < self.effective_at:
            raise ValueError("expires_at must be greater than or equal to effective_at.")
        return self


class BacktestRun(TimestampedModel):
    """Metadata for a temporally controlled backtest execution."""

    backtest_run_id: str = Field(description="Canonical backtest run identifier.")
    experiment_id: str = Field(description="Experiment identifier that owns the run.")
    strategy_name: str = Field(description="Strategy or signal family under evaluation.")
    status: BacktestStatus = Field(description="Backtest execution status.")
    train_start: date | None = Field(default=None, description="Training window start date.")
    train_end: date | None = Field(default=None, description="Training window end date.")
    test_start: date = Field(description="Out-of-sample test window start date.")
    test_end: date = Field(description="Out-of-sample test window end date.")
    decision_cutoff_time: datetime = Field(
        description="UTC cutoff representing the maximum information set available during the run."
    )
    rebalance_frequency: str = Field(description="Rebalance cadence used by the run.")
    universe_definition: str = Field(description="Point-in-time universe definition.")
    leakage_checks: list[str] = Field(
        default_factory=list,
        description="Leakage checks executed as part of the run.",
    )
    result_artifact_uri: str | None = Field(
        default=None,
        description="URI to serialized results, reports, or diagnostics.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the backtest run.")

    @model_validator(mode="after")
    def validate_backtest_windows(self) -> BacktestRun:
        """Ensure declared training and test windows are ordered correctly."""

        if self.test_end < self.test_start:
            raise ValueError("test_end must be greater than or equal to test_start.")
        if (
            self.train_start is not None
            and self.train_end is not None
            and self.train_end < self.train_start
        ):
            raise ValueError("train_end must be greater than or equal to train_start.")
        return self


class Experiment(TimestampedModel):
    """Track a research experiment, including datasets, hypotheses, and runs."""

    experiment_id: str = Field(description="Canonical experiment identifier.")
    name: str = Field(description="Experiment name.")
    objective: str = Field(description="Research objective or question under study.")
    created_by: str = Field(description="Analyst or workflow that created the experiment.")
    status: ExperimentStatus = Field(description="Experiment lifecycle status.")
    dataset_snapshot_id: str | None = Field(
        default=None,
        description="Point-in-time dataset snapshot used by the experiment.",
    )
    hypothesis_ids: list[str] = Field(
        default_factory=list,
        description="Hypotheses under study in the experiment.",
    )
    backtest_run_ids: list[str] = Field(
        default_factory=list,
        description="Backtest runs associated with the experiment.",
    )
    notes: list[str] = Field(
        default_factory=list, description="Operational notes for the experiment."
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the experiment.")


class Memo(TimestampedModel):
    """Research memo artifact intended for PMs, reviewers, or risk partners."""

    memo_id: str = Field(description="Canonical memo identifier.")
    title: str = Field(description="Memo title.")
    status: MemoStatus = Field(description="Memo lifecycle status.")
    audience: str = Field(description="Primary intended audience.")
    generated_at: datetime = Field(description="UTC timestamp when the memo was generated.")
    author_agent_run_id: str | None = Field(
        default=None, description="Agent run that generated the memo."
    )
    related_hypothesis_ids: list[str] = Field(
        default_factory=list,
        description="Hypotheses summarized in the memo.",
    )
    related_portfolio_proposal_id: str | None = Field(
        default=None,
        description="Portfolio proposal discussed in the memo, if applicable.",
    )
    executive_summary: str = Field(description="Short executive summary.")
    key_points: list[str] = Field(
        default_factory=list, description="Main points highlighted in the memo."
    )
    key_risks: list[str] = Field(
        default_factory=list, description="Material risks called out in the memo."
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Open questions still requiring research or human judgment.",
    )
    content_uri: str | None = Field(
        default=None, description="URI to the full memo content or render."
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the memo.")


class AgentRun(TimestampedModel):
    """Operational metadata for an individual agent execution."""

    agent_run_id: str = Field(description="Canonical agent run identifier.")
    agent_name: str = Field(description="Stable agent name.")
    agent_version: str = Field(description="Agent version or release tag.")
    objective: str = Field(description="Run objective or prompt purpose.")
    model_name: str | None = Field(
        default=None, description="Model used for the run when applicable."
    )
    prompt_version: str | None = Field(default=None, description="Prompt or policy version used.")
    input_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Input artifact identifiers provided to the run.",
    )
    output_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Output artifact identifiers produced by the run.",
    )
    status: AgentRunStatus = Field(description="Agent run lifecycle status.")
    started_at: datetime = Field(description="UTC timestamp when the run started.")
    completed_at: datetime | None = Field(
        default=None, description="UTC timestamp when the run completed."
    )
    human_review_required: bool = Field(
        default=True,
        description="Whether a human must review or approve the output.",
    )
    escalation_reason: str | None = Field(
        default=None, description="Reason for escalation when applicable."
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the run.")
