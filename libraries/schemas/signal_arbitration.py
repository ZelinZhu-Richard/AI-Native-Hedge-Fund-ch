from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from libraries.schemas.base import ProvenanceRecord, StrictModel, TimestampedModel
from libraries.schemas.research import DerivedArtifactValidationStatus, EvidenceGrade


class FreshnessState(StrEnum):
    """Heuristic freshness label for a signal at one arbitration time."""

    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    UNKNOWN = "unknown"


class SignalConflictKind(StrEnum):
    """Conflict kinds supported by deterministic signal arbitration."""

    DIRECTIONAL_DISAGREEMENT = "directional_disagreement"
    SCORE_SUPPORT_MISMATCH = "score_support_mismatch"
    FRESHNESS_MISMATCH = "freshness_mismatch"
    DUPLICATE_SUPPORT_OVERLAP = "duplicate_support_overlap"
    MATURITY_MISMATCH = "maturity_mismatch"


class UncertaintyEstimate(StrictModel):
    """Structured uncertainty interpretation derived from visible signal facts."""

    uncertainty_estimate_id: str = Field(description="Canonical uncertainty-estimate identifier.")
    signal_id: str = Field(description="Signal identifier the estimate describes.")
    uncertainty_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Deterministic uncertainty score used by arbitration.",
    )
    base_uncertainty_source: str = Field(
        description="Source used to derive the uncertainty score."
    )
    lineage_complete: bool = Field(
        description="Whether minimum signal lineage completeness was present."
    )
    validation_status: DerivedArtifactValidationStatus = Field(
        description="Validation status visible on the source signal."
    )
    evidence_grade: EvidenceGrade | None = Field(
        default=None,
        description="Evidence grade associated with the signal when available.",
    )
    freshness_state: FreshnessState = Field(
        description="Freshness label relative to the arbitration as-of time."
    )
    factors: list[str] = Field(
        default_factory=list,
        description="Explicit factors that shaped the uncertainty estimate.",
    )
    method_name: str = Field(description="Deterministic heuristic used to build the estimate.")
    provenance: ProvenanceRecord = Field(description="Traceability for the uncertainty estimate.")

    @model_validator(mode="after")
    def validate_method(self) -> Self:
        """Require explicit estimation method metadata."""

        if not self.method_name:
            raise ValueError("method_name must be non-empty.")
        if not self.base_uncertainty_source:
            raise ValueError("base_uncertainty_source must be non-empty.")
        return self


class SignalCalibration(TimestampedModel):
    """Deterministic normalized view of a raw signal for comparison only."""

    signal_calibration_id: str = Field(description="Canonical signal-calibration identifier.")
    signal_id: str = Field(description="Source signal identifier.")
    company_id: str = Field(description="Covered company identifier.")
    raw_primary_score: float = Field(description="Original signal primary score.")
    normalized_score: float = Field(
        ge=-1.0,
        le=1.0,
        description="Clamped comparable score used for ranking.",
    )
    absolute_strength: float = Field(
        ge=0.0,
        le=1.0,
        description="Absolute score magnitude used for ranking.",
    )
    calibration_method: str = Field(
        description="Deterministic calibration method label."
    )
    uncertainty_estimate: UncertaintyEstimate = Field(
        description="Structured uncertainty interpretation for the signal."
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes or caveats attached to calibration.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the calibration.")

    @model_validator(mode="after")
    def validate_strength(self) -> Self:
        """Require internally consistent normalized strength."""

        if round(self.absolute_strength, 10) != round(abs(self.normalized_score), 10):
            raise ValueError("absolute_strength must equal abs(normalized_score).")
        if not self.calibration_method:
            raise ValueError("calibration_method must be non-empty.")
        return self


class ArbitrationRule(StrictModel):
    """Code-owned rule metadata recorded in arbitration decisions."""

    arbitration_rule_id: str = Field(description="Canonical arbitration-rule identifier.")
    rule_name: str = Field(description="Stable rule name.")
    description: str = Field(description="Human-readable description of the rule.")
    priority: int = Field(ge=1, description="Rule priority in the deterministic order.")
    blocking: bool = Field(description="Whether the rule can block primary selection.")
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes attached to the rule definition.",
    )

    @model_validator(mode="after")
    def validate_rule(self) -> Self:
        """Require explicit rule metadata."""

        if not self.rule_name:
            raise ValueError("rule_name must be non-empty.")
        if not self.description:
            raise ValueError("description must be non-empty.")
        return self


class SignalConflict(TimestampedModel):
    """Explicit conflict or comparability problem observed during arbitration."""

    signal_conflict_id: str = Field(description="Canonical signal-conflict identifier.")
    company_id: str = Field(description="Covered company identifier.")
    conflict_kind: SignalConflictKind = Field(
        description="Conflict kind observed between signals or signal support."
    )
    signal_ids: list[str] = Field(
        default_factory=list,
        description="Signal identifiers implicated in the conflict.",
    )
    blocking: bool = Field(description="Whether the conflict should block primary selection.")
    message: str = Field(description="Human-readable conflict explanation.")
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Supporting artifact identifiers related to the conflict.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the conflict.")

    @model_validator(mode="after")
    def validate_signal_links(self) -> Self:
        """Require enough signal linkage for the conflict kind."""

        minimum_count = (
            1
            if self.conflict_kind is SignalConflictKind.SCORE_SUPPORT_MISMATCH
            else 2
        )
        if len(self.signal_ids) < minimum_count:
            raise ValueError(
                "signal_ids must contain enough signal identifiers for the requested conflict kind."
            )
        if not self.message:
            raise ValueError("message must be non-empty.")
        return self


class RankingExplanation(StrictModel):
    """Embedded explanation describing one signal's arbitration rank."""

    signal_id: str = Field(description="Signal identifier explained by the rank row.")
    rank: int = Field(ge=1, description="Final deterministic rank of the signal.")
    rule_trace: list[str] = Field(
        default_factory=list,
        description="Short ordered explanation of why the signal received this rank.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Warnings still relevant even if the signal ranked well.",
    )
    why_not_selected: str | None = Field(
        default=None,
        description="Optional explanation when the signal was not selected as primary.",
    )

    @model_validator(mode="after")
    def validate_trace(self) -> Self:
        """Require at least one rule-trace explanation."""

        if not self.rule_trace:
            raise ValueError("rule_trace must contain at least one explanation.")
        return self


class ArbitrationDecision(TimestampedModel):
    """Structured, inspectable outcome of deterministic signal arbitration."""

    arbitration_decision_id: str = Field(
        description="Canonical arbitration-decision identifier."
    )
    company_id: str = Field(description="Covered company identifier.")
    candidate_signal_ids: list[str] = Field(
        default_factory=list,
        description="Signals still under consideration after exclusion rules.",
    )
    selected_primary_signal_id: str | None = Field(
        default=None,
        description="Selected primary signal when arbitration resolved cleanly.",
    )
    prioritized_signal_ids: list[str] = Field(
        default_factory=list,
        description="Signals ordered by deterministic arbitration priority.",
    )
    suppressed_signal_ids: list[str] = Field(
        default_factory=list,
        description="Signals suppressed due to duplicate or lower-priority status.",
    )
    applied_rules: list[ArbitrationRule] = Field(
        default_factory=list,
        description="Code-owned rules applied while making the decision.",
    )
    conflict_ids: list[str] = Field(
        default_factory=list,
        description="Signal-conflict identifiers observed during arbitration.",
    )
    ranking_explanations: list[RankingExplanation] = Field(
        default_factory=list,
        description="Rank explanations for prioritized candidate signals.",
    )
    review_required: bool = Field(
        default=True,
        description="Whether the arbitration outcome still requires human review.",
    )
    summary: str = Field(description="Short explanation of the arbitration outcome.")
    provenance: ProvenanceRecord = Field(description="Traceability for the arbitration decision.")

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        """Ensure selected and ranked signals remain internally coherent."""

        if not self.summary:
            raise ValueError("summary must be non-empty.")
        if self.selected_primary_signal_id is not None and (
            self.selected_primary_signal_id not in self.candidate_signal_ids
            or self.selected_primary_signal_id not in self.prioritized_signal_ids
        ):
            raise ValueError(
                "selected_primary_signal_id must appear in candidate_signal_ids and prioritized_signal_ids."
            )
        ranked_signal_ids = [explanation.signal_id for explanation in self.ranking_explanations]
        if ranked_signal_ids and ranked_signal_ids != self.prioritized_signal_ids:
            raise ValueError(
                "ranking_explanations must be ordered to match prioritized_signal_ids."
            )
        return self


class SignalBundle(TimestampedModel):
    """Persisted arbitration bundle that links raw signals to one decision context."""

    signal_bundle_id: str = Field(description="Canonical signal-bundle identifier.")
    company_id: str = Field(description="Covered company identifier.")
    as_of_time: datetime | None = Field(
        default=None,
        description="Optional information cutoff respected by the bundle.",
    )
    component_signal_ids: list[str] = Field(
        default_factory=list,
        description="Raw signal identifiers examined while building the bundle.",
    )
    signal_calibration_ids: list[str] = Field(
        default_factory=list,
        description="Calibration identifiers produced for the component signals.",
    )
    signal_conflict_ids: list[str] = Field(
        default_factory=list,
        description="Conflict identifiers produced for the bundle.",
    )
    arbitration_decision_id: str = Field(
        description="Arbitration decision associated with the bundle."
    )
    bundle_summary: str = Field(description="Short summary of the bundle and its outcome.")
    review_required: bool = Field(
        default=True,
        description="Whether the bundle remains review-facing and non-autonomous.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the signal bundle.")

    @model_validator(mode="after")
    def validate_bundle(self) -> Self:
        """Require preserved signal linkage and decision linkage."""

        if not self.component_signal_ids:
            raise ValueError("component_signal_ids must contain at least one signal identifier.")
        if not self.signal_calibration_ids:
            raise ValueError(
                "signal_calibration_ids must contain at least one calibration identifier."
            )
        if not self.arbitration_decision_id:
            raise ValueError("arbitration_decision_id must be non-empty.")
        if not self.bundle_summary:
            raise ValueError("bundle_summary must be non-empty.")
        return self
