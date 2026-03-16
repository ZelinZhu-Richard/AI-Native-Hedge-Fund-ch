from __future__ import annotations

from datetime import date, datetime

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
    PositionSide,
    ProvenanceRecord,
    SignalStatus,
    TimestampedModel,
)


class Hypothesis(TimestampedModel):
    """Forward-looking research thesis supported by evidence and assumptions."""

    hypothesis_id: str = Field(description="Canonical hypothesis identifier.")
    company_id: str = Field(description="Covered company identifier.")
    title: str = Field(description="Short hypothesis title.")
    thesis: str = Field(description="Primary investment thesis statement.")
    direction: PositionSide = Field(description="Directional view implied by the thesis.")
    status: HypothesisStatus = Field(description="Hypothesis lifecycle status.")
    time_horizon: str = Field(
        description="Qualitative time horizon, for example `quarterly` or `12m`."
    )
    catalyst: str | None = Field(default=None, description="Expected catalyst or validating event.")
    invalidation_conditions: list[str] = Field(
        default_factory=list,
        description="Observable conditions that would invalidate the thesis.",
    )
    evidence_span_ids: list[str] = Field(
        default_factory=list,
        description="Evidence spans directly supporting the thesis.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Explicit assumptions that are not yet verified by evidence.",
    )
    confidence: ConfidenceAssessment | None = Field(
        default=None,
        description="Confidence and uncertainty assessment for the thesis.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the hypothesis.")


class CounterHypothesis(TimestampedModel):
    """Adversarial counter-thesis designed to challenge a primary hypothesis."""

    counter_hypothesis_id: str = Field(description="Canonical counter-hypothesis identifier.")
    hypothesis_id: str = Field(description="Primary hypothesis being challenged.")
    title: str = Field(description="Short counter-thesis title.")
    thesis: str = Field(description="Concise statement of the opposing case.")
    strongest_evidence_span_ids: list[str] = Field(
        default_factory=list,
        description="Evidence spans that most strongly support the counter case.",
    )
    unresolved_questions: list[str] = Field(
        default_factory=list,
        description="Questions still unresolved after critique.",
    )
    confidence: ConfidenceAssessment | None = Field(
        default=None,
        description="Confidence and uncertainty assessment for the counter-thesis.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the counter-hypothesis.")


class Feature(TimestampedModel):
    """Point-in-time feature value with explicit availability semantics."""

    feature_id: str = Field(description="Canonical feature identifier.")
    name: str = Field(description="Stable feature name.")
    family: str = Field(description="Feature family or namespace.")
    entity_id: str = Field(
        description="Entity the feature applies to, such as company or portfolio."
    )
    company_id: str | None = Field(
        default=None, description="Associated company identifier when applicable."
    )
    data_layer: DataLayer = Field(description="Artifact layer of the feature value.")
    definition: str = Field(description="Human-readable feature definition.")
    as_of_date: date = Field(description="Logical business date the feature describes.")
    available_at: datetime = Field(
        description="UTC time when the feature became available to decision-making systems.",
    )
    status: FeatureStatus = Field(description="Feature lifecycle status.")
    numeric_value: float | None = Field(
        default=None, description="Numeric feature value when applicable."
    )
    text_value: str | None = Field(
        default=None, description="Textual feature value when applicable."
    )
    boolean_value: bool | None = Field(
        default=None, description="Boolean feature value when applicable."
    )
    unit: str | None = Field(default=None, description="Unit associated with the feature value.")
    confidence: ConfidenceAssessment | None = Field(
        default=None,
        description="Confidence and uncertainty assessment for the feature value.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the feature.")

    @model_validator(mode="after")
    def validate_single_value(self) -> Feature:
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


class Signal(TimestampedModel):
    """Research signal derived from features, evidence, and reviewed hypotheses."""

    signal_id: str = Field(description="Canonical signal identifier.")
    company_id: str = Field(description="Covered company identifier.")
    hypothesis_id: str = Field(description="Primary hypothesis driving the signal.")
    signal_family: str = Field(description="Stable signal family name.")
    direction: PositionSide = Field(description="Directional view implied by the signal.")
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
    confidence: ConfidenceAssessment | None = Field(
        default=None,
        description="Confidence and uncertainty assessment for the signal.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the signal.")


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
        description="UTC cutoff representing the maximum information set available during the run.",
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
        description="Portfolio proposal discussed in the memo, if any.",
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
