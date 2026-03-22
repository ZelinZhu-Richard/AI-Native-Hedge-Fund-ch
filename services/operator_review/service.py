from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import Field

from libraries.core import (
    ArtifactWorkspace,
    build_provenance,
    resolve_artifact_workspace,
    resolve_artifact_workspace_from_stage_root,
)
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ActionRecommendationSummary,
    ArtifactStorageLocation,
    AuditLog,
    AuditOutcome,
    DerivedArtifactValidationStatus,
    EscalationStatus,
    EvidenceGrade,
    MemoryScope,
    PaperTrade,
    PaperTradeStatus,
    PipelineEventType,
    PortfolioAttribution,
    PortfolioProposal,
    PortfolioProposalStatus,
    PositionAttribution,
    PositionIdea,
    ResearchBrief,
    ResearchReviewStatus,
    RetrievalContext,
    RetrievalQuery,
    ReviewAssignment,
    ReviewContext,
    ReviewDecision,
    ReviewNote,
    ReviewOutcome,
    ReviewQueueItem,
    ReviewQueueStatus,
    ReviewTargetType,
    RiskCheck,
    Signal,
    SignalStatus,
    StressTestResult,
    StressTestRun,
    StrictModel,
    SupportingEvidenceLink,
    WorkflowStatus,
)
from libraries.utils import (
    apply_review_decision_to_paper_trade,
    apply_review_decision_to_portfolio_proposal,
    make_prefixed_id,
)
from services.audit import AuditEventRequest, AuditLoggingService
from services.monitoring import (
    MonitoringService,
    RecordPipelineEventRequest,
    RecordRunSummaryRequest,
)
from services.operator_review.loaders import (
    LoadedReviewWorkspace,
    load_review_queue_items,
    load_review_workspace,
    target_key,
)
from services.operator_review.storage import LocalReviewArtifactStore
from services.research_memory import ResearchMemoryService, SearchResearchMemoryRequest

TTarget = TypeVar("TTarget")


class SyncReviewQueueRequest(StrictModel):
    """Request to materialize or refresh operator review queue items."""

    research_root: Path | None = Field(default=None)
    signal_root: Path | None = Field(default=None)
    portfolio_root: Path | None = Field(default=None)
    review_root: Path | None = Field(default=None)
    audit_root: Path | None = Field(default=None)
    include_resolved: bool = Field(
        default=False,
        description="Whether the returned queue items should include resolved entries.",
    )


class SyncReviewQueueResponse(StrictModel):
    """Response returned after queue synchronization."""

    queue_items: list[ReviewQueueItem] = Field(default_factory=list)
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ListReviewQueueRequest(StrictModel):
    """Request to list persisted review queue items."""

    research_root: Path | None = Field(default=None)
    signal_root: Path | None = Field(default=None)
    portfolio_root: Path | None = Field(default=None)
    review_root: Path | None = Field(default=None)
    audit_root: Path | None = Field(default=None)
    target_type: ReviewTargetType | None = Field(default=None)
    queue_status: ReviewQueueStatus | None = Field(default=None)
    include_resolved: bool = Field(default=False)
    sync: bool = Field(default=True)


class ReviewQueueListResponse(StrictModel):
    """Review queue listing response."""

    items: list[ReviewQueueItem] = Field(default_factory=list)
    total: int = Field(description="Count of queue items returned.")
    notes: list[str] = Field(default_factory=list)


class GetReviewContextRequest(StrictModel):
    """Request to build one operator-console review context."""

    target_type: ReviewTargetType = Field(description="Type of reviewable target.")
    target_id: str = Field(description="Identifier of the reviewable target.")
    research_root: Path | None = Field(default=None)
    signal_root: Path | None = Field(default=None)
    portfolio_root: Path | None = Field(default=None)
    portfolio_analysis_root: Path | None = Field(default=None)
    review_root: Path | None = Field(default=None)
    audit_root: Path | None = Field(default=None)
    sync: bool = Field(default=True)


class AddReviewNoteRequest(StrictModel):
    """Request to attach one operator note to a reviewable object."""

    target_type: ReviewTargetType = Field(description="Type of reviewable target.")
    target_id: str = Field(description="Identifier of the reviewable target.")
    author_id: str = Field(description="Operator authoring the note.")
    body: str = Field(description="Free-form review note content.")
    related_artifact_ids: list[str] = Field(default_factory=list)
    research_root: Path | None = Field(default=None)
    signal_root: Path | None = Field(default=None)
    portfolio_root: Path | None = Field(default=None)
    review_root: Path | None = Field(default=None)
    audit_root: Path | None = Field(default=None)


class AddReviewNoteResponse(StrictModel):
    """Response returned after a review note is added."""

    review_note: ReviewNote = Field(description="Persisted review note.")
    queue_item: ReviewQueueItem = Field(description="Updated queue item.")
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    audit_log: AuditLog = Field(description="Audit log for the action.")


class AssignReviewRequest(StrictModel):
    """Request to assign one queue item to one operator."""

    target_type: ReviewTargetType = Field(description="Type of reviewable target.")
    target_id: str = Field(description="Identifier of the reviewable target.")
    assigned_by: str = Field(description="Operator creating the assignment.")
    assignee_id: str = Field(description="Operator receiving the assignment.")
    research_root: Path | None = Field(default=None)
    signal_root: Path | None = Field(default=None)
    portfolio_root: Path | None = Field(default=None)
    review_root: Path | None = Field(default=None)
    audit_root: Path | None = Field(default=None)


class AssignReviewResponse(StrictModel):
    """Response returned after assignment changes."""

    review_assignment: ReviewAssignment = Field(description="Persisted active assignment.")
    queue_item: ReviewQueueItem = Field(description="Updated queue item.")
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    audit_log: AuditLog = Field(description="Audit log for the action.")


class ApplyReviewActionRequest(StrictModel):
    """Request to apply one explicit review action to a reviewable object."""

    target_type: ReviewTargetType = Field(description="Type of reviewable target.")
    target_id: str = Field(description="Identifier of the reviewable target.")
    reviewer_id: str = Field(description="Operator applying the review action.")
    outcome: ReviewOutcome = Field(description="Requested review outcome.")
    rationale: str = Field(description="Decision rationale.")
    blocking_issues: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)
    research_root: Path | None = Field(default=None)
    signal_root: Path | None = Field(default=None)
    portfolio_root: Path | None = Field(default=None)
    review_root: Path | None = Field(default=None)
    audit_root: Path | None = Field(default=None)


class ApplyReviewActionResponse(StrictModel):
    """Response returned after applying one review action."""

    review_decision: ReviewDecision = Field(description="Persisted review decision.")
    queue_item: ReviewQueueItem = Field(description="Updated queue item.")
    updated_target: ResearchBrief | Signal | PortfolioProposal | PaperTrade = Field(
        description="Updated target after the review action."
    )
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    audit_log: AuditLog = Field(description="Audit log for the action.")


class OperatorReviewService(BaseService):
    """Coordinate explicit operator review workflows across research and paper-trading layers."""

    capability_name = "operator_review"
    capability_description = "Surfaces reviewable artifacts, captures review actions, and preserves auditability."

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["ResearchBrief", "Signal", "PortfolioProposal", "PaperTrade"],
            produces=["ReviewQueueItem", "ReviewDecision", "ReviewContext"],
            api_routes=[
                "GET /reviews/queue",
                "GET /reviews/context/{target_type}/{target_id}",
                "POST /reviews/notes",
                "POST /reviews/assignments",
                "POST /reviews/actions",
            ],
        )

    def sync_review_queue(self, request: SyncReviewQueueRequest) -> SyncReviewQueueResponse:
        """Materialize or refresh review queue items from persisted artifacts."""

        research_root, signal_root, portfolio_root, review_root, audit_root = self._resolve_roots(
            research_root=request.research_root,
            signal_root=request.signal_root,
            portfolio_root=request.portfolio_root,
            review_root=request.review_root,
            audit_root=request.audit_root,
        )
        workspace = load_review_workspace(
            research_root=research_root,
            signal_root=signal_root,
            portfolio_root=portfolio_root,
            review_root=review_root,
            audit_root=audit_root,
        )
        store = LocalReviewArtifactStore(root=review_root, clock=self.clock)
        storage_locations: list[ArtifactStorageLocation] = []
        notes: list[str] = []
        active_keys: set[str] = set()
        for target_type, target in self._iter_reviewable_targets(workspace):
            key = target_key(target_type, self._target_id(target))
            active_keys.add(key)
            existing = workspace.queue_items_by_target_key.get(key)
            queue_item = self._build_queue_item(
                target_type=target_type,
                target=target,
                existing=existing,
                workspace=workspace,
            )
            changed = existing is None or self._queue_item_changed(existing=existing, candidate=queue_item)
            workspace.queue_items_by_target_key[key] = queue_item
            if changed:
                storage_locations.append(
                    store.persist_model(
                        artifact_id=queue_item.review_queue_item_id,
                        category="queue_items",
                        model=queue_item,
                        source_reference_ids=queue_item.provenance.source_reference_ids,
                    )
                )
                event_type = (
                    "review_queue_item_created" if existing is None else "review_queue_item_refreshed"
                )
                audit_response = self._audit_service().record_event(
                    AuditEventRequest(
                        event_type=event_type,
                        actor_type="service",
                        actor_id="operator_review",
                        target_type=target_type.value,
                        target_id=self._target_id(target),
                        action="queued",
                        outcome=AuditOutcome.SUCCESS,
                        reason=queue_item.summary,
                        request_id=queue_item.review_queue_item_id,
                        status_before=existing.current_target_status if existing is not None else None,
                        status_after=queue_item.current_target_status,
                        related_artifact_ids=[queue_item.review_queue_item_id],
                        notes=[f"queue_status={queue_item.queue_status.value}"],
                    ),
                    output_root=audit_root,
                )
                storage_locations.append(audit_response.storage_location)
        for key, existing in list(workspace.queue_items_by_target_key.items()):
            if key in active_keys:
                continue
            stale_target = self._load_target_if_exists(
                target_type=existing.target_type,
                target_id=existing.target_id,
                workspace=workspace,
            )
            if stale_target is None:
                continue
            resolved_queue_item = existing.model_copy(
                update={
                    "current_target_status": self._target_status(stale_target),
                    "queue_status": ReviewQueueStatus.RESOLVED,
                    "escalation_status": (
                        EscalationStatus.RESOLVED
                        if existing.escalation_status is not EscalationStatus.NONE
                        else EscalationStatus.NONE
                    ),
                    "updated_at": self.clock.now(),
                }
            )
            if self._queue_item_changed(existing=existing, candidate=resolved_queue_item):
                workspace.queue_items_by_target_key[key] = resolved_queue_item
                storage_locations.append(
                    store.persist_model(
                        artifact_id=resolved_queue_item.review_queue_item_id,
                        category="queue_items",
                        model=resolved_queue_item,
                        source_reference_ids=resolved_queue_item.provenance.source_reference_ids,
                    )
                )
                audit_response = self._audit_service().record_event(
                    AuditEventRequest(
                        event_type="review_queue_item_refreshed",
                        actor_type="service",
                        actor_id="operator_review",
                        target_type=existing.target_type.value,
                        target_id=existing.target_id,
                        action="refresh",
                        outcome=AuditOutcome.SUCCESS,
                        reason="Queue item refreshed to reflect a non-reviewable target state.",
                        request_id=resolved_queue_item.review_queue_item_id,
                        status_before=existing.current_target_status,
                        status_after=resolved_queue_item.current_target_status,
                        related_artifact_ids=[resolved_queue_item.review_queue_item_id],
                        notes=[f"queue_status={resolved_queue_item.queue_status.value}"],
                    ),
                    output_root=audit_root,
                )
                storage_locations.append(audit_response.storage_location)
        items = self._filtered_queue_items(
            queue_items=list(workspace.queue_items_by_target_key.values()),
            target_type=None,
            queue_status=None,
            include_resolved=request.include_resolved,
        )
        if not items:
            notes.append("No reviewable targets were found.")
        return SyncReviewQueueResponse(
            queue_items=sorted(items, key=lambda item: item.updated_at, reverse=True),
            storage_locations=storage_locations,
            notes=notes,
        )

    def list_review_queue(self, request: ListReviewQueueRequest) -> ReviewQueueListResponse:
        """List persisted review queue items, optionally after a sync pass."""

        notes: list[str] = []
        if request.sync:
            sync_response = self.sync_review_queue(
                SyncReviewQueueRequest(
                    research_root=request.research_root,
                    signal_root=request.signal_root,
                    portfolio_root=request.portfolio_root,
                    review_root=request.review_root,
                    audit_root=request.audit_root,
                    include_resolved=True,
                )
            )
            notes.extend(sync_response.notes)
        _, _, _, review_root, _ = self._resolve_roots(
            research_root=request.research_root,
            signal_root=request.signal_root,
            portfolio_root=request.portfolio_root,
            review_root=request.review_root,
            audit_root=request.audit_root,
        )
        items = self._filtered_queue_items(
            queue_items=load_review_queue_items(review_root),
            target_type=request.target_type,
            queue_status=request.queue_status,
            include_resolved=request.include_resolved,
        )
        items = sorted(items, key=lambda item: item.updated_at, reverse=True)
        return ReviewQueueListResponse(items=items, total=len(items), notes=notes)

    def get_review_context(self, request: GetReviewContextRequest) -> ReviewContext:
        """Build a derived operator-console context for one reviewable object."""

        research_root, signal_root, portfolio_root, review_root, audit_root = self._resolve_roots(
            research_root=request.research_root,
            signal_root=request.signal_root,
            portfolio_root=request.portfolio_root,
            review_root=request.review_root,
            audit_root=request.audit_root,
            portfolio_analysis_root=request.portfolio_analysis_root,
        )
        artifact_workspace = self._resolve_workspace(
            research_root=request.research_root,
            signal_root=request.signal_root,
            portfolio_root=request.portfolio_root,
            review_root=request.review_root,
            audit_root=request.audit_root,
            portfolio_analysis_root=request.portfolio_analysis_root,
        )
        portfolio_analysis_root = (
            request.portfolio_analysis_root or artifact_workspace.portfolio_analysis_root
        )
        if request.sync:
            self.sync_review_queue(
                SyncReviewQueueRequest(
                    research_root=research_root,
                    signal_root=signal_root,
                    portfolio_root=portfolio_root,
                    review_root=review_root,
                    audit_root=audit_root,
                    include_resolved=True,
                )
            )
        workspace = load_review_workspace(
            research_root=research_root,
            signal_root=signal_root,
            portfolio_root=portfolio_root,
            review_root=review_root,
            audit_root=audit_root,
            portfolio_analysis_root=portfolio_analysis_root,
        )
        key = target_key(request.target_type, request.target_id)
        queue_item = workspace.queue_items_by_target_key.get(key)
        if queue_item is None:
            raise ValueError(f"No review queue item exists for `{request.target_type.value}:{request.target_id}`.")

        review_notes = list(workspace.review_notes_by_target_key.get(key, []))
        review_decisions = list(workspace.review_decisions_by_target_key.get(key, []))
        review_decisions.sort(key=lambda decision: decision.decided_at, reverse=True)
        review_assignment = (
            workspace.review_assignments_by_id.get(queue_item.review_assignment_id)
            if queue_item.review_assignment_id is not None
            else None
        )
        audit_logs = list(workspace.audit_logs_by_target_key.get(key, []))[:10]

        research_brief = None
        hypothesis = None
        counter_hypothesis = None
        evidence_assessment = None
        signal = None
        portfolio_proposal = None
        paper_trade = None
        supporting_evidence_links: list[SupportingEvidenceLink] = []
        risk_checks: list[RiskCheck] = []
        related_signals: list[Signal] = []
        position_ideas: list[PositionIdea] = []
        portfolio_attribution: PortfolioAttribution | None = None
        position_attributions: list[PositionAttribution] = []
        stress_test_run: StressTestRun | None = None
        stress_test_results: list[StressTestResult] = []

        if request.target_type is ReviewTargetType.RESEARCH_BRIEF:
            research_brief = self._require_target(workspace.research_briefs_by_id, request.target_id)
            hypothesis = workspace.hypotheses_by_id.get(research_brief.hypothesis_id)
            counter_hypothesis = workspace.counter_hypotheses_by_id.get(
                research_brief.counter_hypothesis_id
            )
            evidence_assessment = workspace.evidence_assessments_by_id.get(
                research_brief.evidence_assessment_id
            )
            supporting_evidence_links = list(research_brief.supporting_evidence_links)
            related_signals = self._related_signals_for_research_brief(
                research_brief=research_brief,
                workspace=workspace,
            )
        elif request.target_type is ReviewTargetType.SIGNAL:
            signal = self._require_target(workspace.signals_by_id, request.target_id)
            supporting_evidence_links = self._supporting_links_for_signal(signal=signal, workspace=workspace)
            related_signals = self._related_signals_for_signal(signal=signal, workspace=workspace)
        elif request.target_type is ReviewTargetType.PORTFOLIO_PROPOSAL:
            portfolio_proposal = self._require_target(
                workspace.portfolio_proposals_by_id,
                request.target_id,
            )
            risk_checks = list(portfolio_proposal.risk_checks)
            position_ideas = list(portfolio_proposal.position_ideas)
            related_signals = self._signals_for_position_ideas(position_ideas=position_ideas, workspace=workspace)
            supporting_evidence_links = self._supporting_links_for_position_ideas(
                position_ideas=position_ideas,
                workspace=workspace,
            )
            (
                portfolio_attribution,
                position_attributions,
                stress_test_run,
                stress_test_results,
            ) = self._portfolio_analysis_for_proposal(
                portfolio_proposal=portfolio_proposal,
                workspace=workspace,
            )
        elif request.target_type is ReviewTargetType.PAPER_TRADE:
            paper_trade = self._require_target(workspace.paper_trades_by_id, request.target_id)
            portfolio_proposal = workspace.portfolio_proposals_by_id.get(paper_trade.portfolio_proposal_id)
            if portfolio_proposal is not None:
                risk_checks = list(portfolio_proposal.risk_checks)
                (
                    portfolio_attribution,
                    position_attributions,
                    stress_test_run,
                    stress_test_results,
                ) = self._portfolio_analysis_for_proposal(
                    portfolio_proposal=portfolio_proposal,
                    workspace=workspace,
                )
            position_idea = workspace.position_ideas_by_id.get(paper_trade.position_idea_id)
            if position_idea is not None:
                position_ideas = [position_idea]
                related_signals = self._signals_for_position_ideas(
                    position_ideas=position_ideas,
                    workspace=workspace,
                )
                supporting_evidence_links = self._supporting_links_for_position_ideas(
                    position_ideas=position_ideas,
                    workspace=workspace,
                )

        return ReviewContext(
            queue_item=queue_item,
            research_brief=research_brief,
            hypothesis=hypothesis,
            counter_hypothesis=counter_hypothesis,
            evidence_assessment=evidence_assessment,
            signal=signal,
            portfolio_proposal=portfolio_proposal,
            paper_trade=paper_trade,
            portfolio_attribution=portfolio_attribution,
            position_attributions=position_attributions,
            stress_test_run=stress_test_run,
            stress_test_results=stress_test_results,
            supporting_evidence_links=supporting_evidence_links,
            risk_checks=risk_checks,
            related_signals=related_signals,
            position_ideas=position_ideas,
            review_notes=review_notes,
            review_decisions=review_decisions,
            audit_logs=audit_logs,
            review_assignment=review_assignment,
            action_recommendation=queue_item.action_recommendation,
            related_prior_work=self._build_related_prior_work(
                workspace=workspace,
                request=request,
                research_root=research_root,
                review_root=review_root,
                company_id=self._company_id_for_review_target(
                    research_brief=research_brief,
                    signal=signal,
                    portfolio_proposal=portfolio_proposal,
                    paper_trade=paper_trade,
                    position_ideas=position_ideas,
                    workspace=workspace,
                ),
            ),
        )

    def add_review_note(self, request: AddReviewNoteRequest) -> AddReviewNoteResponse:
        """Attach one review note to a queue item."""

        research_root, signal_root, portfolio_root, review_root, audit_root = self._resolve_roots(
            research_root=request.research_root,
            signal_root=request.signal_root,
            portfolio_root=request.portfolio_root,
            review_root=request.review_root,
            audit_root=request.audit_root,
        )
        self.sync_review_queue(
            SyncReviewQueueRequest(
                research_root=research_root,
                signal_root=signal_root,
                portfolio_root=portfolio_root,
                review_root=review_root,
                audit_root=audit_root,
                include_resolved=True,
            )
        )
        workspace = load_review_workspace(
            research_root=research_root,
            signal_root=signal_root,
            portfolio_root=portfolio_root,
            review_root=review_root,
            audit_root=audit_root,
        )
        key = target_key(request.target_type, request.target_id)
        queue_item = workspace.queue_items_by_target_key.get(key)
        if queue_item is None:
            raise ValueError(f"No review queue item exists for `{request.target_type.value}:{request.target_id}`.")

        now = self.clock.now()
        review_note = ReviewNote(
            review_note_id=make_prefixed_id("rnote"),
            target_type=request.target_type,
            target_id=request.target_id,
            author_id=request.author_id,
            created_at=now,
            body=request.body,
            related_artifact_ids=request.related_artifact_ids,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="operator_review_note",
                upstream_artifact_ids=[request.target_id, queue_item.review_queue_item_id],
                notes=[f"author_id={request.author_id}"],
            ),
            updated_at=now,
        )
        updated_queue_item = queue_item.model_copy(
            update={
                "review_note_ids": self._append_unique(queue_item.review_note_ids, review_note.review_note_id),
                "updated_at": now,
            }
        )
        store = LocalReviewArtifactStore(root=review_root, clock=self.clock)
        storage_locations = [
            store.persist_model(
                artifact_id=review_note.review_note_id,
                category="review_notes",
                model=review_note,
                source_reference_ids=review_note.provenance.source_reference_ids,
            ),
            store.persist_model(
                artifact_id=updated_queue_item.review_queue_item_id,
                category="queue_items",
                model=updated_queue_item,
                source_reference_ids=updated_queue_item.provenance.source_reference_ids,
            ),
        ]
        audit_response = self._audit_service().record_event(
            AuditEventRequest(
                event_type="review_note_added",
                actor_type="human",
                actor_id=request.author_id,
                target_type=request.target_type.value,
                target_id=request.target_id,
                action="add_note",
                outcome=AuditOutcome.SUCCESS,
                reason=request.body,
                request_id=review_note.review_note_id,
                status_before=queue_item.queue_status.value,
                status_after=updated_queue_item.queue_status.value,
                related_artifact_ids=[
                    queue_item.review_queue_item_id,
                    review_note.review_note_id,
                    *request.related_artifact_ids,
                ],
                notes=["note_added_to_review_queue_item"],
            ),
            output_root=audit_root,
        )
        storage_locations.append(audit_response.storage_location)
        return AddReviewNoteResponse(
            review_note=review_note,
            queue_item=updated_queue_item,
            storage_locations=storage_locations,
            audit_log=audit_response.audit_log,
        )

    def assign_review(self, request: AssignReviewRequest) -> AssignReviewResponse:
        """Create or replace the active assignment for one queue item."""

        research_root, signal_root, portfolio_root, review_root, audit_root = self._resolve_roots(
            research_root=request.research_root,
            signal_root=request.signal_root,
            portfolio_root=request.portfolio_root,
            review_root=request.review_root,
            audit_root=request.audit_root,
        )
        self.sync_review_queue(
            SyncReviewQueueRequest(
                research_root=research_root,
                signal_root=signal_root,
                portfolio_root=portfolio_root,
                review_root=review_root,
                audit_root=audit_root,
                include_resolved=True,
            )
        )
        workspace = load_review_workspace(
            research_root=research_root,
            signal_root=signal_root,
            portfolio_root=portfolio_root,
            review_root=review_root,
            audit_root=audit_root,
        )
        key = target_key(request.target_type, request.target_id)
        queue_item = workspace.queue_items_by_target_key.get(key)
        if queue_item is None:
            raise ValueError(f"No review queue item exists for `{request.target_type.value}:{request.target_id}`.")

        now = self.clock.now()
        store = LocalReviewArtifactStore(root=review_root, clock=self.clock)
        storage_locations: list[ArtifactStorageLocation] = []
        if queue_item.review_assignment_id is not None:
            existing_assignment = workspace.review_assignments_by_id.get(queue_item.review_assignment_id)
            if existing_assignment is not None and existing_assignment.active:
                deactivated_assignment = existing_assignment.model_copy(
                    update={
                        "active": False,
                        "updated_at": now,
                    }
                )
                storage_locations.append(
                    store.persist_model(
                        artifact_id=deactivated_assignment.review_assignment_id,
                        category="review_assignments",
                        model=deactivated_assignment,
                        source_reference_ids=deactivated_assignment.provenance.source_reference_ids,
                    )
                )

        assignment = ReviewAssignment(
            review_assignment_id=make_prefixed_id("rassign"),
            queue_item_id=queue_item.review_queue_item_id,
            assigned_by=request.assigned_by,
            assignee_id=request.assignee_id,
            assigned_at=now,
            active=True,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="operator_review_assignment",
                upstream_artifact_ids=[queue_item.review_queue_item_id, request.target_id],
                notes=[f"assignee_id={request.assignee_id}"],
            ),
            created_at=now,
            updated_at=now,
        )
        updated_queue_item = queue_item.model_copy(
            update={
                "review_assignment_id": assignment.review_assignment_id,
                "queue_status": (
                    ReviewQueueStatus.IN_REVIEW
                    if queue_item.queue_status
                    in {ReviewQueueStatus.PENDING_REVIEW, ReviewQueueStatus.AWAITING_REVISION}
                    else queue_item.queue_status
                ),
                "updated_at": now,
            }
        )
        storage_locations.extend(
            [
                store.persist_model(
                    artifact_id=assignment.review_assignment_id,
                    category="review_assignments",
                    model=assignment,
                    source_reference_ids=assignment.provenance.source_reference_ids,
                ),
                store.persist_model(
                    artifact_id=updated_queue_item.review_queue_item_id,
                    category="queue_items",
                    model=updated_queue_item,
                    source_reference_ids=updated_queue_item.provenance.source_reference_ids,
                ),
            ]
        )
        audit_response = self._audit_service().record_event(
            AuditEventRequest(
                event_type="review_assignment_changed",
                actor_type="human",
                actor_id=request.assigned_by,
                target_type=request.target_type.value,
                target_id=request.target_id,
                action="assign",
                outcome=AuditOutcome.SUCCESS,
                reason=f"Assigned review to `{request.assignee_id}`.",
                request_id=assignment.review_assignment_id,
                status_before=queue_item.queue_status.value,
                status_after=updated_queue_item.queue_status.value,
                related_artifact_ids=[
                    queue_item.review_queue_item_id,
                    assignment.review_assignment_id,
                ],
                notes=[f"assignee_id={request.assignee_id}"],
            ),
            output_root=audit_root,
        )
        storage_locations.append(audit_response.storage_location)
        return AssignReviewResponse(
            review_assignment=assignment,
            queue_item=updated_queue_item,
            storage_locations=storage_locations,
            audit_log=audit_response.audit_log,
        )

    def apply_review_action(self, request: ApplyReviewActionRequest) -> ApplyReviewActionResponse:
        """Create a review decision, update the target, and record audit state."""

        workflow_run_id = make_prefixed_id("reviewflow")
        monitoring_root = self._resolve_workspace(
            research_root=request.research_root,
            signal_root=request.signal_root,
            portfolio_root=request.portfolio_root,
            review_root=request.review_root,
            audit_root=request.audit_root,
        ).monitoring_root
        monitoring_service = MonitoringService(clock=self.clock)
        started_at = self.clock.now()
        start_event = monitoring_service.record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name="review_action",
                workflow_run_id=workflow_run_id,
                service_name=self.capability_name,
                event_type=PipelineEventType.RUN_STARTED,
                status=WorkflowStatus.RUNNING,
                message=(
                    f"Review action started for `{request.target_type.value}:{request.target_id}`."
                ),
                related_artifact_ids=[request.target_id],
                notes=[f"reviewer_id={request.reviewer_id}"],
            ),
            output_root=monitoring_root,
        )
        try:
            response = self._apply_review_action_impl(
                request,
                workflow_run_id=workflow_run_id,
            )
        except Exception as exc:
            failed_event = monitoring_service.record_pipeline_event(
                RecordPipelineEventRequest(
                    workflow_name="review_action",
                    workflow_run_id=workflow_run_id,
                    service_name=self.capability_name,
                    event_type=PipelineEventType.RUN_FAILED,
                    status=WorkflowStatus.FAILED,
                    message=(
                        "Review action failed for "
                        f"`{request.target_type.value}:{request.target_id}`: {exc}"
                    ),
                    related_artifact_ids=[request.target_id],
                    notes=[f"reviewer_id={request.reviewer_id}"],
                ),
                output_root=monitoring_root,
            )
            monitoring_service.record_run_summary(
                RecordRunSummaryRequest(
                    workflow_name="review_action",
                    workflow_run_id=workflow_run_id,
                    service_name=self.capability_name,
                    requested_by=request.reviewer_id,
                    status=WorkflowStatus.FAILED,
                    started_at=started_at,
                    completed_at=self.clock.now(),
                    storage_locations=[],
                    produced_artifact_ids=[request.target_id],
                    pipeline_event_ids=[
                        start_event.pipeline_event.pipeline_event_id,
                        failed_event.pipeline_event.pipeline_event_id,
                    ],
                    failure_messages=[str(exc)],
                    notes=[f"target_type={request.target_type.value}"],
                    outputs_expected=True,
                ),
                output_root=monitoring_root,
            )
            raise

        review_event = monitoring_service.record_pipeline_event(
            RecordPipelineEventRequest(
                workflow_name="review_action",
                workflow_run_id=workflow_run_id,
                service_name=self.capability_name,
                event_type=PipelineEventType.REVIEW_ACTION,
                status=WorkflowStatus.SUCCEEDED,
                message=(
                    f"Review action `{request.outcome.value}` completed for "
                    f"`{request.target_type.value}:{request.target_id}`."
                ),
                related_artifact_ids=[
                    request.target_id,
                    response.review_decision.review_decision_id,
                    response.queue_item.review_queue_item_id,
                    response.audit_log.audit_log_id,
                ],
                notes=[f"reviewer_id={request.reviewer_id}"],
            ),
            output_root=monitoring_root,
        )
        monitoring_service.record_run_summary(
            RecordRunSummaryRequest(
                workflow_name="review_action",
                workflow_run_id=workflow_run_id,
                service_name=self.capability_name,
                requested_by=request.reviewer_id,
                status=WorkflowStatus.SUCCEEDED,
                started_at=started_at,
                completed_at=self.clock.now(),
                storage_locations=response.storage_locations,
                produced_artifact_ids=[
                    request.target_id,
                    response.review_decision.review_decision_id,
                    response.queue_item.review_queue_item_id,
                    response.audit_log.audit_log_id,
                ],
                pipeline_event_ids=[
                    start_event.pipeline_event.pipeline_event_id,
                    review_event.pipeline_event.pipeline_event_id,
                ],
                notes=[
                    f"target_type={request.target_type.value}",
                    f"outcome={request.outcome.value}",
                ],
                outputs_expected=True,
            ),
            output_root=monitoring_root,
        )
        return response

    def _apply_review_action_impl(
        self,
        request: ApplyReviewActionRequest,
        *,
        workflow_run_id: str,
    ) -> ApplyReviewActionResponse:
        """Create a review decision, update the target, and record audit state."""

        research_root, signal_root, portfolio_root, review_root, audit_root = self._resolve_roots(
            research_root=request.research_root,
            signal_root=request.signal_root,
            portfolio_root=request.portfolio_root,
            review_root=request.review_root,
            audit_root=request.audit_root,
        )
        self.sync_review_queue(
            SyncReviewQueueRequest(
                research_root=research_root,
                signal_root=signal_root,
                portfolio_root=portfolio_root,
                review_root=review_root,
                audit_root=audit_root,
                include_resolved=True,
            )
        )
        workspace = load_review_workspace(
            research_root=research_root,
            signal_root=signal_root,
            portfolio_root=portfolio_root,
            review_root=review_root,
            audit_root=audit_root,
        )
        key = target_key(request.target_type, request.target_id)
        queue_item = workspace.queue_items_by_target_key.get(key)
        if queue_item is None:
            raise ValueError(f"No review queue item exists for `{request.target_type.value}:{request.target_id}`.")
        target = self._load_target_for_action(
            target_type=request.target_type,
            target_id=request.target_id,
            workspace=workspace,
        )
        status_before = self._target_status(target)
        self._validate_review_action(
            target_type=request.target_type,
            target=target,
            outcome=request.outcome,
            workspace=workspace,
        )

        now = self.clock.now()
        review_decision = ReviewDecision(
            review_decision_id=make_prefixed_id("review"),
            target_type=request.target_type,
            target_id=request.target_id,
            reviewer_id=request.reviewer_id,
            outcome=request.outcome,
            decided_at=now,
            rationale=request.rationale,
            blocking_issues=request.blocking_issues,
            conditions=request.conditions,
            review_notes=request.review_notes,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="operator_review_action",
                upstream_artifact_ids=[request.target_id, queue_item.review_queue_item_id],
                workflow_run_id=workflow_run_id,
                notes=[f"outcome={request.outcome.value}"],
            ),
            created_at=now,
            updated_at=now,
        )
        updated_target = self._apply_target_review_action(
            target_type=request.target_type,
            target=target,
            review_decision=review_decision,
        )
        status_after = self._target_status(updated_target)
        updated_queue_item = queue_item.model_copy(
            update={
                "current_target_status": status_after,
                "queue_status": self._queue_status_from_outcome(request.outcome),
                "escalation_status": self._escalation_status_after_action(
                    current=queue_item.escalation_status,
                    outcome=request.outcome,
                ),
                "review_decision_ids": self._append_unique(
                    queue_item.review_decision_ids,
                    review_decision.review_decision_id,
                ),
                "updated_at": now,
            }
        )
        store = LocalReviewArtifactStore(root=review_root, clock=self.clock)
        storage_locations = [
            store.persist_model(
                artifact_id=review_decision.review_decision_id,
                category="review_decisions",
                model=review_decision,
                source_reference_ids=review_decision.provenance.source_reference_ids,
            ),
            self._persist_updated_target(
                target_type=request.target_type,
                target=updated_target,
                research_root=research_root,
                signal_root=signal_root,
                portfolio_root=portfolio_root,
            ),
            store.persist_model(
                artifact_id=updated_queue_item.review_queue_item_id,
                category="queue_items",
                model=updated_queue_item,
                source_reference_ids=updated_queue_item.provenance.source_reference_ids,
            ),
        ]
        audit_response = self._audit_service().record_event(
            AuditEventRequest(
                event_type=(
                    "review_escalation_requested"
                    if request.outcome is ReviewOutcome.ESCALATE
                    else "review_action_applied"
                ),
                actor_type="human",
                actor_id=request.reviewer_id,
                target_type=request.target_type.value,
                target_id=request.target_id,
                action=request.outcome.value,
                outcome=(
                    AuditOutcome.SUCCESS
                    if request.outcome is ReviewOutcome.APPROVE
                    else AuditOutcome.WARNING
                ),
                reason=request.rationale,
                request_id=workflow_run_id,
                status_before=status_before,
                status_after=status_after,
                related_artifact_ids=[
                    queue_item.review_queue_item_id,
                    review_decision.review_decision_id,
                ],
                notes=request.review_notes,
            ),
            output_root=audit_root,
        )
        storage_locations.append(audit_response.storage_location)
        return ApplyReviewActionResponse(
            review_decision=review_decision,
            queue_item=updated_queue_item,
            updated_target=updated_target,
            storage_locations=storage_locations,
            audit_log=audit_response.audit_log,
        )

    def _resolve_roots(
        self,
        *,
        research_root: Path | None,
        signal_root: Path | None,
        portfolio_root: Path | None,
        review_root: Path | None,
        audit_root: Path | None,
        portfolio_analysis_root: Path | None = None,
    ) -> tuple[Path, Path, Path, Path, Path]:
        """Resolve artifact roots for operator review workflows."""

        workspace = self._resolve_workspace(
            research_root=research_root,
            signal_root=signal_root,
            portfolio_root=portfolio_root,
            review_root=review_root,
            audit_root=audit_root,
            portfolio_analysis_root=portfolio_analysis_root,
        )
        return (
            research_root or workspace.research_root,
            signal_root or workspace.signal_root,
            portfolio_root or workspace.portfolio_root,
            review_root or workspace.review_root,
            audit_root or workspace.audit_root,
        )

    def _resolve_workspace(
        self,
        *,
        research_root: Path | None,
        signal_root: Path | None,
        portfolio_root: Path | None,
        review_root: Path | None,
        audit_root: Path | None,
        portfolio_analysis_root: Path | None = None,
    ) -> ArtifactWorkspace:
        """Resolve one shared workspace and reject mismatched explicit review roots."""

        explicit_roots = [
            root
            for root in (
                research_root,
                signal_root,
                portfolio_root,
                review_root,
                audit_root,
                portfolio_analysis_root,
            )
            if root is not None
        ]
        if not explicit_roots:
            return resolve_artifact_workspace()
        workspace_parents = {root.resolve().parent for root in explicit_roots}
        if len(workspace_parents) != 1:
            raise ValueError(
                "Operator review roots must belong to the same artifact workspace when mixed explicit roots are supplied."
            )
        return resolve_artifact_workspace_from_stage_root(explicit_roots[0])

    def _iter_reviewable_targets(
        self,
        workspace: LoadedReviewWorkspace,
    ) -> list[tuple[ReviewTargetType, ResearchBrief | Signal | PortfolioProposal | PaperTrade]]:
        """Collect currently reviewable targets across supported domains."""

        targets: list[tuple[ReviewTargetType, ResearchBrief | Signal | PortfolioProposal | PaperTrade]] = []
        for brief in workspace.research_briefs_by_id.values():
            if brief.review_status in {
                ResearchReviewStatus.PENDING_HUMAN_REVIEW,
                ResearchReviewStatus.REVISION_REQUESTED,
            }:
                targets.append((ReviewTargetType.RESEARCH_BRIEF, brief))
        for signal in workspace.signals_by_id.values():
            if signal.status is SignalStatus.CANDIDATE:
                targets.append((ReviewTargetType.SIGNAL, signal))
        for proposal in workspace.portfolio_proposals_by_id.values():
            if proposal.status in {
                PortfolioProposalStatus.PENDING_REVIEW,
                PortfolioProposalStatus.DRAFT,
            }:
                targets.append((ReviewTargetType.PORTFOLIO_PROPOSAL, proposal))
        for paper_trade in workspace.paper_trades_by_id.values():
            if paper_trade.status is PaperTradeStatus.PROPOSED:
                targets.append((ReviewTargetType.PAPER_TRADE, paper_trade))
        return sorted(targets, key=lambda item: item[1].created_at, reverse=True)

    def _build_queue_item(
        self,
        *,
        target_type: ReviewTargetType,
        target: ResearchBrief | Signal | PortfolioProposal | PaperTrade,
        existing: ReviewQueueItem | None,
        workspace: LoadedReviewWorkspace,
    ) -> ReviewQueueItem:
        """Build or refresh one queue item from a reviewable target."""

        now = self.clock.now()
        title, summary = self._target_title_summary(target_type=target_type, target=target)
        recommendation = self._action_recommendation(
            target_type=target_type,
            target=target,
            workspace=workspace,
        )
        return ReviewQueueItem(
            review_queue_item_id=(
                existing.review_queue_item_id if existing is not None else make_prefixed_id("rqueue")
            ),
            target_type=target_type,
            target_id=self._target_id(target),
            queue_status=self._queue_status_for_sync(existing=existing),
            current_target_status=self._target_status(target),
            title=title,
            summary=summary,
            submitted_at=existing.submitted_at if existing is not None else now,
            escalation_status=(
                existing.escalation_status if existing is not None else EscalationStatus.NONE
            ),
            action_recommendation=recommendation,
            review_note_ids=list(existing.review_note_ids) if existing is not None else [],
            review_decision_ids=list(existing.review_decision_ids) if existing is not None else [],
            review_assignment_id=(existing.review_assignment_id if existing is not None else None),
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="operator_review_queue_sync",
                upstream_artifact_ids=[self._target_id(target)],
                notes=[f"target_type={target_type.value}"],
            ),
            created_at=existing.created_at if existing is not None else now,
            updated_at=now if existing is not None else now,
        )

    def _queue_item_changed(self, *, existing: ReviewQueueItem, candidate: ReviewQueueItem) -> bool:
        """Compare queue items while ignoring expected refresh timestamp churn."""

        return existing.model_dump(exclude={"updated_at"}) != candidate.model_dump(
            exclude={"updated_at"}
        )

    def _filtered_queue_items(
        self,
        *,
        queue_items: list[ReviewQueueItem],
        target_type: ReviewTargetType | None,
        queue_status: ReviewQueueStatus | None,
        include_resolved: bool,
    ) -> list[ReviewQueueItem]:
        """Filter queue items for list responses."""

        items = queue_items
        if target_type is not None:
            items = [item for item in items if item.target_type is target_type]
        if queue_status is not None:
            items = [item for item in items if item.queue_status is queue_status]
        if not include_resolved:
            items = [item for item in items if item.queue_status is not ReviewQueueStatus.RESOLVED]
        return items

    def _action_recommendation(
        self,
        *,
        target_type: ReviewTargetType,
        target: ResearchBrief | Signal | PortfolioProposal | PaperTrade,
        workspace: LoadedReviewWorkspace,
    ) -> ActionRecommendationSummary:
        """Build the conservative recommendation shown to operators."""

        if target_type is ReviewTargetType.RESEARCH_BRIEF:
            brief = target
            assert isinstance(brief, ResearchBrief)
            assessment = workspace.evidence_assessments_by_id.get(brief.evidence_assessment_id)
            if assessment is None or not brief.supporting_evidence_links:
                return ActionRecommendationSummary(
                    recommended_outcome=ReviewOutcome.ESCALATE,
                    summary="Research brief is missing linked evidence support or assessment.",
                    blocking_reasons=["Missing evidence assessment or supporting evidence links."],
                    warnings=[],
                    follow_up_actions=["Restore missing research linkage before review."],
                )
            if assessment.grade in {EvidenceGrade.STRONG, EvidenceGrade.MODERATE}:
                return ActionRecommendationSummary(
                    recommended_outcome=ReviewOutcome.APPROVE,
                    summary="Evidence support is sufficient for manual approval consideration.",
                    blocking_reasons=[],
                    warnings=list(brief.key_counterarguments),
                    follow_up_actions=list(brief.next_validation_steps),
                )
            if assessment.grade is EvidenceGrade.WEAK:
                return ActionRecommendationSummary(
                    recommended_outcome=ReviewOutcome.NEEDS_REVISION,
                    summary="Research brief has weak support and should be revised before promotion.",
                    blocking_reasons=[],
                    warnings=list(assessment.key_gaps),
                    follow_up_actions=list(brief.next_validation_steps),
                )
            return ActionRecommendationSummary(
                recommended_outcome=ReviewOutcome.ESCALATE,
                summary="Research brief support is insufficient for a normal approval path.",
                blocking_reasons=["Evidence support is insufficient."],
                warnings=list(assessment.key_gaps),
                follow_up_actions=list(brief.next_validation_steps),
            )
        if target_type is ReviewTargetType.SIGNAL:
            signal = target
            assert isinstance(signal, Signal)
            lineage_complete = self._signal_lineage_complete(signal=signal)
            exposes_uncertainty = bool(signal.uncertainties)
            if (
                lineage_complete
                and exposes_uncertainty
                and signal.validation_status is DerivedArtifactValidationStatus.VALIDATED
            ):
                return ActionRecommendationSummary(
                    recommended_outcome=ReviewOutcome.APPROVE,
                    summary="Signal lineage, uncertainty, and validation are explicit enough for manual approval consideration.",
                    blocking_reasons=[],
                    warnings=[],
                    follow_up_actions=["Confirm the signal still fits the active evaluation slice."],
                )
            blocking_reasons: list[str] = []
            if signal.validation_status is not DerivedArtifactValidationStatus.VALIDATED:
                blocking_reasons.append(
                    "Signal is not validated and should not be operator-approved yet."
                )
            if not lineage_complete:
                blocking_reasons.append("Signal lineage is incomplete.")
            if not exposes_uncertainty:
                blocking_reasons.append("Signal does not expose uncertainty explicitly.")
            return ActionRecommendationSummary(
                recommended_outcome=ReviewOutcome.NEEDS_REVISION,
                summary="Signal review should request revisions because validation, lineage, or uncertainty is incomplete.",
                blocking_reasons=blocking_reasons,
                warnings=[],
                follow_up_actions=[
                    "Complete validation, restore missing lineage, and add explicit uncertainty before approval."
                ],
            )
        if target_type is ReviewTargetType.PORTFOLIO_PROPOSAL:
            proposal = target
            assert isinstance(proposal, PortfolioProposal)
            blocking_reasons = list(proposal.blocking_issues)
            if not blocking_reasons:
                blocking_reasons = [
                    check.message for check in proposal.risk_checks if check.blocking
                ]
            if blocking_reasons:
                return ActionRecommendationSummary(
                    recommended_outcome=ReviewOutcome.NEEDS_REVISION,
                    summary="Portfolio proposal has blocking risk issues and should not be approved.",
                    blocking_reasons=blocking_reasons,
                    warnings=[],
                    follow_up_actions=["Resolve blocking risk checks before approval."],
                )
            return ActionRecommendationSummary(
                recommended_outcome=None,
                summary="Manual review is still required even though no blocking risk issues are present.",
                blocking_reasons=[],
                warnings=["No automatic approval claim is made for portfolio proposals."],
                follow_up_actions=["Review position rationale and risk checks manually."],
            )
        paper_trade = target
        assert isinstance(paper_trade, PaperTrade)
        parent_proposal = workspace.portfolio_proposals_by_id.get(paper_trade.portfolio_proposal_id)
        if (
            parent_proposal is not None
            and parent_proposal.status is PortfolioProposalStatus.APPROVED
            and not parent_proposal.blocking_issues
            and not any(check.blocking for check in parent_proposal.risk_checks)
        ):
            return ActionRecommendationSummary(
                recommended_outcome=ReviewOutcome.APPROVE,
                summary="Parent proposal is approved and has no blocking issues.",
                blocking_reasons=[],
                warnings=["Paper trade remains simulated only."],
                follow_up_actions=["Confirm the reference price assumption before approval."],
            )
        return ActionRecommendationSummary(
            recommended_outcome=ReviewOutcome.NEEDS_REVISION,
            summary="Paper trade should remain review-bound because parent approval is incomplete or blocked.",
            blocking_reasons=[],
            warnings=["Parent proposal approval or risk state is not sufficient for trade approval."],
            follow_up_actions=["Resolve proposal review or blocking issues before approving the trade."],
        )

    def _target_title_summary(
        self,
        *,
        target_type: ReviewTargetType,
        target: ResearchBrief | Signal | PortfolioProposal | PaperTrade,
    ) -> tuple[str, str]:
        """Build queue display text for one target."""

        if target_type is ReviewTargetType.RESEARCH_BRIEF:
            brief = target
            assert isinstance(brief, ResearchBrief)
            return brief.title, brief.context_summary
        if target_type is ReviewTargetType.SIGNAL:
            signal = target
            assert isinstance(signal, Signal)
            return (
                f"{signal.company_id} {signal.signal_family}",
                signal.thesis_summary,
            )
        if target_type is ReviewTargetType.PORTFOLIO_PROPOSAL:
            proposal = target
            assert isinstance(proposal, PortfolioProposal)
            return proposal.name, proposal.summary
        paper_trade = target
        assert isinstance(paper_trade, PaperTrade)
        return (
            f"{paper_trade.side.value} {paper_trade.symbol} paper trade",
            f"Paper-only trade candidate for {paper_trade.notional_usd:.2f} USD notional.",
        )

    def _target_id(
        self,
        target: ResearchBrief | Signal | PortfolioProposal | PaperTrade,
    ) -> str:
        """Return the canonical identifier for a supported target object."""

        if isinstance(target, ResearchBrief):
            return target.research_brief_id
        if isinstance(target, Signal):
            return target.signal_id
        if isinstance(target, PortfolioProposal):
            return target.portfolio_proposal_id
        return target.paper_trade_id

    def _target_status(
        self,
        target: ResearchBrief | Signal | PortfolioProposal | PaperTrade,
    ) -> str:
        """Return the current lifecycle status string for a supported target."""

        if isinstance(target, ResearchBrief):
            return target.review_status.value
        if isinstance(target, Signal):
            return target.status.value
        if isinstance(target, PortfolioProposal):
            return target.status.value
        return target.status.value

    def _queue_status_for_sync(self, *, existing: ReviewQueueItem | None) -> ReviewQueueStatus:
        """Choose queue status during sync without silently resolving items."""

        if existing is None:
            return ReviewQueueStatus.PENDING_REVIEW
        if existing.queue_status in {
            ReviewQueueStatus.IN_REVIEW,
            ReviewQueueStatus.AWAITING_REVISION,
            ReviewQueueStatus.ESCALATED,
        }:
            return existing.queue_status
        return ReviewQueueStatus.PENDING_REVIEW

    def _load_target_for_action(
        self,
        *,
        target_type: ReviewTargetType,
        target_id: str,
        workspace: LoadedReviewWorkspace,
    ) -> ResearchBrief | Signal | PortfolioProposal | PaperTrade:
        """Load the concrete review target for one action request."""

        if target_type is ReviewTargetType.RESEARCH_BRIEF:
            return self._require_target(workspace.research_briefs_by_id, target_id)
        if target_type is ReviewTargetType.SIGNAL:
            return self._require_target(workspace.signals_by_id, target_id)
        if target_type is ReviewTargetType.PORTFOLIO_PROPOSAL:
            return self._require_target(workspace.portfolio_proposals_by_id, target_id)
        return self._require_target(workspace.paper_trades_by_id, target_id)

    def _load_target_if_exists(
        self,
        *,
        target_type: ReviewTargetType,
        target_id: str,
        workspace: LoadedReviewWorkspace,
    ) -> ResearchBrief | Signal | PortfolioProposal | PaperTrade | None:
        """Load a target when present without raising for missing artifacts."""

        if target_type is ReviewTargetType.RESEARCH_BRIEF:
            return workspace.research_briefs_by_id.get(target_id)
        if target_type is ReviewTargetType.SIGNAL:
            return workspace.signals_by_id.get(target_id)
        if target_type is ReviewTargetType.PORTFOLIO_PROPOSAL:
            return workspace.portfolio_proposals_by_id.get(target_id)
        return workspace.paper_trades_by_id.get(target_id)

    def _validate_review_action(
        self,
        *,
        target_type: ReviewTargetType,
        target: ResearchBrief | Signal | PortfolioProposal | PaperTrade,
        outcome: ReviewOutcome,
        workspace: LoadedReviewWorkspace,
    ) -> None:
        """Reject unsafe or silently inconsistent review actions."""

        if target_type is ReviewTargetType.PORTFOLIO_PROPOSAL:
            proposal = target
            assert isinstance(proposal, PortfolioProposal)
            if outcome is ReviewOutcome.APPROVE and (
                proposal.blocking_issues or any(check.blocking for check in proposal.risk_checks)
            ):
                raise ValueError("Blocking portfolio proposals cannot be approved.")
        if target_type is ReviewTargetType.RESEARCH_BRIEF:
            brief = target
            assert isinstance(brief, ResearchBrief)
            if outcome is ReviewOutcome.APPROVE:
                assessment = workspace.evidence_assessments_by_id.get(brief.evidence_assessment_id)
                if assessment is None or not brief.supporting_evidence_links:
                    raise ValueError(
                        "Research briefs require linked evidence support and an evidence assessment before approval."
                    )
                if assessment.grade in {EvidenceGrade.WEAK, EvidenceGrade.INSUFFICIENT}:
                    raise ValueError(
                        "Research briefs with weak or insufficient support cannot be approved."
                    )
        if target_type is ReviewTargetType.SIGNAL:
            signal = target
            assert isinstance(signal, Signal)
            if outcome is ReviewOutcome.APPROVE:
                if signal.validation_status is not DerivedArtifactValidationStatus.VALIDATED:
                    raise ValueError("Signals require validated status before approval.")
                if not self._signal_lineage_complete(signal=signal):
                    raise ValueError("Signals require complete lineage before approval.")
                if not signal.uncertainties:
                    raise ValueError("Signals require explicit uncertainties before approval.")
        if target_type is ReviewTargetType.PAPER_TRADE:
            paper_trade = target
            assert isinstance(paper_trade, PaperTrade)
            if outcome is ReviewOutcome.APPROVE:
                parent_proposal = workspace.portfolio_proposals_by_id.get(
                    paper_trade.portfolio_proposal_id
                )
                if parent_proposal is None:
                    raise ValueError("Paper trades cannot be approved without a parent portfolio proposal.")
                if parent_proposal.status is not PortfolioProposalStatus.APPROVED:
                    raise ValueError("Paper trades require an approved parent portfolio proposal.")
                if parent_proposal.blocking_issues or any(
                    check.blocking for check in parent_proposal.risk_checks
                ):
                    raise ValueError("Paper trades cannot be approved while the parent proposal is blocked.")

    def _signal_lineage_complete(self, *, signal: Signal) -> bool:
        """Return whether the minimum lineage contract for signal approval is present."""

        return bool(
            signal.feature_ids
            and signal.lineage.feature_ids
            and signal.lineage.supporting_evidence_link_ids
            and signal.lineage.input_families
        )

    def _apply_target_review_action(
        self,
        *,
        target_type: ReviewTargetType,
        target: ResearchBrief | Signal | PortfolioProposal | PaperTrade,
        review_decision: ReviewDecision,
    ) -> ResearchBrief | Signal | PortfolioProposal | PaperTrade:
        """Apply one review decision to the requested target type."""

        if target_type is ReviewTargetType.RESEARCH_BRIEF:
            brief = target
            assert isinstance(brief, ResearchBrief)
            review_status = {
                ReviewOutcome.APPROVE: ResearchReviewStatus.APPROVED_FOR_FEATURE_WORK,
                ReviewOutcome.NEEDS_REVISION: ResearchReviewStatus.REVISION_REQUESTED,
                ReviewOutcome.REJECT: ResearchReviewStatus.REJECTED,
                ReviewOutcome.ESCALATE: brief.review_status,
            }[review_decision.outcome]
            return brief.model_copy(
                update={
                    "review_status": review_status,
                    "updated_at": review_decision.decided_at,
                }
            )
        if target_type is ReviewTargetType.SIGNAL:
            signal = target
            assert isinstance(signal, Signal)
            signal_status = {
                ReviewOutcome.APPROVE: SignalStatus.APPROVED,
                ReviewOutcome.NEEDS_REVISION: SignalStatus.CANDIDATE,
                ReviewOutcome.REJECT: SignalStatus.REJECTED,
                ReviewOutcome.ESCALATE: signal.status,
            }[review_decision.outcome]
            return signal.model_copy(
                update={
                    "status": signal_status,
                    "updated_at": review_decision.decided_at,
                }
            )
        if target_type is ReviewTargetType.PORTFOLIO_PROPOSAL:
            proposal = target
            assert isinstance(proposal, PortfolioProposal)
            return apply_review_decision_to_portfolio_proposal(
                portfolio_proposal=proposal,
                review_decision=review_decision,
            )
        paper_trade = target
        assert isinstance(paper_trade, PaperTrade)
        return apply_review_decision_to_paper_trade(
            paper_trade=paper_trade,
            review_decision=review_decision,
        )

    def _persist_updated_target(
        self,
        *,
        target_type: ReviewTargetType,
        target: ResearchBrief | Signal | PortfolioProposal | PaperTrade,
        research_root: Path,
        signal_root: Path,
        portfolio_root: Path,
    ) -> ArtifactStorageLocation:
        """Persist one updated review target back into its owning artifact root."""

        if target_type is ReviewTargetType.RESEARCH_BRIEF:
            root = research_root
            category = "research_briefs"
            artifact = target
            assert isinstance(artifact, ResearchBrief)
            artifact_id = artifact.research_brief_id
        elif target_type is ReviewTargetType.SIGNAL:
            root = signal_root
            category = "signals"
            artifact = target
            assert isinstance(artifact, Signal)
            artifact_id = artifact.signal_id
        elif target_type is ReviewTargetType.PORTFOLIO_PROPOSAL:
            root = portfolio_root
            category = "portfolio_proposals"
            artifact = target
            assert isinstance(artifact, PortfolioProposal)
            artifact_id = artifact.portfolio_proposal_id
        else:
            root = portfolio_root
            category = "paper_trades"
            artifact = target
            assert isinstance(artifact, PaperTrade)
            artifact_id = artifact.paper_trade_id

        destination_store = LocalReviewArtifactStore(root=root, clock=self.clock)
        return destination_store.persist_model(
            artifact_id=artifact_id,
            category=category,
            model=artifact,
            source_reference_ids=artifact.provenance.source_reference_ids,
        )

    def _related_signals_for_research_brief(
        self,
        *,
        research_brief: ResearchBrief,
        workspace: LoadedReviewWorkspace,
    ) -> list[Signal]:
        """Return signals linked to a research brief."""

        related = [
            signal
            for signal in workspace.signals_by_id.values()
            if signal.hypothesis_id == research_brief.hypothesis_id
            or research_brief.research_brief_id in signal.lineage.research_artifact_ids
        ]
        return sorted(related, key=lambda signal: signal.effective_at, reverse=True)

    def _related_signals_for_signal(
        self,
        *,
        signal: Signal,
        workspace: LoadedReviewWorkspace,
    ) -> list[Signal]:
        """Return related signals for the same company or hypothesis."""

        related = [
            candidate
            for candidate in workspace.signals_by_id.values()
            if candidate.company_id == signal.company_id
            and (
                candidate.hypothesis_id == signal.hypothesis_id
                or bool(
                    set(candidate.lineage.research_artifact_ids)
                    & set(signal.lineage.research_artifact_ids)
                )
            )
        ]
        unique = {candidate.signal_id: candidate for candidate in related}
        return sorted(unique.values(), key=lambda candidate: candidate.effective_at, reverse=True)

    def _supporting_links_for_signal(
        self,
        *,
        signal: Signal,
        workspace: LoadedReviewWorkspace,
    ) -> list[SupportingEvidenceLink]:
        """Resolve supporting evidence links referenced by one signal."""

        link_ids = set(signal.lineage.supporting_evidence_link_ids)
        links = self._supporting_links_from_research_artifact_ids(
            artifact_ids=signal.lineage.research_artifact_ids,
            workspace=workspace,
        )
        return [link for link in links if link.supporting_evidence_link_id in link_ids]

    def _signals_for_position_ideas(
        self,
        *,
        position_ideas: list[PositionIdea],
        workspace: LoadedReviewWorkspace,
    ) -> list[Signal]:
        """Resolve signals referenced by one or more position ideas."""

        signals = [
            workspace.signals_by_id[idea.signal_id]
            for idea in position_ideas
            if idea.signal_id in workspace.signals_by_id
        ]
        unique = {signal.signal_id: signal for signal in signals}
        return sorted(unique.values(), key=lambda signal: signal.effective_at, reverse=True)

    def _supporting_links_for_position_ideas(
        self,
        *,
        position_ideas: list[PositionIdea],
        workspace: LoadedReviewWorkspace,
    ) -> list[SupportingEvidenceLink]:
        """Resolve supporting evidence links referenced by one or more position ideas."""

        desired_link_ids = {
            link_id for idea in position_ideas for link_id in idea.supporting_evidence_link_ids
        }
        artifact_ids = [artifact_id for idea in position_ideas for artifact_id in idea.research_artifact_ids]
        links = self._supporting_links_from_research_artifact_ids(
            artifact_ids=artifact_ids,
            workspace=workspace,
        )
        unique_links = {
            link.supporting_evidence_link_id: link
            for link in links
            if link.supporting_evidence_link_id in desired_link_ids
        }
        return list(unique_links.values())

    def _portfolio_analysis_for_proposal(
        self,
        *,
        portfolio_proposal: PortfolioProposal,
        workspace: LoadedReviewWorkspace,
    ) -> tuple[
        PortfolioAttribution | None,
        list[PositionAttribution],
        StressTestRun | None,
        list[StressTestResult],
    ]:
        """Resolve proposal-linked attribution and stress artifacts when available."""

        portfolio_attribution = (
            workspace.portfolio_attributions_by_id.get(portfolio_proposal.portfolio_attribution_id)
            if portfolio_proposal.portfolio_attribution_id is not None
            else None
        )
        position_attributions = (
            [
                attribution
                for attribution_id in portfolio_attribution.position_attribution_ids
                if (
                    attribution := workspace.position_attributions_by_id.get(attribution_id)
                )
                is not None
            ]
            if portfolio_attribution is not None
            else []
        )
        stress_test_run = (
            workspace.stress_test_runs_by_id.get(portfolio_proposal.stress_test_run_id)
            if portfolio_proposal.stress_test_run_id is not None
            else None
        )
        stress_test_results = (
            [
                result
                for result_id in stress_test_run.stress_test_result_ids
                if (result := workspace.stress_test_results_by_id.get(result_id)) is not None
            ]
            if stress_test_run is not None
            else []
        )
        return portfolio_attribution, position_attributions, stress_test_run, stress_test_results

    def _company_id_for_review_target(
        self,
        *,
        research_brief: ResearchBrief | None,
        signal: Signal | None,
        portfolio_proposal: PortfolioProposal | None,
        paper_trade: PaperTrade | None,
        position_ideas: list[PositionIdea],
        workspace: LoadedReviewWorkspace,
    ) -> str | None:
        """Resolve one canonical company identifier for related-prior-work retrieval."""

        if research_brief is not None:
            return research_brief.company_id
        if signal is not None:
            return signal.company_id
        if position_ideas:
            company_ids = {idea.company_id for idea in position_ideas}
            if len(company_ids) == 1:
                return next(iter(company_ids))
        if portfolio_proposal is not None:
            company_ids = {idea.company_id for idea in portfolio_proposal.position_ideas}
            if len(company_ids) == 1:
                return next(iter(company_ids))
        if paper_trade is not None:
            position_idea = workspace.position_ideas_by_id.get(paper_trade.position_idea_id)
            if position_idea is not None:
                return position_idea.company_id
        return None

    def _build_related_prior_work(
        self,
        *,
        workspace: LoadedReviewWorkspace,
        request: GetReviewContextRequest,
        research_root: Path,
        review_root: Path,
        company_id: str | None,
    ) -> RetrievalContext | None:
        """Build advisory same-company prior-work retrieval context for operators."""

        if company_id is None:
            return None
        response = ResearchMemoryService(clock=self.clock).search_research_memory(
            SearchResearchMemoryRequest(
                workspace_root=review_root.parent,
                research_root=research_root,
                review_root=review_root,
                query=RetrievalQuery(
                    retrieval_query_id=make_prefixed_id("rqry"),
                    scopes=[
                        MemoryScope.EVIDENCE_ASSESSMENT,
                        MemoryScope.HYPOTHESIS,
                        MemoryScope.COUNTER_HYPOTHESIS,
                        MemoryScope.RESEARCH_BRIEF,
                        MemoryScope.MEMO,
                        MemoryScope.EXPERIMENT,
                        MemoryScope.REVIEW_NOTE,
                    ],
                    company_id=company_id,
                    limit=20,
                ),
            )
        )
        current_target_scope = {
            ReviewTargetType.RESEARCH_BRIEF: MemoryScope.RESEARCH_BRIEF,
        }.get(request.target_type)
        filtered_results = [
            result
            for result in response.retrieval_context.results
            if not (
                result.artifact_reference.artifact_id == request.target_id
                and current_target_scope is not None
                and result.scope is current_target_scope
            )
            and not (
                result.scope is MemoryScope.REVIEW_NOTE
                and (
                    note := workspace.review_notes_by_id.get(result.artifact_reference.artifact_id)
                ) is not None
                and note.target_type is request.target_type
                and note.target_id == request.target_id
            )
        ]
        return RetrievalContext(
            query=response.retrieval_context.query,
            results=filtered_results,
            evidence_results=response.retrieval_context.evidence_results,
            notes=response.retrieval_context.notes,
            semantic_retrieval_used=False,
        )

    def _supporting_links_from_research_artifact_ids(
        self,
        *,
        artifact_ids: list[str],
        workspace: LoadedReviewWorkspace,
    ) -> list[SupportingEvidenceLink]:
        """Resolve supporting evidence links from research brief or hypothesis artifacts."""

        links_by_id: dict[str, SupportingEvidenceLink] = {}
        for artifact_id in artifact_ids:
            brief = workspace.research_briefs_by_id.get(artifact_id)
            if brief is not None:
                for link in brief.supporting_evidence_links:
                    links_by_id.setdefault(link.supporting_evidence_link_id, link)
            hypothesis = workspace.hypotheses_by_id.get(artifact_id)
            if hypothesis is not None:
                for link in hypothesis.supporting_evidence_links:
                    links_by_id.setdefault(link.supporting_evidence_link_id, link)
        return list(links_by_id.values())

    def _queue_status_from_outcome(self, outcome: ReviewOutcome) -> ReviewQueueStatus:
        """Map one review outcome onto queue state."""

        return {
            ReviewOutcome.APPROVE: ReviewQueueStatus.RESOLVED,
            ReviewOutcome.REJECT: ReviewQueueStatus.RESOLVED,
            ReviewOutcome.NEEDS_REVISION: ReviewQueueStatus.AWAITING_REVISION,
            ReviewOutcome.ESCALATE: ReviewQueueStatus.ESCALATED,
        }[outcome]

    def _escalation_status_after_action(
        self,
        *,
        current: EscalationStatus,
        outcome: ReviewOutcome,
    ) -> EscalationStatus:
        """Map one action onto escalation state."""

        if outcome is ReviewOutcome.ESCALATE:
            return EscalationStatus.REQUESTED
        if current is not EscalationStatus.NONE:
            return EscalationStatus.RESOLVED
        return EscalationStatus.NONE

    def _require_target(self, target_map: dict[str, TTarget], target_id: str) -> TTarget:
        """Require a target object to exist in one loaded map."""

        target = target_map.get(target_id)
        if target is None:
            raise ValueError(f"Target `{target_id}` was not found.")
        return target

    def _append_unique(self, values: list[str], new_value: str) -> list[str]:
        """Append one identifier while preserving insertion order and uniqueness."""

        return list(dict.fromkeys([*values, new_value]))

    def _audit_service(self) -> AuditLoggingService:
        """Build an audit service using the shared clock."""

        return AuditLoggingService(clock=self.clock)
