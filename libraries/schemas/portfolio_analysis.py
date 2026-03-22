from __future__ import annotations

from pydantic import Field, model_validator

from libraries.schemas.base import (
    ProvenanceRecord,
    RiskCheckStatus,
    Severity,
    StrictModel,
    TimestampedModel,
)


class ContributionBreakdown(StrictModel):
    """Structured contribution row used inside attribution and stress artifacts."""

    contributor_type: str = Field(description="Type of contributor such as signal, position, or constraint.")
    contributor_id: str = Field(description="Identifier of the contributing object.")
    metric_name: str = Field(description="Metric explained by the contribution row.")
    metric_value: float = Field(description="Numeric value associated with the contribution.")
    unit: str = Field(description="Unit for the metric value.")
    summary: str = Field(description="Short explanation of why the contribution matters.")

    @model_validator(mode="after")
    def validate_breakdown(self) -> ContributionBreakdown:
        """Require explicit contributor and explanation fields."""

        if not self.contributor_type:
            raise ValueError("contributor_type must be non-empty.")
        if not self.contributor_id:
            raise ValueError("contributor_id must be non-empty.")
        if not self.metric_name:
            raise ValueError("metric_name must be non-empty.")
        if not self.unit:
            raise ValueError("unit must be non-empty.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class PositionAttribution(TimestampedModel):
    """Structured explanation of why one position idea appears in a proposal."""

    position_attribution_id: str = Field(description="Canonical position-attribution identifier.")
    portfolio_proposal_id: str = Field(description="Portfolio proposal being explained.")
    position_idea_id: str = Field(description="Position idea explained by the attribution row.")
    company_id: str = Field(description="Covered company identifier.")
    signal_id: str = Field(description="Signal motivating the position idea.")
    portfolio_constraint_ids: list[str] = Field(
        default_factory=list,
        description="Constraint identifiers relevant to the attributed position.",
    )
    supporting_evidence_link_ids: list[str] = Field(
        default_factory=list,
        description="Supporting evidence links grounding the position idea.",
    )
    from_arbitrated_signal: bool = Field(
        description="Whether the position idea came from an arbitrated primary signal."
    )
    contribution_breakdowns: list[ContributionBreakdown] = Field(
        default_factory=list,
        description="Structured contribution rows explaining the position.",
    )
    summary: str = Field(description="Operator-readable summary of the position attribution.")
    provenance: ProvenanceRecord = Field(description="Traceability for the attribution.")

    @model_validator(mode="after")
    def validate_position_attribution(self) -> PositionAttribution:
        """Require visible linkage and contribution detail."""

        if not self.position_idea_id:
            raise ValueError("position_idea_id must be non-empty.")
        if not self.signal_id:
            raise ValueError("signal_id must be non-empty.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        if not self.contribution_breakdowns:
            raise ValueError("contribution_breakdowns must contain at least one row.")
        return self


class PortfolioAttribution(TimestampedModel):
    """Structured explanation of proposal-level contributors and constraint pressure."""

    portfolio_attribution_id: str = Field(description="Canonical portfolio-attribution identifier.")
    portfolio_proposal_id: str = Field(description="Portfolio proposal being explained.")
    position_attribution_ids: list[str] = Field(
        default_factory=list,
        description="Position-attribution identifiers contributing to the portfolio view.",
    )
    signal_ids: list[str] = Field(
        default_factory=list,
        description="Signals contributing to the proposal.",
    )
    portfolio_constraint_ids: list[str] = Field(
        default_factory=list,
        description="Constraints used while explaining headroom and fragility.",
    )
    dominant_position_idea_ids: list[str] = Field(
        default_factory=list,
        description="Most concentrated or dominant position ideas in the proposal.",
    )
    contribution_breakdowns: list[ContributionBreakdown] = Field(
        default_factory=list,
        description="Structured proposal-level contribution rows.",
    )
    concentration_summary: str = Field(description="Structured summary of proposal concentration.")
    exposure_summary: str = Field(description="Structured summary of dominant exposure traits.")
    summary: str = Field(description="Operator-readable summary of the proposal attribution.")
    provenance: ProvenanceRecord = Field(description="Traceability for the attribution.")

    @model_validator(mode="after")
    def validate_portfolio_attribution(self) -> PortfolioAttribution:
        """Require explicit proposal linkage and structured explanation."""

        if not self.portfolio_proposal_id:
            raise ValueError("portfolio_proposal_id must be non-empty.")
        if not self.concentration_summary:
            raise ValueError("concentration_summary must be non-empty.")
        if not self.exposure_summary:
            raise ValueError("exposure_summary must be non-empty.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        if not self.contribution_breakdowns:
            raise ValueError("contribution_breakdowns must contain at least one row.")
        return self


class ExposureShock(StrictModel):
    """One explicit scenario shock input used by a deterministic stress definition."""

    shock_scope: str = Field(description="Scope of the shock such as portfolio, sector, constraint, or confidence.")
    target_identifier: str | None = Field(
        default=None,
        description="Optional target identifier such as a sector or constraint name.",
    )
    metric_name: str = Field(description="Metric changed by the shock.")
    magnitude: float = Field(description="Magnitude of the shock.")
    unit: str = Field(description="Unit for the shock magnitude.")
    summary: str = Field(description="Short explanation of the explicit shock.")

    @model_validator(mode="after")
    def validate_shock(self) -> ExposureShock:
        """Require explicit shock semantics."""

        if not self.shock_scope:
            raise ValueError("shock_scope must be non-empty.")
        if not self.metric_name:
            raise ValueError("metric_name must be non-empty.")
        if not self.unit:
            raise ValueError("unit must be non-empty.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class ScenarioDefinition(TimestampedModel):
    """Persisted deterministic scenario definition for proposal stress testing."""

    scenario_definition_id: str = Field(description="Canonical scenario-definition identifier.")
    scenario_name: str = Field(description="Stable scenario name.")
    description: str = Field(description="Human-readable description of the scenario.")
    shocks: list[ExposureShock] = Field(
        default_factory=list,
        description="Explicit shocks applied by the scenario.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Explicit assumptions attached to the scenario.",
    )
    review_guidance: list[str] = Field(
        default_factory=list,
        description="Operator-facing review guidance for interpreting the scenario.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the scenario definition.")

    @model_validator(mode="after")
    def validate_scenario(self) -> ScenarioDefinition:
        """Require explicit scenario configuration."""

        if not self.scenario_name:
            raise ValueError("scenario_name must be non-empty.")
        if not self.description:
            raise ValueError("description must be non-empty.")
        if not self.shocks:
            raise ValueError("shocks must contain at least one explicit shock.")
        return self


class StressTestRun(TimestampedModel):
    """Structured stress-test batch run executed against one portfolio proposal."""

    stress_test_run_id: str = Field(description="Canonical stress-test run identifier.")
    portfolio_proposal_id: str = Field(description="Portfolio proposal tested by the run.")
    scenario_definition_ids: list[str] = Field(
        default_factory=list,
        description="Scenario definitions applied during the run.",
    )
    stress_test_result_ids: list[str] = Field(
        default_factory=list,
        description="Stress-test results produced by the run.",
    )
    review_required: bool = Field(
        default=True,
        description="Whether human review should inspect the stress outputs.",
    )
    summary: str = Field(description="Short summary of the overall stress-test run.")
    provenance: ProvenanceRecord = Field(description="Traceability for the run.")

    @model_validator(mode="after")
    def validate_stress_run(self) -> StressTestRun:
        """Require explicit scenario linkage and summary text."""

        if not self.portfolio_proposal_id:
            raise ValueError("portfolio_proposal_id must be non-empty.")
        if not self.scenario_definition_ids:
            raise ValueError("scenario_definition_ids must contain at least one scenario.")
        if not self.stress_test_result_ids:
            raise ValueError("stress_test_result_ids must contain at least one result.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class StressTestResult(TimestampedModel):
    """One structured scenario outcome for a portfolio proposal."""

    stress_test_result_id: str = Field(description="Canonical stress-test result identifier.")
    stress_test_run_id: str = Field(description="Stress-test run identifier.")
    portfolio_proposal_id: str = Field(description="Portfolio proposal evaluated by the scenario.")
    scenario_definition_id: str = Field(description="Scenario definition that produced the result.")
    status: RiskCheckStatus = Field(description="Stress outcome status.")
    severity: Severity = Field(description="Stress outcome severity.")
    affected_position_ids: list[str] = Field(
        default_factory=list,
        description="Position ideas materially affected by the scenario.",
    )
    breached_constraint_ids: list[str] = Field(
        default_factory=list,
        description="Constraint identifiers breached under the scenario.",
    )
    estimated_pnl_impact_usd: float | None = Field(
        default=None,
        description="Estimated proposal-level PnL impact in USD when applicable.",
    )
    estimated_return_impact_bps: float | None = Field(
        default=None,
        description="Estimated proposal-level return impact in basis points when applicable.",
    )
    contribution_breakdowns: list[ContributionBreakdown] = Field(
        default_factory=list,
        description="Structured rows explaining the scenario outcome.",
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Assumptions required to interpret the result.",
    )
    summary: str = Field(description="Operator-readable summary of the scenario outcome.")
    provenance: ProvenanceRecord = Field(description="Traceability for the result.")

    @model_validator(mode="after")
    def validate_stress_result(self) -> StressTestResult:
        """Require visible scenario linkage and explanation."""

        if not self.stress_test_run_id:
            raise ValueError("stress_test_run_id must be non-empty.")
        if not self.portfolio_proposal_id:
            raise ValueError("portfolio_proposal_id must be non-empty.")
        if not self.scenario_definition_id:
            raise ValueError("scenario_definition_id must be non-empty.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        if not self.contribution_breakdowns:
            raise ValueError("contribution_breakdowns must contain at least one row.")
        return self
