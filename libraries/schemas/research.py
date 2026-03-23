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
    Severity,
    SignalStatus,
    TimestampedModel,
)
from libraries.schemas.timing import AvailabilityWindow, DecisionCutoff


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

    NAIVE = "naive"
    PRICE_ONLY = "price_only"
    FUNDAMENTALS_ONLY = "fundamentals_only"
    TEXT_ONLY = "text_only"
    COMBINED = "combined"


class StrategyFamily(StrEnum):
    """Comparable strategy families used by the ablation harness."""

    NAIVE_BASELINE = "naive_baseline"
    PRICE_ONLY_BASELINE = "price_only_baseline"
    TEXT_ONLY_CANDIDATE_BASELINE = "text_only_candidate_baseline"
    COMBINED_BASELINE = "combined_baseline"


class DerivedArtifactValidationStatus(StrEnum):
    """Validation lifecycle for downstream feature and signal artifacts."""

    UNVALIDATED = "unvalidated"
    PENDING_VALIDATION = "pending_validation"
    PARTIALLY_VALIDATED = "partially_validated"
    VALIDATED = "validated"
    INVALIDATED = "invalidated"


class EvaluationStatus(StrEnum):
    """Outcome classification for deterministic evaluation checks."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    NOT_EVALUATED = "not_evaluated"


class EvaluationDimension(StrEnum):
    """Evaluation dimensions the Day 10 layer can judge structurally."""

    PROVENANCE_COMPLETENESS = "provenance_completeness"
    HYPOTHESIS_SUPPORT_QUALITY = "hypothesis_support_quality"
    FEATURE_LINEAGE_COMPLETENESS = "feature_lineage_completeness"
    SIGNAL_GENERATION_VALIDITY = "signal_generation_validity"
    BACKTEST_ARTIFACT_COMPLETENESS = "backtest_artifact_completeness"
    STRATEGY_COMPARISON_OUTPUT = "strategy_comparison_output"
    RISK_REVIEW_COVERAGE = "risk_review_coverage"


class FailureCaseKind(StrEnum):
    """Structured failure classes recorded by the evaluation layer."""

    MISSING_EVIDENCE = "missing_evidence"
    WEAK_SUPPORT = "weak_support"
    INVALID_TIMESTAMP = "invalid_timestamp"
    BROKEN_LINEAGE = "broken_lineage"
    INCOMPLETE_CONFIG = "incomplete_config"
    EMPTY_OUTPUT = "empty_output"
    SUSPICIOUS_ASSUMPTION = "suspicious_assumption"
    SOURCE_INCONSISTENCY = "source_inconsistency"
    MISSING_PROVENANCE = "missing_provenance"


class RobustnessCheckKind(StrEnum):
    """Explicit robustness checks supported by the Day 10 layer."""

    MISSING_DATA_SENSITIVITY = "missing_data_sensitivity"
    TIMESTAMP_ANOMALY = "timestamp_anomaly"
    SOURCE_INCONSISTENCY = "source_inconsistency"
    INCOMPLETE_EXTRACTION_ARTIFACT = "incomplete_extraction_artifact"
    INVALID_STRATEGY_CONFIG = "invalid_strategy_config"


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
    availability_window: AvailabilityWindow | None = Field(
        default=None,
        description="Structured availability window used to derive available_at when present.",
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
        if (
            self.availability_window is not None
            and self.available_at != self.availability_window.available_from
        ):
            raise ValueError(
                "available_at must match availability_window.available_from when an availability window is set."
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
    availability_window: AvailabilityWindow | None = Field(
        default=None,
        description="Structured availability window used to derive effective_at when present.",
    )
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
        if (
            self.availability_window is not None
            and self.effective_at != self.availability_window.available_from
        ):
            raise ValueError(
                "effective_at must match availability_window.available_from when an availability window is set."
            )
        if self.expires_at is not None and self.expires_at < self.effective_at:
            raise ValueError("expires_at must be greater than or equal to effective_at.")
        return self


class DecisionAction(StrEnum):
    """Action implied by a backtest strategy decision."""

    OPEN_LONG = "open_long"
    OPEN_SHORT = "open_short"
    CLOSE_POSITION = "close_position"
    HOLD_POSITION = "hold_position"
    HOLD_CASH = "hold_cash"
    SKIP_SIGNAL = "skip_signal"


class SimulationEventType(StrEnum):
    """Event types recorded by the Day 6 simulation engine."""

    DECISION = "decision"
    FILL = "fill"
    MARK = "mark"
    BENCHMARK_MARK = "benchmark_mark"
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"


class BenchmarkKind(StrEnum):
    """Mechanical benchmark types supported by the Day 6 skeleton."""

    FLAT_BASELINE = "flat_baseline"
    BUY_AND_HOLD = "buy_and_hold"
    PLACEHOLDER = "placeholder"


class ExecutionAssumption(TimestampedModel):
    """Explicit execution and cost assumptions for a backtest run."""

    execution_assumption_id: str = Field(description="Canonical execution-assumption identifier.")
    transaction_cost_bps: float = Field(
        ge=0.0,
        description="One-way transaction cost assumption in basis points.",
    )
    slippage_bps: float = Field(
        ge=0.0,
        description="One-way slippage assumption in basis points.",
    )
    execution_lag_bars: int = Field(
        default=1,
        ge=1,
        description="Number of bars between decision time and execution time.",
    )
    decision_price_field: str = Field(
        default="close",
        description="Price field used to anchor the decision event.",
    )
    execution_price_field: str = Field(
        default="open",
        description="Price field used for simulated execution.",
    )
    signal_availability_buffer_minutes: int | None = Field(
        default=None,
        ge=0,
        description="Optional extra delay between signal availability and eligibility.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the assumption set.")

    @model_validator(mode="after")
    def validate_fields(self) -> ExecutionAssumption:
        """Require explicit supported price fields for the Day 6 skeleton."""

        if self.decision_price_field != "close":
            raise ValueError("Day 6 only supports `close` as the decision_price_field.")
        if self.execution_price_field != "open":
            raise ValueError("Day 6 only supports `open` as the execution_price_field.")
        return self


class BacktestConfig(TimestampedModel):
    """Reproducible configuration for one exploratory Day 6 backtest run."""

    backtest_config_id: str = Field(description="Stable backtest-config identifier.")
    strategy_name: str = Field(description="Human-readable strategy name.")
    signal_family: str = Field(description="Signal family evaluated by the run.")
    ablation_view: AblationView = Field(description="Ablation slice evaluated by the run.")
    test_start: date = Field(description="Backtest window start date.")
    test_end: date = Field(description="Backtest window end date.")
    decision_frequency: str = Field(
        default="daily",
        description="Decision cadence. Day 6 only supports daily decisions.",
    )
    signal_status_allowlist: list[SignalStatus] = Field(
        default_factory=lambda: [SignalStatus.CANDIDATE],
        description="Signal statuses allowed into the exploratory backtest boundary.",
    )
    decision_rule: str = Field(
        default="latest_signal_to_unit_position",
        description="Deterministic Day 6 decision rule name.",
    )
    exploratory_only: bool = Field(
        default=True,
        description="Whether the run is explicitly exploratory and non-promotable.",
    )
    starting_cash: float = Field(
        default=100_000.0,
        gt=0.0,
        description="Starting account value used for simple simulation accounting.",
    )
    execution_assumption: ExecutionAssumption = Field(
        description="Execution assumptions applied by the simulation engine."
    )
    benchmark_kinds: list[BenchmarkKind] = Field(
        default_factory=lambda: [BenchmarkKind.FLAT_BASELINE, BenchmarkKind.BUY_AND_HOLD],
        description="Mechanical benchmarks emitted alongside the strategy run.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the backtest config.")

    @model_validator(mode="after")
    def validate_config(self) -> BacktestConfig:
        """Require a coherent daily exploratory backtest configuration."""

        if self.test_end < self.test_start:
            raise ValueError("test_end must be greater than or equal to test_start.")
        if self.decision_frequency != "daily":
            raise ValueError("Day 6 only supports `daily` decision_frequency.")
        if self.decision_rule != "latest_signal_to_unit_position":
            raise ValueError("Day 6 only supports `latest_signal_to_unit_position`.")
        if not self.signal_status_allowlist:
            raise ValueError("signal_status_allowlist must contain at least one status.")
        if not self.benchmark_kinds:
            raise ValueError("benchmark_kinds must contain at least one benchmark.")
        return self


class StrategyDecision(TimestampedModel):
    """One point-in-time strategy decision made during the backtest."""

    strategy_decision_id: str = Field(description="Canonical strategy-decision identifier.")
    backtest_run_id: str = Field(description="Owning backtest run identifier.")
    company_id: str = Field(description="Covered company identifier.")
    signal_id: str | None = Field(
        default=None,
        description="Signal selected for the decision when one was eligible.",
    )
    decision_time: datetime = Field(description="UTC decision timestamp.")
    signal_effective_at: datetime | None = Field(
        default=None,
        description="UTC signal effective time when a signal drove the decision.",
    )
    decision_cutoff: DecisionCutoff | None = Field(
        default=None,
        description="Structured decision cutoff used to evaluate point-in-time eligibility.",
    )
    action: DecisionAction = Field(description="Action implied by the decision.")
    target_units: int = Field(
        ge=-1,
        le=1,
        description="Target unit exposure after execution under the Day 6 unit-position rule.",
    )
    decision_snapshot_id: str = Field(description="Snapshot identifier used for the decision.")
    reason: str = Field(description="Short explanation for the decision.")
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions attached to the decision.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the decision.")

    @model_validator(mode="after")
    def validate_signal_link(self) -> StrategyDecision:
        """Require signal timestamps whenever a signal drives the decision."""

        if self.signal_id is None and self.signal_effective_at is not None:
            raise ValueError("signal_effective_at requires a corresponding signal_id.")
        if self.signal_id is not None and self.signal_effective_at is None:
            raise ValueError("signal_effective_at is required when signal_id is set.")
        if self.decision_cutoff is not None and self.decision_cutoff.decision_time != self.decision_time:
            raise ValueError("decision_cutoff.decision_time must match decision_time.")
        return self


class SimulationEvent(TimestampedModel):
    """Structured event emitted by the Day 6 simulation skeleton."""

    simulation_event_id: str = Field(description="Canonical simulation-event identifier.")
    backtest_run_id: str = Field(description="Owning backtest run identifier.")
    strategy_decision_id: str | None = Field(
        default=None,
        description="Decision identifier associated with the event when applicable.",
    )
    event_type: SimulationEventType = Field(description="Simulation event type.")
    event_time: datetime = Field(description="UTC event timestamp.")
    symbol: str | None = Field(default=None, description="Instrument symbol when applicable.")
    quantity: int | None = Field(
        default=None,
        description="Executed or marked quantity associated with the event.",
    )
    price: float | None = Field(default=None, gt=0.0, description="Event price when applicable.")
    transaction_cost_applied: float = Field(
        default=0.0,
        ge=0.0,
        description="Transaction cost deducted at the event.",
    )
    slippage_applied: float = Field(
        default=0.0,
        ge=0.0,
        description="Slippage cost deducted at the event.",
    )
    cash_delta: float = Field(description="Cash change applied by the event.")
    position_after_units: int | None = Field(
        default=None,
        description="Position units after applying the event.",
    )
    note: str | None = Field(default=None, description="Short event note.")
    provenance: ProvenanceRecord = Field(description="Traceability for the event.")

    @model_validator(mode="after")
    def validate_event_payload(self) -> SimulationEvent:
        """Ensure fill and decision events carry the minimum expected structure."""

        if self.event_type in {SimulationEventType.DECISION, SimulationEventType.FILL}:
            if self.strategy_decision_id is None:
                raise ValueError(
                    "strategy_decision_id is required for decision and fill events."
                )
        if self.event_type is SimulationEventType.FILL:
            if self.price is None or self.quantity is None or self.position_after_units is None:
                raise ValueError(
                    "Fill events require price, quantity, and position_after_units."
                )
        return self


class PerformanceSummary(TimestampedModel):
    """Mechanical performance summary for a Day 6 exploratory run."""

    performance_summary_id: str = Field(description="Canonical performance-summary identifier.")
    backtest_run_id: str = Field(description="Owning backtest run identifier.")
    starting_cash: float = Field(gt=0.0, description="Starting account value.")
    ending_cash: float = Field(description="Ending marked-to-market account value.")
    gross_pnl: float = Field(description="Gross PnL before costs.")
    net_pnl: float = Field(description="Net PnL after costs.")
    trade_count: int = Field(ge=0, description="Number of executed fills.")
    turnover_notional: float = Field(
        ge=0.0,
        description="Total turnover notional traded during the run.",
    )
    benchmark_reference_ids: list[str] = Field(
        default_factory=list,
        description="Benchmark references emitted alongside the run.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Important assumptions or interpretation notes for the summary.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the summary.")

    @model_validator(mode="after")
    def validate_summary(self) -> PerformanceSummary:
        """Require benchmark references for every Day 6 performance summary."""

        if not self.benchmark_reference_ids:
            raise ValueError("benchmark_reference_ids must contain at least one benchmark.")
        return self


class BenchmarkReference(TimestampedModel):
    """Mechanical benchmark result emitted for an exploratory backtest run."""

    benchmark_reference_id: str = Field(description="Canonical benchmark-reference identifier.")
    backtest_run_id: str = Field(description="Owning backtest run identifier.")
    benchmark_name: str = Field(description="Human-readable benchmark name.")
    benchmark_kind: BenchmarkKind = Field(description="Benchmark type.")
    symbol: str | None = Field(default=None, description="Symbol when the benchmark uses one.")
    starting_value: float = Field(gt=0.0, description="Starting benchmark account value.")
    ending_value: float = Field(gt=0.0, description="Ending benchmark account value.")
    simple_return: float = Field(description="Simple benchmark return over the run window.")
    notes: list[str] = Field(
        default_factory=list,
        description="Interpretation notes for the benchmark.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the benchmark.")


class BacktestRun(TimestampedModel):
    """Metadata for a temporally controlled backtest execution."""

    backtest_run_id: str = Field(description="Canonical backtest run identifier.")
    backtest_config_id: str = Field(description="Backtest configuration used by the run.")
    experiment_id: str | None = Field(
        default=None, description="Optional experiment identifier that owns the run."
    )
    company_id: str = Field(description="Covered company identifier for the run.")
    strategy_name: str = Field(description="Strategy or signal family under evaluation.")
    signal_family: str = Field(description="Signal family evaluated by the run.")
    ablation_view: AblationView = Field(description="Ablation slice evaluated by the run.")
    status: BacktestStatus = Field(description="Backtest execution status.")
    train_start: date | None = Field(default=None, description="Training window start date.")
    train_end: date | None = Field(default=None, description="Training window end date.")
    test_start: date = Field(description="Out-of-sample test window start date.")
    test_end: date = Field(description="Out-of-sample test window end date.")
    signal_snapshot_id: str = Field(description="Signal snapshot identifier used by the run.")
    price_snapshot_id: str = Field(description="Price snapshot identifier used by the run.")
    execution_assumption_id: str = Field(
        description="Execution assumption identifier applied by the run."
    )
    execution_timing_rule_id: str | None = Field(
        default=None,
        description="Execution-timing rule identifier describing the backtest timing semantics.",
    )
    fill_assumption_id: str | None = Field(
        default=None,
        description="Fill-assumption identifier describing the backtest fill model.",
    )
    cost_model_id: str | None = Field(
        default=None,
        description="Cost-model identifier describing the backtest transaction-cost model.",
    )
    performance_summary_id: str = Field(description="Performance summary identifier.")
    benchmark_reference_ids: list[str] = Field(
        default_factory=list,
        description="Benchmark references emitted alongside the run.",
    )
    decision_cutoff_time: datetime = Field(
        description="UTC cutoff representing the latest decision time used during the run."
    )
    exploratory_only: bool = Field(
        default=True,
        description="Whether the run is exploratory and non-promotable by default.",
    )
    allowed_signal_statuses: list[SignalStatus] = Field(
        default_factory=list,
        description="Signal lifecycle states explicitly allowed into the run.",
    )
    leakage_checks: list[str] = Field(
        default_factory=list,
        description="Leakage checks executed as part of the run.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes and simplifications for the run.",
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
        if not self.allowed_signal_statuses:
            raise ValueError("allowed_signal_statuses must contain at least one status.")
        if not self.benchmark_reference_ids:
            raise ValueError("benchmark_reference_ids must contain at least one benchmark.")
        return self


class StrategySpec(TimestampedModel):
    """Stable definition for one comparable strategy family."""

    strategy_spec_id: str = Field(description="Canonical strategy-spec identifier.")
    name: str = Field(description="Human-readable strategy name.")
    family: StrategyFamily = Field(description="Strategy family represented by the spec.")
    description: str = Field(description="Short explanation of the strategy family.")
    signal_family: str = Field(description="Stable signal family label emitted by the strategy.")
    required_inputs: list[str] = Field(
        default_factory=list,
        description="Named input families required to materialize the strategy.",
    )
    decision_rule_name: str = Field(description="Deterministic decision rule used by the strategy.")
    provenance: ProvenanceRecord = Field(description="Traceability for the strategy specification.")

    @model_validator(mode="after")
    def validate_spec(self) -> StrategySpec:
        """Require honest, explicit strategy definitions."""

        if not self.description:
            raise ValueError("description must be non-empty.")
        if not self.required_inputs:
            raise ValueError("required_inputs must contain at least one declared input.")
        if not self.decision_rule_name:
            raise ValueError("decision_rule_name must be non-empty.")
        return self


class StrategyVariant(TimestampedModel):
    """Concrete runnable strategy configuration inside one ablation run."""

    strategy_variant_id: str = Field(description="Canonical strategy-variant identifier.")
    strategy_spec_id: str = Field(description="Owning strategy-spec identifier.")
    variant_name: str = Field(description="Human-readable variant label.")
    family: StrategyFamily = Field(description="Strategy family implemented by the variant.")
    parameters: list[ExperimentParameter] = Field(
        default_factory=list,
        description="Explicit parameters for the runnable variant.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes or constraints attached to the variant.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the strategy variant.")

    @model_validator(mode="after")
    def validate_variant(self) -> StrategyVariant:
        """Require a stable spec link and non-empty naming."""

        if not self.strategy_spec_id:
            raise ValueError("strategy_spec_id must be non-empty.")
        if not self.variant_name:
            raise ValueError("variant_name must be non-empty.")
        return self


class StrategyVariantSignal(TimestampedModel):
    """Comparable signal artifact emitted by a baseline or ablation strategy variant."""

    strategy_variant_signal_id: str = Field(
        description="Canonical strategy-variant-signal identifier."
    )
    strategy_variant_id: str = Field(description="Owning strategy-variant identifier.")
    company_id: str = Field(description="Covered company identifier.")
    signal_family: str = Field(description="Stable comparable signal family label.")
    family: StrategyFamily = Field(description="Strategy family that emitted the signal.")
    ablation_view: AblationView = Field(description="Ablation slice represented by the signal.")
    stance: ResearchStance = Field(description="Research-layer stance implied by the signal.")
    primary_score: float = Field(description="Comparable normalized score for the signal.")
    effective_at: datetime = Field(description="UTC time when the signal becomes eligible.")
    availability_window: AvailabilityWindow | None = Field(
        default=None,
        description="Structured availability window used to derive effective_at when present.",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="UTC expiry time when the signal should no longer be considered.",
    )
    status: SignalStatus = Field(description="Lifecycle status for the variant signal.")
    validation_status: DerivedArtifactValidationStatus = Field(
        description="Validation lifecycle status for the variant signal."
    )
    summary: str = Field(description="Short explanation of why the comparable signal exists.")
    source_signal_ids: list[str] = Field(
        default_factory=list,
        description="Upstream research-signal identifiers used to derive the signal when applicable.",
    )
    source_snapshot_ids: list[str] = Field(
        default_factory=list,
        description="Snapshot identifiers used to derive the signal.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Explicit assumptions required to interpret the signal responsibly.",
    )
    uncertainties: list[str] = Field(
        default_factory=list,
        description="Open uncertainties still limiting trust in the signal.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the variant signal.")

    @property
    def signal_id(self) -> str:
        """Expose a comparable signal identifier for generic backtest consumers."""

        return self.strategy_variant_signal_id

    @model_validator(mode="after")
    def validate_signal_window(self) -> StrategyVariantSignal:
        """Require an explicit snapshot trail and ordered signal windows."""

        if not self.summary:
            raise ValueError("summary must be non-empty.")
        if not self.source_snapshot_ids:
            raise ValueError("source_snapshot_ids must contain at least one snapshot identifier.")
        if (
            self.availability_window is not None
            and self.effective_at != self.availability_window.available_from
        ):
            raise ValueError(
                "effective_at must match availability_window.available_from when an availability window is set."
            )
        if self.expires_at is not None and self.expires_at < self.effective_at:
            raise ValueError("expires_at must be greater than or equal to effective_at.")
        return self


class EvaluationSlice(TimestampedModel):
    """Shared evaluation slice used to compare strategy variants honestly."""

    evaluation_slice_id: str = Field(description="Canonical evaluation-slice identifier.")
    company_id: str = Field(description="Covered company identifier.")
    test_start: date = Field(description="Evaluation window start date.")
    test_end: date = Field(description="Evaluation window end date.")
    decision_frequency: str = Field(
        default="daily",
        description="Decision cadence for the comparison slice.",
    )
    as_of_time: datetime | None = Field(
        default=None,
        description="Optional information boundary applied to the comparison slice.",
    )
    price_fixture_path: str = Field(description="Price fixture path used by the evaluation slice.")
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes attached to the evaluation slice.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the evaluation slice.")

    @model_validator(mode="after")
    def validate_slice(self) -> EvaluationSlice:
        """Require an ordered daily evaluation slice."""

        if self.test_end < self.test_start:
            raise ValueError("test_end must be greater than or equal to test_start.")
        if self.decision_frequency != "daily":
            raise ValueError("Day 9 only supports `daily` decision_frequency.")
        if not self.price_fixture_path:
            raise ValueError("price_fixture_path must be non-empty.")
        return self


class AblationConfig(TimestampedModel):
    """Shared reproducible configuration for one multi-variant comparison run."""

    ablation_config_id: str = Field(description="Canonical ablation-config identifier.")
    name: str = Field(description="Human-readable ablation name.")
    strategy_variants: list[StrategyVariant] = Field(
        default_factory=list,
        description="Strategy variants to compare under the shared slice.",
    )
    evaluation_slice: EvaluationSlice = Field(description="Shared comparison slice.")
    shared_backtest_config: BacktestConfig = Field(
        description="Backtest configuration shared across all variants."
    )
    comparison_metric_name: str = Field(
        description="Primary metric name used for mechanical row ordering."
    )
    record_experiment: bool = Field(
        default=True,
        description="Whether the ablation harness records experiment metadata.",
    )
    requested_by: str = Field(description="Requester identifier.")
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes for the ablation run.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the ablation config.")

    @model_validator(mode="after")
    def validate_ablation(self) -> AblationConfig:
        """Require multiple variants and an explicit comparison metric."""

        if len(self.strategy_variants) < 2:
            raise ValueError("strategy_variants must contain at least two variants.")
        if not self.comparison_metric_name:
            raise ValueError("comparison_metric_name must be non-empty.")
        return self


class AblationVariantResult(TimestampedModel):
    """Structured comparison row for one strategy variant inside an ablation run."""

    strategy_variant_id: str = Field(description="Owning strategy-variant identifier.")
    family: StrategyFamily = Field(description="Strategy family represented by the result.")
    variant_signal_ids: list[str] = Field(
        default_factory=list,
        description="Comparable signal identifiers emitted for the variant.",
    )
    backtest_run_id: str = Field(description="Backtest run identifier for the variant.")
    experiment_id: str | None = Field(
        default=None,
        description="Child experiment identifier recorded for the variant when available.",
    )
    performance_summary_id: str = Field(description="Performance summary identifier.")
    benchmark_reference_ids: list[str] = Field(
        default_factory=list,
        description="Benchmark references emitted by the variant backtest.",
    )
    dataset_reference_ids: list[str] = Field(
        default_factory=list,
        description="Dataset references used by the variant run.",
    )
    gross_pnl: float = Field(description="Gross PnL reported by the variant backtest.")
    net_pnl: float = Field(description="Net PnL reported by the variant backtest.")
    trade_count: int = Field(ge=0, description="Trade count reported by the variant backtest.")
    turnover_notional: float = Field(
        ge=0.0,
        description="Turnover notional reported by the variant backtest.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Interpretation notes for the comparison row.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the comparison row.")


class AblationResult(TimestampedModel):
    """Structured summary comparing multiple strategy variants on one shared slice."""

    ablation_result_id: str = Field(description="Canonical ablation-result identifier.")
    ablation_config_id: str = Field(description="Owning ablation-config identifier.")
    evaluation_slice_id: str = Field(description="Evaluation-slice identifier used by the run.")
    variant_results: list[AblationVariantResult] = Field(
        default_factory=list,
        description="Variant comparison rows produced by the ablation run.",
    )
    comparison_metric_name: str = Field(
        description="Primary metric used for mechanical row ordering."
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes or caveats for the ablation result.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the ablation result.")

    @model_validator(mode="after")
    def validate_result(self) -> AblationResult:
        """Require at least two comparison rows and an explicit metric."""

        if len(self.variant_results) < 2:
            raise ValueError("variant_results must contain at least two comparison rows.")
        if not self.comparison_metric_name:
            raise ValueError("comparison_metric_name must be non-empty.")
        return self


class ExperimentParameterValueType(StrEnum):
    """Typed value families supported by experiment parameter recording."""

    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    ENUM = "enum"
    PATH = "path"


class ExperimentArtifactRole(StrEnum):
    """Role an artifact plays inside an experiment record."""

    INPUT_SNAPSHOT = "input_snapshot"
    OUTPUT = "output"
    SUMMARY = "summary"
    DIAGNOSTIC = "diagnostic"
    BENCHMARK = "benchmark"


class ExperimentParameter(TimestampedModel):
    """One explicitly recorded parameter used to configure an experiment run."""

    experiment_parameter_id: str = Field(description="Canonical experiment-parameter identifier.")
    key: str = Field(description="Stable parameter name.")
    value_repr: str = Field(description="String representation of the parameter value.")
    value_type: ExperimentParameterValueType = Field(
        description="Declared parameter value type."
    )
    redacted: bool = Field(
        default=False,
        description="Whether the parameter value was intentionally redacted.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the parameter record.")

    @model_validator(mode="after")
    def validate_value_repr(self) -> ExperimentParameter:
        """Require a stable string representation for every parameter."""

        if not self.value_repr:
            raise ValueError("value_repr must be non-empty.")
        return self


class ModelReference(TimestampedModel):
    """Minimal future-facing reference to a model and prompt configuration."""

    model_reference_id: str = Field(description="Canonical model-reference identifier.")
    provider: str = Field(description="Model provider or internal registry owner.")
    model_name: str = Field(description="Model name used by the workflow.")
    model_version: str | None = Field(default=None, description="Optional model version label.")
    prompt_version: str | None = Field(default=None, description="Optional prompt version label.")
    notes: list[str] = Field(
        default_factory=list,
        description="Important caveats about the model or prompt reference.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the model reference.")


class ExperimentConfig(TimestampedModel):
    """Stable, reproducible configuration metadata for one experiment."""

    experiment_config_id: str = Field(description="Canonical experiment-config identifier.")
    workflow_name: str = Field(description="Workflow family the experiment config applies to.")
    workflow_version: str = Field(description="Workflow or application version label.")
    parameter_hash: str = Field(description="Stable hash of the recorded parameters.")
    parameters: list[ExperimentParameter] = Field(
        default_factory=list,
        description="Explicit parameter rows describing the recorded configuration.",
    )
    source_config_artifact_id: str | None = Field(
        default=None,
        description="Primary upstream config artifact identifier when one exists.",
    )
    model_reference_ids: list[str] = Field(
        default_factory=list,
        description="Optional model references attached to the configuration.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the experiment config.")

    @model_validator(mode="after")
    def validate_config(self) -> ExperimentConfig:
        """Require a stable parameter hash and at least one recorded parameter."""

        if not self.parameter_hash:
            raise ValueError("parameter_hash must be non-empty.")
        if not self.parameters:
            raise ValueError("parameters must contain at least one parameter.")
        return self


class RunContext(TimestampedModel):
    """Operational context for the workflow run that owns an experiment."""

    run_context_id: str = Field(description="Canonical run-context identifier.")
    workflow_name: str = Field(description="Workflow family that produced the run.")
    workflow_run_id: str = Field(description="Concrete workflow run identifier.")
    requested_by: str = Field(description="Requester or operator who launched the run.")
    environment: str = Field(description="Runtime environment name.")
    artifact_root_uri: str = Field(description="Artifact root used by the run.")
    as_of_time: datetime | None = Field(
        default=None,
        description="Optional information boundary applied to the run.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes or context attached to the run.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the run context.")

    @model_validator(mode="after")
    def validate_artifact_root(self) -> RunContext:
        """Require a stable artifact root URI for replayability."""

        if not self.artifact_root_uri:
            raise ValueError("artifact_root_uri must be non-empty.")
        return self


class ExperimentArtifact(TimestampedModel):
    """Structured reference to an artifact produced or consumed by an experiment."""

    experiment_artifact_id: str = Field(description="Canonical experiment-artifact identifier.")
    experiment_id: str = Field(description="Owning experiment identifier.")
    artifact_id: str = Field(description="Referenced artifact identifier.")
    artifact_type: str = Field(description="Artifact model or category name.")
    artifact_role: ExperimentArtifactRole = Field(description="Role the artifact plays.")
    artifact_storage_location_id: str | None = Field(
        default=None,
        description="Artifact storage-location identifier when a local write was persisted.",
    )
    uri: str | None = Field(default=None, description="Direct URI when no storage record exists.")
    produced_at: datetime = Field(description="UTC timestamp when the artifact was produced.")
    provenance: ProvenanceRecord = Field(description="Traceability for the experiment artifact.")

    @model_validator(mode="after")
    def validate_location(self) -> ExperimentArtifact:
        """Require either a storage-location ID or a URI for the referenced artifact."""

        if self.artifact_storage_location_id is None and self.uri is None:
            raise ValueError(
                "ExperimentArtifact requires artifact_storage_location_id or uri."
            )
        return self


class ExperimentMetric(TimestampedModel):
    """Structured numeric metric recorded for an experiment."""

    experiment_metric_id: str = Field(description="Canonical experiment-metric identifier.")
    experiment_id: str = Field(description="Owning experiment identifier.")
    metric_name: str = Field(description="Stable metric name.")
    numeric_value: float = Field(description="Numeric metric value.")
    unit: str | None = Field(default=None, description="Optional metric unit label.")
    source_artifact_id: str | None = Field(
        default=None,
        description="Artifact identifier that produced or summarized the metric.",
    )
    recorded_at: datetime = Field(description="UTC timestamp when the metric was recorded.")
    provenance: ProvenanceRecord = Field(description="Traceability for the metric.")


class Experiment(TimestampedModel):
    """Track a research experiment, including datasets, hypotheses, and runs."""

    experiment_id: str = Field(description="Canonical experiment identifier.")
    name: str = Field(description="Experiment name.")
    objective: str = Field(description="Research objective or question under study.")
    created_by: str = Field(description="Analyst or workflow that created the experiment.")
    status: ExperimentStatus = Field(description="Experiment lifecycle status.")
    experiment_config_id: str = Field(description="Experiment-config identifier.")
    run_context_id: str = Field(description="Run-context identifier for the owning workflow.")
    dataset_reference_ids: list[str] = Field(
        default_factory=list,
        description="Dataset references that define the experiment input boundary.",
    )
    model_reference_ids: list[str] = Field(
        default_factory=list,
        description="Optional model references attached to the experiment.",
    )
    hypothesis_ids: list[str] = Field(
        default_factory=list,
        description="Hypotheses under study in the experiment.",
    )
    backtest_run_ids: list[str] = Field(
        default_factory=list,
        description="Backtest runs associated with the experiment.",
    )
    experiment_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Recorded experiment-artifact identifiers.",
    )
    experiment_metric_ids: list[str] = Field(
        default_factory=list,
        description="Recorded experiment-metric identifiers.",
    )
    started_at: datetime = Field(description="UTC timestamp when the experiment started.")
    completed_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the experiment completed or failed.",
    )
    notes: list[str] = Field(
        default_factory=list, description="Operational notes for the experiment."
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the experiment.")

    @model_validator(mode="after")
    def validate_experiment(self) -> Experiment:
        """Require explicit reproducibility links and ordered experiment timestamps."""

        if not self.dataset_reference_ids:
            raise ValueError("dataset_reference_ids must contain at least one dataset reference.")
        if self.completed_at is not None and self.completed_at < self.started_at:
            raise ValueError("completed_at must be greater than or equal to started_at.")
        if self.status in {ExperimentStatus.COMPLETED, ExperimentStatus.FAILED}:
            if self.completed_at is None:
                raise ValueError("completed_at is required when the experiment is finished.")
        return self


class MetricValue(TimestampedModel):
    """Typed value payload attached to one evaluation metric."""

    metric_value_id: str = Field(description="Canonical metric-value identifier.")
    numeric_value: float | None = Field(
        default=None,
        description="Numeric metric value when applicable.",
    )
    boolean_value: bool | None = Field(
        default=None,
        description="Boolean metric value when applicable.",
    )
    text_value: str | None = Field(
        default=None,
        description="Text metric value when applicable.",
    )
    unit: str | None = Field(default=None, description="Optional metric unit label.")

    @model_validator(mode="after")
    def validate_single_metric_value(self) -> MetricValue:
        """Require exactly one metric value representation."""

        populated = [
            self.numeric_value is not None,
            self.boolean_value is not None,
            self.text_value is not None,
        ]
        if sum(populated) != 1:
            raise ValueError(
                "Exactly one of numeric_value, boolean_value, or text_value must be set."
            )
        return self


class EvaluationMetric(TimestampedModel):
    """One deterministic metric recorded inside an evaluation report."""

    evaluation_metric_id: str = Field(description="Canonical evaluation-metric identifier.")
    evaluation_report_id: str = Field(description="Owning evaluation-report identifier.")
    dimension: EvaluationDimension = Field(description="Evaluation dimension represented.")
    metric_name: str = Field(description="Stable metric name.")
    target_type: str = Field(description="Artifact type judged by the metric.")
    target_id: str = Field(description="Artifact identifier judged by the metric.")
    status: EvaluationStatus = Field(description="Outcome classification for the metric.")
    metric_value: MetricValue = Field(description="Typed value payload for the metric.")
    threshold: float | None = Field(
        default=None,
        description="Optional threshold used to interpret the metric mechanically.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Interpretation notes attached to the metric.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the evaluation metric.")

    @model_validator(mode="after")
    def validate_metric(self) -> EvaluationMetric:
        """Require explicit metric names and evaluation linkage."""

        if not self.metric_name:
            raise ValueError("metric_name must be non-empty.")
        if not self.target_type or not self.target_id:
            raise ValueError("target_type and target_id must be non-empty.")
        return self


class FailureCase(TimestampedModel):
    """Structured failure recorded by the evaluation layer."""

    failure_case_id: str = Field(description="Canonical failure-case identifier.")
    evaluation_report_id: str = Field(description="Owning evaluation-report identifier.")
    target_type: str = Field(description="Artifact type affected by the failure.")
    target_id: str = Field(description="Artifact identifier affected by the failure.")
    failure_kind: FailureCaseKind = Field(description="Failure category.")
    severity: Severity = Field(description="Severity of the failure.")
    blocking: bool = Field(description="Whether the failure should block trust progression.")
    message: str = Field(description="Human-readable failure explanation.")
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts related to the observed failure.",
    )
    suspected_cause: str | None = Field(
        default=None,
        description="Optional suspected cause for the failure.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the failure case.")

    @model_validator(mode="after")
    def validate_failure_case(self) -> FailureCase:
        """Require explicit failure messages."""

        if not self.message:
            raise ValueError("message must be non-empty.")
        return self


class RobustnessCheck(TimestampedModel):
    """Structured robustness result attached to an evaluation report."""

    robustness_check_id: str = Field(description="Canonical robustness-check identifier.")
    evaluation_report_id: str = Field(description="Owning evaluation-report identifier.")
    check_kind: RobustnessCheckKind = Field(description="Robustness check category.")
    target_type: str = Field(description="Artifact type judged by the check.")
    target_id: str = Field(description="Artifact identifier judged by the check.")
    status: EvaluationStatus = Field(description="Outcome of the robustness check.")
    severity: Severity = Field(description="Severity attached to the robustness result.")
    message: str = Field(description="Human-readable explanation of the robustness result.")
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Artifacts related to the robustness result.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the robustness check.")

    @model_validator(mode="after")
    def validate_check(self) -> RobustnessCheck:
        """Require explicit robustness messaging."""

        if not self.message:
            raise ValueError("message must be non-empty.")
        return self


class ComparisonSummary(TimestampedModel):
    """Mechanical summary of one multi-variant comparison output."""

    comparison_summary_id: str = Field(description="Canonical comparison-summary identifier.")
    evaluation_report_id: str = Field(description="Owning evaluation-report identifier.")
    target_id: str = Field(description="Artifact identifier summarized by the comparison.")
    comparison_metric_name: str = Field(description="Primary comparison metric name.")
    expected_family_count: int = Field(ge=0, description="Expected number of strategy families.")
    observed_family_count: int = Field(ge=0, description="Observed number of strategy families.")
    ordered_strategy_variant_ids: list[str] = Field(
        default_factory=list,
        description="Mechanically ordered strategy-variant identifiers.",
    )
    mechanical_order_only: bool = Field(
        default=True,
        description="Whether ordering is explicitly mechanical and non-validating.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Important comparison caveats.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the comparison summary.")

    @model_validator(mode="after")
    def validate_summary(self) -> ComparisonSummary:
        """Require a declared comparison metric and ordered rows."""

        if not self.comparison_metric_name:
            raise ValueError("comparison_metric_name must be non-empty.")
        if not self.ordered_strategy_variant_ids:
            raise ValueError("ordered_strategy_variant_ids must contain at least one variant.")
        return self


class CoverageSummary(TimestampedModel):
    """Coverage rollup for one evaluation dimension."""

    coverage_summary_id: str = Field(description="Canonical coverage-summary identifier.")
    evaluation_report_id: str = Field(description="Owning evaluation-report identifier.")
    dimension: EvaluationDimension = Field(description="Evaluation dimension summarized.")
    target_type: str = Field(description="Artifact type covered by the summary.")
    target_id: str = Field(description="Artifact identifier covered by the summary.")
    covered_count: int = Field(ge=0, description="Count of artifacts that passed the check.")
    missing_count: int = Field(ge=0, description="Count of artifacts missing or failing coverage.")
    total_count: int = Field(ge=0, description="Total number of artifacts evaluated.")
    coverage_ratio: float = Field(
        ge=0.0,
        le=1.0,
        description="Covered count divided by total count.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Coverage caveats or interpretation notes.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the coverage summary.")

    @model_validator(mode="after")
    def validate_counts(self) -> CoverageSummary:
        """Require internally consistent coverage counts and ratios."""

        if self.covered_count + self.missing_count != self.total_count:
            raise ValueError("covered_count + missing_count must equal total_count.")
        expected_ratio = 0.0 if self.total_count == 0 else self.covered_count / self.total_count
        if abs(self.coverage_ratio - expected_ratio) > 1e-9:
            raise ValueError("coverage_ratio must equal covered_count / total_count.")
        return self


class EvaluationReport(TimestampedModel):
    """Primary Day 10 evaluation artifact summarizing structural quality and failures."""

    evaluation_report_id: str = Field(description="Canonical evaluation-report identifier.")
    target_type: str = Field(description="Artifact type evaluated by the report.")
    target_id: str = Field(description="Artifact identifier evaluated by the report.")
    generated_at: datetime = Field(description="UTC timestamp when evaluation completed.")
    overall_status: EvaluationStatus = Field(description="Overall structural evaluation outcome.")
    metric_ids: list[str] = Field(
        default_factory=list,
        description="Evaluation-metric identifiers included in the report.",
    )
    failure_case_ids: list[str] = Field(
        default_factory=list,
        description="Failure-case identifiers included in the report.",
    )
    robustness_check_ids: list[str] = Field(
        default_factory=list,
        description="Robustness-check identifiers included in the report.",
    )
    comparison_summary_id: str | None = Field(
        default=None,
        description="Comparison-summary identifier when one exists.",
    )
    coverage_summary_ids: list[str] = Field(
        default_factory=list,
        description="Coverage-summary identifiers included in the report.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="High-level evaluation notes and caveats.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the evaluation report.")

    @model_validator(mode="after")
    def validate_report(self) -> EvaluationReport:
        """Require reports to reference at least one structured evaluation output."""

        if not any(
            [
                self.metric_ids,
                self.failure_case_ids,
                self.robustness_check_ids,
                self.comparison_summary_id is not None,
                self.coverage_summary_ids,
            ]
        ):
            raise ValueError(
                "EvaluationReport must reference at least one metric, failure, robustness check, comparison summary, or coverage summary."
            )
        return self


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
