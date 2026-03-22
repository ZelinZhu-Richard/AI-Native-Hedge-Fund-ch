from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import Field, model_validator

from libraries.schemas.base import ProvenanceRecord, ReviewOutcome, StrictModel, TimestampedModel

if TYPE_CHECKING:
    from libraries.schemas.portfolio import PaperTrade, PortfolioProposal, PositionIdea, RiskCheck
    from libraries.schemas.portfolio_analysis import (
        PortfolioAttribution,
        PositionAttribution,
        StressTestResult,
        StressTestRun,
    )
    from libraries.schemas.research import (
        CounterHypothesis,
        EvidenceAssessment,
        Hypothesis,
        ResearchBrief,
        Signal,
        SupportingEvidenceLink,
    )
    from libraries.schemas.retrieval import RetrievalContext
    from libraries.schemas.system import AuditLog


class ReviewTargetType(StrEnum):
    """Top-level reviewable object categories exposed to operators."""

    RESEARCH_BRIEF = "research_brief"
    SIGNAL = "signal"
    PORTFOLIO_PROPOSAL = "portfolio_proposal"
    PAPER_TRADE = "paper_trade"


class EscalationStatus(StrEnum):
    """Escalation lifecycle for one review queue item."""

    NONE = "none"
    REQUESTED = "requested"
    ESCALATED = "escalated"
    RESOLVED = "resolved"


class ReviewQueueStatus(StrEnum):
    """Operator queue lifecycle for one reviewable object."""

    PENDING_REVIEW = "pending_review"
    IN_REVIEW = "in_review"
    AWAITING_REVISION = "awaiting_revision"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class ActionRecommendationSummary(StrictModel):
    """Conservative action recommendation shown to operators."""

    recommended_outcome: ReviewOutcome | None = Field(
        default=None,
        description="Optional conservative suggested outcome for the operator.",
    )
    summary: str = Field(description="Short explanation of the recommendation.")
    blocking_reasons: list[str] = Field(
        default_factory=list,
        description="Explicit issues that should block approval consideration.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Visible warnings that do not necessarily block action.",
    )
    follow_up_actions: list[str] = Field(
        default_factory=list,
        description="Concrete next actions the operator should consider.",
    )

    @model_validator(mode="after")
    def validate_summary(self) -> ActionRecommendationSummary:
        """Require a non-empty recommendation summary."""

        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class ReviewNote(TimestampedModel):
    """Free-form operator note attached to a reviewable object."""

    review_note_id: str = Field(description="Canonical review-note identifier.")
    target_type: ReviewTargetType = Field(description="Type of object under review.")
    target_id: str = Field(description="Identifier of the object under review.")
    author_id: str = Field(description="Operator identifier that authored the note.")
    created_at: datetime = Field(description="UTC timestamp when the note was created.")
    body: str = Field(description="Operator note body.")
    related_artifact_ids: list[str] = Field(
        default_factory=list,
        description="Optional related artifact identifiers referenced by the note.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the review note.")

    @model_validator(mode="after")
    def validate_note(self) -> ReviewNote:
        """Require non-empty note content and linkage."""

        if not self.target_id:
            raise ValueError("target_id must be non-empty.")
        if not self.body:
            raise ValueError("body must be non-empty.")
        if not self.author_id:
            raise ValueError("author_id must be non-empty.")
        return self


class ReviewAssignment(TimestampedModel):
    """Single active assignment for one review queue item."""

    review_assignment_id: str = Field(description="Canonical review-assignment identifier.")
    queue_item_id: str = Field(description="Queue item identifier being assigned.")
    assigned_by: str = Field(description="Operator identifier that created the assignment.")
    assignee_id: str = Field(description="Operator identifier responsible for review.")
    assigned_at: datetime = Field(description="UTC timestamp when the assignment was created.")
    active: bool = Field(description="Whether the assignment is still active.")
    provenance: ProvenanceRecord = Field(description="Traceability for the review assignment.")

    @model_validator(mode="after")
    def validate_assignment(self) -> ReviewAssignment:
        """Require explicit queue and assignee linkage."""

        if not self.queue_item_id:
            raise ValueError("queue_item_id must be non-empty.")
        if not self.assigned_by:
            raise ValueError("assigned_by must be non-empty.")
        if not self.assignee_id:
            raise ValueError("assignee_id must be non-empty.")
        return self


class ReviewDecision(TimestampedModel):
    """Generic human review decision attached to a reviewable object."""

    review_decision_id: str = Field(description="Canonical review decision identifier.")
    target_type: ReviewTargetType = Field(description="Type of entity being reviewed.")
    target_id: str = Field(description="Identifier of the entity being reviewed.")
    reviewer_id: str = Field(description="Human reviewer identifier.")
    outcome: ReviewOutcome = Field(description="Decision outcome.")
    decided_at: datetime = Field(description="UTC timestamp when the decision was made.")
    rationale: str = Field(description="Reason for the decision.")
    blocking_issues: list[str] = Field(
        default_factory=list,
        description="Issues preventing approval if the outcome is not approval.",
    )
    conditions: list[str] = Field(
        default_factory=list,
        description="Conditions attached to the decision.",
    )
    review_notes: list[str] = Field(
        default_factory=list,
        description="Free-form review notes preserved with the decision.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the review decision.")

    @model_validator(mode="after")
    def validate_decision(self) -> ReviewDecision:
        """Ensure review decisions remain internally coherent."""

        if self.outcome == ReviewOutcome.APPROVE and self.blocking_issues:
            raise ValueError("Approval decisions must not carry blocking_issues.")
        if not self.target_id:
            raise ValueError("target_id must be non-empty.")
        if not self.reviewer_id:
            raise ValueError("reviewer_id must be non-empty.")
        if not self.rationale:
            raise ValueError("rationale must be non-empty.")
        return self


class ReviewQueueItem(TimestampedModel):
    """Persisted operator queue item for a reviewable object."""

    review_queue_item_id: str = Field(description="Canonical review-queue item identifier.")
    target_type: ReviewTargetType = Field(description="Type of object under review.")
    target_id: str = Field(description="Identifier of the object under review.")
    queue_status: ReviewQueueStatus = Field(description="Current queue lifecycle state.")
    current_target_status: str = Field(
        description="Current lifecycle status of the underlying target object."
    )
    title: str = Field(description="Short queue title for the review target.")
    summary: str = Field(description="Short queue summary for the review target.")
    submitted_at: datetime = Field(description="UTC time when the item entered the review queue.")
    escalation_status: EscalationStatus = Field(description="Current escalation state.")
    action_recommendation: ActionRecommendationSummary = Field(
        description="Conservative action recommendation shown to the operator."
    )
    review_note_ids: list[str] = Field(
        default_factory=list,
        description="Attached review-note identifiers.",
    )
    review_decision_ids: list[str] = Field(
        default_factory=list,
        description="Attached review-decision identifiers.",
    )
    review_assignment_id: str | None = Field(
        default=None,
        description="Current active review-assignment identifier when present.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the queue item.")

    @model_validator(mode="after")
    def validate_queue_item(self) -> ReviewQueueItem:
        """Require explicit target linkage and visible queue text."""

        if not self.target_id:
            raise ValueError("target_id must be non-empty.")
        if not self.title:
            raise ValueError("title must be non-empty.")
        if not self.summary:
            raise ValueError("summary must be non-empty.")
        return self


class ReviewContext(StrictModel):
    """Derived operator-console read model for one reviewable object."""

    queue_item: ReviewQueueItem = Field(description="Review queue metadata for the target.")
    research_brief: ResearchBrief | None = Field(
        default=None,
        description="Research brief payload when the target is research review.",
    )
    hypothesis: Hypothesis | None = Field(
        default=None,
        description="Primary hypothesis associated with a research brief target.",
    )
    counter_hypothesis: CounterHypothesis | None = Field(
        default=None,
        description="Primary critique associated with a research brief target.",
    )
    evidence_assessment: EvidenceAssessment | None = Field(
        default=None,
        description="Evidence assessment associated with the review target when applicable.",
    )
    signal: Signal | None = Field(
        default=None,
        description="Signal payload when the target is a signal review.",
    )
    portfolio_proposal: PortfolioProposal | None = Field(
        default=None,
        description="Portfolio proposal payload when applicable.",
    )
    paper_trade: PaperTrade | None = Field(
        default=None,
        description="Paper-trade payload when the target is a trade review.",
    )
    supporting_evidence_links: list[SupportingEvidenceLink] = Field(
        default_factory=list,
        description="Exact supporting evidence links relevant to the target.",
    )
    risk_checks: list[RiskCheck] = Field(
        default_factory=list,
        description="Risk checks relevant to the target.",
    )
    related_signals: list[Signal] = Field(
        default_factory=list,
        description="Signals related to the target for console display.",
    )
    position_ideas: list[PositionIdea] = Field(
        default_factory=list,
        description="Position ideas relevant to the target.",
    )
    portfolio_attribution: PortfolioAttribution | None = Field(
        default=None,
        description="Proposal attribution artifact when available.",
    )
    position_attributions: list[PositionAttribution] = Field(
        default_factory=list,
        description="Position-level attribution artifacts when available.",
    )
    stress_test_run: StressTestRun | None = Field(
        default=None,
        description="Stress-test batch linked to the proposal when available.",
    )
    stress_test_results: list[StressTestResult] = Field(
        default_factory=list,
        description="Scenario-level stress results linked to the proposal when available.",
    )
    review_notes: list[ReviewNote] = Field(
        default_factory=list,
        description="Persisted review notes for the target.",
    )
    review_decisions: list[ReviewDecision] = Field(
        default_factory=list,
        description="Persisted review decisions for the target.",
    )
    audit_logs: list[AuditLog] = Field(
        default_factory=list,
        description="Recent audit logs relevant to the target.",
    )
    review_assignment: ReviewAssignment | None = Field(
        default=None,
        description="Current review assignment when present.",
    )
    action_recommendation: ActionRecommendationSummary = Field(
        description="Current conservative action recommendation for the operator."
    )
    related_prior_work: RetrievalContext | None = Field(
        default=None,
        description="Advisory same-company prior work retrieved for operator context.",
    )

    @model_validator(mode="after")
    def validate_target_payload(self) -> ReviewContext:
        """Require at least one material target payload for the derived context."""

        if (
            self.research_brief is None
            and self.signal is None
            and self.portfolio_proposal is None
            and self.paper_trade is None
        ):
            raise ValueError("ReviewContext requires at least one reviewable target payload.")
        return self


def _rebuild_review_context() -> None:
    """Resolve cross-module references for the derived review context model."""

    from libraries.schemas.portfolio import PaperTrade, PortfolioProposal, PositionIdea, RiskCheck
    from libraries.schemas.portfolio_analysis import (
        PortfolioAttribution,
        PositionAttribution,
        StressTestResult,
        StressTestRun,
    )
    from libraries.schemas.research import (
        CounterHypothesis,
        EvidenceAssessment,
        Hypothesis,
        ResearchBrief,
        Signal,
        SupportingEvidenceLink,
    )
    from libraries.schemas.retrieval import RetrievalContext
    from libraries.schemas.system import AuditLog

    ReviewContext.model_rebuild(
        _types_namespace={
            "PaperTrade": PaperTrade,
            "PortfolioProposal": PortfolioProposal,
            "PositionIdea": PositionIdea,
            "PortfolioAttribution": PortfolioAttribution,
            "PositionAttribution": PositionAttribution,
            "RiskCheck": RiskCheck,
            "StressTestRun": StressTestRun,
            "StressTestResult": StressTestResult,
            "CounterHypothesis": CounterHypothesis,
            "EvidenceAssessment": EvidenceAssessment,
            "Hypothesis": Hypothesis,
            "ResearchBrief": ResearchBrief,
            "Signal": Signal,
            "SupportingEvidenceLink": SupportingEvidenceLink,
            "RetrievalContext": RetrievalContext,
            "AuditLog": AuditLog,
        }
    )


_rebuild_review_context()
