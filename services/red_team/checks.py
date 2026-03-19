from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TypeVar

from libraries.core import build_provenance
from libraries.schemas import (
    AdversarialInput,
    ConfidenceAssessment,
    EvaluationStatus,
    EvidenceAssessment,
    EvidenceGrade,
    Experiment,
    ExtractedClaim,
    GuardrailViolation,
    PaperTrade,
    PaperTradeStatus,
    ParsedDocumentText,
    PortfolioProposal,
    PortfolioProposalStatus,
    RecommendedMitigation,
    RedTeamCase,
    ResearchBrief,
    ReviewDecision,
    SafetyFinding,
    Severity,
    Signal,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id

OVERSTRONG_LANGUAGE_PATTERNS = (
    r"\bguaranteed\b",
    r"\bmust buy\b",
    r"\bclear alpha\b",
    r"\bcannot fail\b",
    r"\bwill certainly\b",
    r"\bproves\b",
)

TItem = TypeVar("TItem")

DEFAULT_SCENARIO_NAMES = (
    "missing_provenance",
    "contradictory_evidence",
    "timestamp_corruption",
    "incomplete_review_state",
    "unsupported_causal_claim",
    "malformed_portfolio_inputs",
    "weak_signal_lineage",
    "empty_extraction_downstream",
    "paper_trade_missing_approval_state",
    "evaluation_missing_references",
)


@dataclass
class LoadedRedTeamWorkspace:
    """In-memory view of persisted artifacts used by the red-team suite."""

    research_briefs: list[ResearchBrief] = field(default_factory=list)
    evidence_assessments: list[EvidenceAssessment] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)
    parsed_texts: list[ParsedDocumentText] = field(default_factory=list)
    claims: list[ExtractedClaim] = field(default_factory=list)
    portfolio_proposals: list[PortfolioProposal] = field(default_factory=list)
    paper_trades: list[PaperTrade] = field(default_factory=list)
    review_decisions: list[ReviewDecision] = field(default_factory=list)
    experiments: list[Experiment] = field(default_factory=list)

    @property
    def evidence_assessments_by_id(self) -> dict[str, EvidenceAssessment]:
        return {
            assessment.evidence_assessment_id: assessment for assessment in self.evidence_assessments
        }

    @property
    def review_decisions_by_id(self) -> dict[str, ReviewDecision]:
        return {decision.review_decision_id: decision for decision in self.review_decisions}

    @property
    def portfolio_proposals_by_id(self) -> dict[str, PortfolioProposal]:
        return {
            proposal.portfolio_proposal_id: proposal for proposal in self.portfolio_proposals
        }


@dataclass
class ScenarioArtifacts:
    """Structured outputs recorded for one executed red-team scenario."""

    red_team_case: RedTeamCase
    guardrail_violations: list[GuardrailViolation] = field(default_factory=list)
    safety_findings: list[SafetyFinding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def execute_red_team_scenario(
    *,
    scenario_name: str,
    workspace: LoadedRedTeamWorkspace,
    clock: Clock,
    workflow_run_id: str,
) -> ScenarioArtifacts | None:
    """Execute one deterministic adversarial scenario against cloned artifacts."""

    handlers = {
        "missing_provenance": _missing_provenance_case,
        "contradictory_evidence": _contradictory_evidence_case,
        "timestamp_corruption": _timestamp_corruption_case,
        "incomplete_review_state": _incomplete_review_state_case,
        "unsupported_causal_claim": _unsupported_causal_claim_case,
        "malformed_portfolio_inputs": _malformed_portfolio_inputs_case,
        "weak_signal_lineage": _weak_signal_lineage_case,
        "empty_extraction_downstream": _empty_extraction_downstream_case,
        "paper_trade_missing_approval_state": _paper_trade_missing_approval_state_case,
        "evaluation_missing_references": _evaluation_missing_references_case,
    }
    handler = handlers.get(scenario_name)
    if handler is None:
        raise ValueError(f"Unsupported red-team scenario `{scenario_name}`.")
    return handler(workspace=workspace, clock=clock, workflow_run_id=workflow_run_id)


def _missing_provenance_case(
    *,
    workspace: LoadedRedTeamWorkspace,
    clock: Clock,
    workflow_run_id: str,
) -> ScenarioArtifacts | None:
    signal = _first(workspace.signals)
    if signal is None:
        return None
    adversarial_signal = signal.model_copy(
        update={
            "provenance": signal.provenance.model_copy(
                update={
                    "processing_time": None,
                    "transformation_name": None,
                    "source_reference_ids": [],
                    "upstream_artifact_ids": [],
                }
            )
        }
    )
    case_id = _case_id(workflow_run_id=workflow_run_id, scenario_name="missing_provenance", target_id=signal.signal_id)
    related_artifact_ids = [signal.signal_id]
    adversarial_inputs = [
        _adversarial_input(
            case_id=case_id,
            input_kind="provenance_override",
            description="Clone the signal with no usable provenance linkage or transformation metadata.",
            target_type="signal",
            target_id=signal.signal_id,
            related_artifact_ids=related_artifact_ids,
            payload_summary="processing_time=null, transformation_name=null, source_reference_ids=[], upstream_artifact_ids=[]",
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    ]
    violations = _as_list(
        check_required_provenance_present(
            case_id=case_id,
            artifact=adversarial_signal,
            target_type="signal",
            target_id=signal.signal_id,
            related_artifact_ids=related_artifact_ids,
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    return _case_artifacts(
        case_id=case_id,
        name="Missing provenance on cloned signal",
        scenario_name="missing_provenance",
        target_type="signal",
        target_id=signal.signal_id,
        adversarial_inputs=adversarial_inputs,
        expected_guardrails=["required_provenance_present"],
        violations=violations,
        weaknesses=["missing_provenance"],
        notes=["Adversarial mutations were applied only to in-memory signal clones."],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def _contradictory_evidence_case(
    *,
    workspace: LoadedRedTeamWorkspace,
    clock: Clock,
    workflow_run_id: str,
) -> ScenarioArtifacts | None:
    brief = _first(workspace.research_briefs)
    if brief is None:
        return None
    assessment = workspace.evidence_assessments_by_id.get(brief.evidence_assessment_id)
    if assessment is None:
        assessment = EvidenceAssessment(
            evidence_assessment_id=make_canonical_id("evasmt", workflow_run_id, brief.research_brief_id),
            company_id=brief.company_id,
            hypothesis_id=brief.hypothesis_id,
            grade=EvidenceGrade.WEAK,
            supporting_evidence_link_ids=[link.supporting_evidence_link_id for link in brief.supporting_evidence_links],
            support_summary="Support is weak and contradictory.",
            key_gaps=["Contradictory evidence is unresolved."],
            contradiction_notes=["A contradictory demand warning was ignored in the summary."],
            review_status=brief.review_status,
            validation_status=brief.validation_status,
            confidence=ConfidenceAssessment(confidence=0.25, uncertainty=0.8),
            provenance=build_provenance(
                clock=clock,
                transformation_name="red_team_synthetic_evidence_assessment",
                upstream_artifact_ids=[brief.research_brief_id],
                workflow_run_id=workflow_run_id,
            ),
            created_at=clock.now(),
            updated_at=clock.now(),
        )
    adversarial_brief = brief.model_copy(
        update={
            "core_hypothesis": (
                f"{brief.core_hypothesis} This guaranteed outcome proves the thesis is already validated."
            ),
            "uncertainty_summary": "",
            "confidence": ConfidenceAssessment(confidence=0.3, uncertainty=0.85),
        }
    )
    adversarial_assessment = assessment.model_copy(
        update={
            "grade": EvidenceGrade.WEAK,
            "contradiction_notes": [
                *assessment.contradiction_notes,
                "Conflicting evidence contradicts the promoted thesis summary.",
            ],
            "confidence": ConfidenceAssessment(confidence=0.25, uncertainty=0.8),
        }
    )
    case_id = _case_id(
        workflow_run_id=workflow_run_id,
        scenario_name="contradictory_evidence",
        target_id=brief.research_brief_id,
    )
    related_artifact_ids = [brief.research_brief_id, adversarial_assessment.evidence_assessment_id]
    adversarial_inputs = [
        _adversarial_input(
            case_id=case_id,
            input_kind="research_brief_text_override",
            description="Inject overstrong certainty language into the thesis summary while contradictory evidence remains unresolved.",
            target_type="research_brief",
            target_id=brief.research_brief_id,
            related_artifact_ids=related_artifact_ids,
            payload_summary=adversarial_brief.core_hypothesis,
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    ]
    violations = _as_list(
        check_claim_strength_matches_support(
            case_id=case_id,
            target_type="research_brief",
            target_id=brief.research_brief_id,
            claim_text=adversarial_brief.core_hypothesis,
            evidence_grade=adversarial_assessment.grade,
            contradiction_notes=adversarial_assessment.contradiction_notes,
            confidence=adversarial_brief.confidence,
            uncertainties=[],
            related_artifact_ids=related_artifact_ids,
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    return _case_artifacts(
        case_id=case_id,
        name="Contradictory evidence ignored by strong thesis wording",
        scenario_name="contradictory_evidence",
        target_type="research_brief",
        target_id=brief.research_brief_id,
        adversarial_inputs=adversarial_inputs,
        expected_guardrails=["claim_strength_matches_support"],
        violations=violations,
        weaknesses=["contradictory_evidence_ignored", "overstrong_language"],
        notes=["The red-team case keeps the original brief intact and evaluates only the cloned summary."],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def _timestamp_corruption_case(
    *,
    workspace: LoadedRedTeamWorkspace,
    clock: Clock,
    workflow_run_id: str,
) -> ScenarioArtifacts | None:
    signal = _first(workspace.signals)
    if signal is None:
        return None
    corrupted_signal = signal.model_copy(
        update={"expires_at": signal.effective_at - timedelta(seconds=1)}
    )
    case_id = _case_id(
        workflow_run_id=workflow_run_id,
        scenario_name="timestamp_corruption",
        target_id=signal.signal_id,
    )
    adversarial_inputs = [
        _adversarial_input(
            case_id=case_id,
            input_kind="timestamp_corruption",
            description="Corrupt the cloned signal window so expiry precedes the intended effective time.",
            target_type="signal",
            target_id=signal.signal_id,
            related_artifact_ids=[signal.signal_id],
            payload_summary=(
                f"effective_at={signal.effective_at.isoformat()}, "
                f"expires_at={(signal.effective_at - timedelta(seconds=1)).isoformat()}"
            ),
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    ]
    violations = _as_list(
        check_timestamp_ordering_valid(
            case_id=case_id,
            target_type="signal",
            target_id=signal.signal_id,
            earlier_name="effective_at",
            earlier_value=corrupted_signal.effective_at,
            later_name="expires_at",
            later_value=corrupted_signal.expires_at,
            related_artifact_ids=[signal.signal_id],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    return _case_artifacts(
        case_id=case_id,
        name="Corrupted signal timestamp window",
        scenario_name="timestamp_corruption",
        target_type="signal",
        target_id=signal.signal_id,
        adversarial_inputs=adversarial_inputs,
        expected_guardrails=["timestamp_ordering_valid"],
        violations=violations,
        weaknesses=["timestamp_corruption"],
        notes=["Timestamp corruption is evaluated on a cloned signal only."],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def _incomplete_review_state_case(
    *,
    workspace: LoadedRedTeamWorkspace,
    clock: Clock,
    workflow_run_id: str,
) -> ScenarioArtifacts | None:
    proposal = _first(workspace.portfolio_proposals)
    if proposal is None:
        return None
    adversarial_proposal = proposal.model_copy(
        update={
            "status": PortfolioProposalStatus.APPROVED,
            "review_decision_ids": [],
            "risk_checks": [],
            "blocking_issues": [],
        }
    )
    case_id = _case_id(
        workflow_run_id=workflow_run_id,
        scenario_name="incomplete_review_state",
        target_id=proposal.portfolio_proposal_id,
    )
    adversarial_inputs = [
        _adversarial_input(
            case_id=case_id,
            input_kind="review_state_override",
            description="Promote a cloned proposal to approved without review decisions or risk checks.",
            target_type="portfolio_proposal",
            target_id=proposal.portfolio_proposal_id,
            related_artifact_ids=[proposal.portfolio_proposal_id],
            payload_summary="status=approved, review_decision_ids=[], risk_checks=[]",
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    ]
    violations = _as_list(
        check_review_bypass_detected(
            case_id=case_id,
            proposal=adversarial_proposal,
            review_decisions_by_id=workspace.review_decisions_by_id,
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    return _case_artifacts(
        case_id=case_id,
        name="Approved proposal with incomplete review state",
        scenario_name="incomplete_review_state",
        target_type="portfolio_proposal",
        target_id=proposal.portfolio_proposal_id,
        adversarial_inputs=adversarial_inputs,
        expected_guardrails=["review_bypass_detected"],
        violations=violations,
        weaknesses=["incomplete_review_state", "review_bypass_attempt"],
        notes=["The red-team case checks review-state consistency without mutating the persisted proposal."],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def _unsupported_causal_claim_case(
    *,
    workspace: LoadedRedTeamWorkspace,
    clock: Clock,
    workflow_run_id: str,
) -> ScenarioArtifacts | None:
    signal = _first(workspace.signals)
    if signal is None:
        return None
    adversarial_signal = signal.model_copy(
        update={
            "thesis_summary": (
                "This signal clearly proves the company will certainly outperform and is a must buy."
            ),
            "confidence": ConfidenceAssessment(confidence=0.2, uncertainty=0.85),
            "uncertainties": [],
        }
    )
    case_id = _case_id(
        workflow_run_id=workflow_run_id,
        scenario_name="unsupported_causal_claim",
        target_id=signal.signal_id,
    )
    adversarial_inputs = [
        _adversarial_input(
            case_id=case_id,
            input_kind="summary_language_override",
            description="Inject overstrong recommendation language into a low-confidence cloned signal summary.",
            target_type="signal",
            target_id=signal.signal_id,
            related_artifact_ids=[signal.signal_id],
            payload_summary=adversarial_signal.thesis_summary,
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    ]
    violations = _as_list(
        check_claim_strength_matches_support(
            case_id=case_id,
            target_type="signal",
            target_id=signal.signal_id,
            claim_text=adversarial_signal.thesis_summary,
            evidence_grade=None,
            contradiction_notes=[],
            confidence=adversarial_signal.confidence,
            uncertainties=adversarial_signal.uncertainties,
            related_artifact_ids=[signal.signal_id],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    return _case_artifacts(
        case_id=case_id,
        name="Unsupported causal certainty in signal summary",
        scenario_name="unsupported_causal_claim",
        target_type="signal",
        target_id=signal.signal_id,
        adversarial_inputs=adversarial_inputs,
        expected_guardrails=["claim_strength_matches_support"],
        violations=violations,
        weaknesses=["unsupported_causal_claim", "overstrong_language", "weak_confidence"],
        notes=["This scenario checks for confident recommendation language without sufficient support."],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def _malformed_portfolio_inputs_case(
    *,
    workspace: LoadedRedTeamWorkspace,
    clock: Clock,
    workflow_run_id: str,
) -> ScenarioArtifacts | None:
    proposal = _first(workspace.portfolio_proposals)
    if proposal is None:
        return None
    malformed_proposal = proposal.model_copy(
        update={
            "status": PortfolioProposalStatus.APPROVED,
            "position_ideas": [],
            "risk_checks": [],
            "review_decision_ids": [],
            "blocking_issues": [],
        }
    )
    case_id = _case_id(
        workflow_run_id=workflow_run_id,
        scenario_name="malformed_portfolio_inputs",
        target_id=proposal.portfolio_proposal_id,
    )
    adversarial_inputs = [
        _adversarial_input(
            case_id=case_id,
            input_kind="portfolio_payload_override",
            description="Strip a cloned approved proposal of positions, review decisions, and risk checks.",
            target_type="portfolio_proposal",
            target_id=proposal.portfolio_proposal_id,
            related_artifact_ids=[proposal.portfolio_proposal_id],
            payload_summary="position_ideas=[], risk_checks=[], review_decision_ids=[]",
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    ]
    violations = _as_list(
        check_review_bypass_detected(
            case_id=case_id,
            proposal=malformed_proposal,
            review_decisions_by_id=workspace.review_decisions_by_id,
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    return _case_artifacts(
        case_id=case_id,
        name="Malformed approved portfolio payload",
        scenario_name="malformed_portfolio_inputs",
        target_type="portfolio_proposal",
        target_id=proposal.portfolio_proposal_id,
        adversarial_inputs=adversarial_inputs,
        expected_guardrails=["review_bypass_detected"],
        violations=violations,
        weaknesses=["malformed_portfolio_inputs", "review_bypass_attempt"],
        notes=["The red-team suite treats structurally thin approved proposals as guardrail failures."],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def _weak_signal_lineage_case(
    *,
    workspace: LoadedRedTeamWorkspace,
    clock: Clock,
    workflow_run_id: str,
) -> ScenarioArtifacts | None:
    signal = _first(workspace.signals)
    if signal is None:
        return None
    weak_lineage_signal = signal.model_copy(
        update={
            "feature_ids": [],
            "lineage": signal.lineage.model_copy(
                update={
                    "feature_ids": [],
                    "feature_definition_ids": [],
                    "feature_value_ids": [],
                    "research_artifact_ids": [],
                    "supporting_evidence_link_ids": [],
                }
            ),
        }
    )
    case_id = _case_id(
        workflow_run_id=workflow_run_id,
        scenario_name="weak_signal_lineage",
        target_id=signal.signal_id,
    )
    adversarial_inputs = [
        _adversarial_input(
            case_id=case_id,
            input_kind="signal_lineage_override",
            description="Remove cloned signal lineage references to features, research artifacts, and evidence links.",
            target_type="signal",
            target_id=signal.signal_id,
            related_artifact_ids=[signal.signal_id],
            payload_summary="feature_ids=[], supporting_evidence_link_ids=[], research_artifact_ids=[]",
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    ]
    violations = _as_list(
        check_required_evidence_present(
            case_id=case_id,
            target_type="signal",
            target_id=signal.signal_id,
            evidence_link_ids=weak_lineage_signal.lineage.supporting_evidence_link_ids,
            supporting_artifact_ids=weak_lineage_signal.lineage.research_artifact_ids,
            related_artifact_ids=[signal.signal_id],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    return _case_artifacts(
        case_id=case_id,
        name="Weak or missing signal lineage",
        scenario_name="weak_signal_lineage",
        target_type="signal",
        target_id=signal.signal_id,
        adversarial_inputs=adversarial_inputs,
        expected_guardrails=["required_evidence_present"],
        violations=violations,
        weaknesses=["weak_signal_lineage", "missing_evidence"],
        notes=["This scenario simulates a downstream signal with detached lineage."],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def _empty_extraction_downstream_case(
    *,
    workspace: LoadedRedTeamWorkspace,
    clock: Clock,
    workflow_run_id: str,
) -> ScenarioArtifacts | None:
    signal = _first(workspace.signals)
    parsed_text = next(
        (item for item in workspace.parsed_texts if item.company_id == signal.company_id),
        None,
    ) if signal is not None else None
    if signal is None or parsed_text is None:
        return None
    empty_parsed_text = parsed_text.model_copy(update={"canonical_text": "", "body_text": ""})
    case_id = _case_id(
        workflow_run_id=workflow_run_id,
        scenario_name="empty_extraction_downstream",
        target_id=signal.signal_id,
    )
    matching_claims = [
        claim for claim in workspace.claims if claim.document_id == parsed_text.document_id
    ]
    adversarial_inputs = [
        _adversarial_input(
            case_id=case_id,
            input_kind="empty_extraction_override",
            description="Force the cloned parsed text to empty while a downstream signal still exists.",
            target_type="signal",
            target_id=signal.signal_id,
            related_artifact_ids=[signal.signal_id, parsed_text.parsed_document_text_id],
            payload_summary="canonical_text='', body_text='' with downstream signal unchanged",
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    ]
    violations = _as_list(
        check_non_empty_extraction_required_for_downstream(
            case_id=case_id,
            target_type="signal",
            target_id=signal.signal_id,
            parsed_text=empty_parsed_text,
            claim_count=len(matching_claims),
            downstream_artifact_ids=[signal.signal_id],
            related_artifact_ids=[signal.signal_id, parsed_text.parsed_document_text_id],
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    return _case_artifacts(
        case_id=case_id,
        name="Empty extraction artifact flowing downstream",
        scenario_name="empty_extraction_downstream",
        target_type="signal",
        target_id=signal.signal_id,
        adversarial_inputs=adversarial_inputs,
        expected_guardrails=["non_empty_extraction_required_for_downstream"],
        violations=violations,
        weaknesses=["empty_extraction_artifact", "downstream_flow_without_content"],
        notes=["The suite checks that blank extraction payloads do not look safe merely because downstream artifacts exist."],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def _paper_trade_missing_approval_state_case(
    *,
    workspace: LoadedRedTeamWorkspace,
    clock: Clock,
    workflow_run_id: str,
) -> ScenarioArtifacts | None:
    paper_trade = _first(workspace.paper_trades)
    if paper_trade is None:
        return None
    parent_proposal = workspace.portfolio_proposals_by_id.get(paper_trade.portfolio_proposal_id)
    adversarial_paper_trade = paper_trade.model_copy(
        update={
            "status": PaperTradeStatus.APPROVED,
            "approved_at": None,
            "approved_by": None,
            "review_decision_ids": [],
        }
    )
    adversarial_parent = (
        parent_proposal.model_copy(update={"status": PortfolioProposalStatus.PENDING_REVIEW})
        if parent_proposal is not None
        else None
    )
    case_id = _case_id(
        workflow_run_id=workflow_run_id,
        scenario_name="paper_trade_missing_approval_state",
        target_id=paper_trade.paper_trade_id,
    )
    related_artifact_ids = [paper_trade.paper_trade_id, paper_trade.portfolio_proposal_id]
    adversarial_inputs = [
        _adversarial_input(
            case_id=case_id,
            input_kind="paper_trade_approval_override",
            description="Approve a cloned paper trade while removing approval metadata and parent approval alignment.",
            target_type="paper_trade",
            target_id=paper_trade.paper_trade_id,
            related_artifact_ids=related_artifact_ids,
            payload_summary="status=approved, approved_at=null, approved_by=null, review_decision_ids=[]",
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    ]
    violations = _as_list(
        check_paper_trade_approval_state_complete(
            case_id=case_id,
            paper_trade=adversarial_paper_trade,
            parent_proposal=adversarial_parent,
            review_decisions_by_id=workspace.review_decisions_by_id,
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    return _case_artifacts(
        case_id=case_id,
        name="Paper trade missing approval state",
        scenario_name="paper_trade_missing_approval_state",
        target_type="paper_trade",
        target_id=paper_trade.paper_trade_id,
        adversarial_inputs=adversarial_inputs,
        expected_guardrails=["paper_trade_approval_state_complete"],
        violations=violations,
        weaknesses=["paper_trade_approval_gap", "review_bypass_attempt"],
        notes=["Paper-trade approval must remain explicit and linked to an approved parent proposal."],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def _evaluation_missing_references_case(
    *,
    workspace: LoadedRedTeamWorkspace,
    clock: Clock,
    workflow_run_id: str,
) -> ScenarioArtifacts | None:
    experiment = _first(workspace.experiments)
    if experiment is None:
        return None
    adversarial_experiment = experiment.model_copy(
        update={"experiment_config_id": "", "dataset_reference_ids": []}
    )
    case_id = _case_id(
        workflow_run_id=workflow_run_id,
        scenario_name="evaluation_missing_references",
        target_id=experiment.experiment_id,
    )
    adversarial_inputs = [
        _adversarial_input(
            case_id=case_id,
            input_kind="experiment_reference_override",
            description="Remove config and dataset references from a cloned recorded experiment.",
            target_type="experiment",
            target_id=experiment.experiment_id,
            related_artifact_ids=[experiment.experiment_id],
            payload_summary="experiment_config_id='', dataset_reference_ids=[]",
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    ]
    violations = _as_list(
        check_evaluation_references_complete(
            case_id=case_id,
            experiment=adversarial_experiment,
            clock=clock,
            workflow_run_id=workflow_run_id,
        )
    )
    return _case_artifacts(
        case_id=case_id,
        name="Experiment missing config or snapshot references",
        scenario_name="evaluation_missing_references",
        target_type="experiment",
        target_id=experiment.experiment_id,
        adversarial_inputs=adversarial_inputs,
        expected_guardrails=["evaluation_references_complete"],
        violations=violations,
        weaknesses=["missing_experiment_references"],
        notes=["Experiment recording is not trustworthy without config and dataset references."],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def check_required_provenance_present(
    *,
    case_id: str,
    artifact: object,
    target_type: str,
    target_id: str,
    related_artifact_ids: list[str],
    clock: Clock,
    workflow_run_id: str,
) -> GuardrailViolation | None:
    """Fail when an artifact lacks minimum usable provenance fields."""

    provenance = getattr(artifact, "provenance", None)
    missing: list[str] = []
    if provenance is None or getattr(provenance, "processing_time", None) is None:
        missing.append("processing_time")
    if provenance is None or not getattr(provenance, "transformation_name", None):
        missing.append("transformation_name")
    source_ids = getattr(provenance, "source_reference_ids", []) if provenance is not None else []
    upstream_ids = getattr(provenance, "upstream_artifact_ids", []) if provenance is not None else []
    if not source_ids and not upstream_ids:
        missing.append("source_or_upstream_linkage")
    if not missing:
        return None
    return _violation(
        case_id=case_id,
        guardrail_name="required_provenance_present",
        target_type=target_type,
        target_id=target_id,
        severity=Severity.HIGH,
        blocking=True,
        message="Artifact provenance is incomplete: missing " + ", ".join(missing) + ".",
        related_artifact_ids=related_artifact_ids,
        mitigations=[
            _mitigation(
                case_id=case_id,
                suffix="provenance",
                summary="Restore minimum provenance fields.",
                required_action="Require processing_time, transformation_name, and source or upstream artifact linkage before downstream trust progression.",
                owner_hint="upstream_workflow",
                blocking=True,
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        ],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def check_required_evidence_present(
    *,
    case_id: str,
    target_type: str,
    target_id: str,
    evidence_link_ids: list[str],
    supporting_artifact_ids: list[str],
    related_artifact_ids: list[str],
    clock: Clock,
    workflow_run_id: str,
) -> GuardrailViolation | None:
    """Fail when an artifact presents a claim or signal without support lineage."""

    if evidence_link_ids and supporting_artifact_ids:
        return None
    missing_parts = []
    if not evidence_link_ids:
        missing_parts.append("supporting_evidence_link_ids")
    if not supporting_artifact_ids:
        missing_parts.append("supporting_artifact_ids")
    return _violation(
        case_id=case_id,
        guardrail_name="required_evidence_present",
        target_type=target_type,
        target_id=target_id,
        severity=Severity.HIGH,
        blocking=True,
        message="Artifact lacks required support lineage: missing " + ", ".join(missing_parts) + ".",
        related_artifact_ids=related_artifact_ids,
        mitigations=[
            _mitigation(
                case_id=case_id,
                suffix="evidence",
                summary="Restore evidence and lineage links.",
                required_action="Require evidence-link IDs and upstream research artifact IDs before allowing downstream interpretation.",
                owner_hint="signal_generation",
                blocking=True,
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        ],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def check_claim_strength_matches_support(
    *,
    case_id: str,
    target_type: str,
    target_id: str,
    claim_text: str,
    evidence_grade: EvidenceGrade | None,
    contradiction_notes: list[str],
    confidence: ConfidenceAssessment | None,
    uncertainties: list[str],
    related_artifact_ids: list[str],
    clock: Clock,
    workflow_run_id: str,
) -> GuardrailViolation | None:
    """Fail when overstrong language appears without corresponding support quality."""

    strong_fragments = _strong_language_fragments(claim_text)
    if not strong_fragments:
        return None
    weak_support = evidence_grade in {None, EvidenceGrade.WEAK, EvidenceGrade.INSUFFICIENT}
    low_confidence = (
        confidence is None
        or confidence.confidence < 0.6
        or confidence.uncertainty > 0.4
    )
    if not any([weak_support, contradiction_notes, low_confidence, not uncertainties]):
        return None
    reasons = []
    if weak_support:
        reasons.append(f"evidence_grade={evidence_grade.value if evidence_grade is not None else 'missing'}")
    if contradiction_notes:
        reasons.append("contradictory evidence is present")
    if low_confidence:
        reasons.append("confidence is weak or missing")
    if not uncertainties:
        reasons.append("uncertainties are not surfaced")
    return _violation(
        case_id=case_id,
        guardrail_name="claim_strength_matches_support",
        target_type=target_type,
        target_id=target_id,
        severity=Severity.HIGH,
        blocking=True,
        message=(
            "Overstrong language "
            + ", ".join(f"`{fragment}`" for fragment in strong_fragments)
            + " is incompatible with the current support state: "
            + "; ".join(reasons)
            + "."
        ),
        related_artifact_ids=related_artifact_ids,
        mitigations=[
            _mitigation(
                case_id=case_id,
                suffix="language",
                summary="Downgrade claim wording or strengthen support.",
                required_action="Remove certainty or recommendation language until evidence grade, confidence, and uncertainty disclosure support it.",
                owner_hint="research_review",
                blocking=True,
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        ],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def check_review_bypass_detected(
    *,
    case_id: str,
    proposal: PortfolioProposal,
    review_decisions_by_id: dict[str, ReviewDecision],
    clock: Clock,
    workflow_run_id: str,
) -> GuardrailViolation | None:
    """Fail when an approved proposal can exist without explicit review coverage."""

    if proposal.status is not PortfolioProposalStatus.APPROVED:
        return None
    missing_review_ids = [
        decision_id
        for decision_id in proposal.review_decision_ids
        if decision_id not in review_decisions_by_id
    ]
    if proposal.review_decision_ids and not missing_review_ids and proposal.risk_checks and proposal.position_ideas:
        return None
    reasons = []
    if not proposal.review_decision_ids:
        reasons.append("review_decision_ids are empty")
    if missing_review_ids:
        reasons.append("review_decision_ids do not resolve")
    if not proposal.risk_checks:
        reasons.append("risk_checks are missing")
    if not proposal.position_ideas:
        reasons.append("position_ideas are missing")
    return _violation(
        case_id=case_id,
        guardrail_name="review_bypass_detected",
        target_type="portfolio_proposal",
        target_id=proposal.portfolio_proposal_id,
        severity=Severity.CRITICAL,
        blocking=True,
        message="Approved proposal appears to bypass review coverage: " + "; ".join(reasons) + ".",
        related_artifact_ids=[proposal.portfolio_proposal_id, *proposal.review_decision_ids],
        mitigations=[
            _mitigation(
                case_id=case_id,
                suffix="review",
                summary="Require explicit review coverage for approved proposals.",
                required_action="Block approval unless review decisions resolve, risk checks exist, and the proposal still contains concrete position ideas.",
                owner_hint="operator_review",
                blocking=True,
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        ],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def check_paper_trade_approval_state_complete(
    *,
    case_id: str,
    paper_trade: PaperTrade,
    parent_proposal: PortfolioProposal | None,
    review_decisions_by_id: dict[str, ReviewDecision],
    clock: Clock,
    workflow_run_id: str,
) -> GuardrailViolation | None:
    """Fail when a paper trade can appear approved without explicit review and parent alignment."""

    if paper_trade.status is not PaperTradeStatus.APPROVED:
        return None
    missing_review_ids = [
        decision_id
        for decision_id in paper_trade.review_decision_ids
        if decision_id not in review_decisions_by_id
    ]
    reasons = []
    if paper_trade.approved_at is None:
        reasons.append("approved_at is missing")
    if paper_trade.approved_by is None:
        reasons.append("approved_by is missing")
    if not paper_trade.review_decision_ids:
        reasons.append("review_decision_ids are empty")
    if missing_review_ids:
        reasons.append("review_decision_ids do not resolve")
    if parent_proposal is None:
        reasons.append("parent proposal is missing")
    elif parent_proposal.status is not PortfolioProposalStatus.APPROVED:
        reasons.append(f"parent proposal status is `{parent_proposal.status.value}`")
    if not reasons:
        return None
    return _violation(
        case_id=case_id,
        guardrail_name="paper_trade_approval_state_complete",
        target_type="paper_trade",
        target_id=paper_trade.paper_trade_id,
        severity=Severity.CRITICAL,
        blocking=True,
        message="Approved paper trade is missing explicit approval state: " + "; ".join(reasons) + ".",
        related_artifact_ids=[
            paper_trade.paper_trade_id,
            paper_trade.portfolio_proposal_id,
            *paper_trade.review_decision_ids,
        ],
        mitigations=[
            _mitigation(
                case_id=case_id,
                suffix="paper_trade",
                summary="Require complete paper-trade approval state.",
                required_action="Do not mark paper trades approved unless approval metadata, review decisions, and an approved parent proposal are all present.",
                owner_hint="paper_execution",
                blocking=True,
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        ],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def check_evaluation_references_complete(
    *,
    case_id: str,
    experiment: Experiment,
    clock: Clock,
    workflow_run_id: str,
) -> GuardrailViolation | None:
    """Fail when a recorded experiment loses its config or dataset references."""

    missing = []
    if not experiment.experiment_config_id:
        missing.append("experiment_config_id")
    if not experiment.dataset_reference_ids:
        missing.append("dataset_reference_ids")
    if not experiment.experiment_artifact_ids:
        missing.append("experiment_artifact_ids")
    if not experiment.experiment_metric_ids:
        missing.append("experiment_metric_ids")
    if not missing:
        return None
    return _violation(
        case_id=case_id,
        guardrail_name="evaluation_references_complete",
        target_type="experiment",
        target_id=experiment.experiment_id,
        severity=Severity.HIGH,
        blocking=True,
        message="Experiment recording is incomplete: missing " + ", ".join(missing) + ".",
        related_artifact_ids=[experiment.experiment_id],
        mitigations=[
            _mitigation(
                case_id=case_id,
                suffix="experiment",
                summary="Require complete experiment references.",
                required_action="Persist experiment config, dataset references, artifacts, and metrics together before treating evaluation outputs as reproducible.",
                owner_hint="experiment_registry",
                blocking=True,
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        ],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def check_non_empty_extraction_required_for_downstream(
    *,
    case_id: str,
    target_type: str,
    target_id: str,
    parsed_text: ParsedDocumentText,
    claim_count: int,
    downstream_artifact_ids: list[str],
    related_artifact_ids: list[str],
    clock: Clock,
    workflow_run_id: str,
) -> GuardrailViolation | None:
    """Fail when empty extraction outputs still appear to support downstream artifacts."""

    has_content = bool(parsed_text.canonical_text.strip())
    if has_content and claim_count > 0:
        return None
    return _violation(
        case_id=case_id,
        guardrail_name="non_empty_extraction_required_for_downstream",
        target_type=target_type,
        target_id=target_id,
        severity=Severity.HIGH,
        blocking=True,
        message=(
            "Downstream artifact exists while extraction content is empty or missing: "
            f"canonical_text_present={has_content}, claim_count={claim_count}."
        ),
        related_artifact_ids=[*related_artifact_ids, *downstream_artifact_ids],
        mitigations=[
            _mitigation(
                case_id=case_id,
                suffix="extraction",
                summary="Require non-empty extraction outputs before downstream promotion.",
                required_action="Block downstream research, feature, and signal use when parsed text or extracted claims are empty for the referenced document slice.",
                owner_hint="parsing",
                blocking=True,
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        ],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def check_timestamp_ordering_valid(
    *,
    case_id: str,
    target_type: str,
    target_id: str,
    earlier_name: str,
    earlier_value: datetime,
    later_name: str,
    later_value: datetime | None,
    related_artifact_ids: list[str],
    clock: Clock,
    workflow_run_id: str,
) -> GuardrailViolation | None:
    """Fail when a time window is ordered incorrectly."""

    if later_value is None or later_value >= earlier_value:
        return None
    return _violation(
        case_id=case_id,
        guardrail_name="timestamp_ordering_valid",
        target_type=target_type,
        target_id=target_id,
        severity=Severity.HIGH,
        blocking=True,
        message=(
            f"{later_name} must be greater than or equal to {earlier_name}; "
            f"observed {later_name}={later_value.isoformat()} and {earlier_name}={earlier_value.isoformat()}."
        ),
        related_artifact_ids=related_artifact_ids,
        mitigations=[
            _mitigation(
                case_id=case_id,
                suffix="timestamp",
                summary="Restore valid temporal ordering.",
                required_action="Reject or quarantine artifacts whose effective, expiry, or cutoff timestamps are temporally inconsistent.",
                owner_hint="temporal_validation",
                blocking=True,
                clock=clock,
                workflow_run_id=workflow_run_id,
            )
        ],
        clock=clock,
        workflow_run_id=workflow_run_id,
    )


def _case_artifacts(
    *,
    case_id: str,
    name: str,
    scenario_name: str,
    target_type: str,
    target_id: str,
    adversarial_inputs: list[AdversarialInput],
    expected_guardrails: list[str],
    violations: list[GuardrailViolation],
    weaknesses: list[str],
    notes: list[str],
    clock: Clock,
    workflow_run_id: str,
) -> ScenarioArtifacts:
    """Build one red-team case plus its derived finding."""

    status = _status_from_violations(violations)
    finding = SafetyFinding(
        safety_finding_id=make_canonical_id("sfnd", case_id, target_id),
        red_team_case_id=case_id,
        target_type=target_type,
        target_id=target_id,
        status=status,
        summary=(
            "Guardrails were triggered for the adversarial scenario."
            if violations
            else "No guardrail violation was recorded for the adversarial scenario."
        ),
        guardrail_violation_ids=[violation.guardrail_violation_id for violation in violations],
        exposed_weaknesses=weaknesses if violations else [],
        related_artifact_ids=[target_id, *[violation.guardrail_violation_id for violation in violations]],
        provenance=build_provenance(
            clock=clock,
            transformation_name="red_team_safety_finding",
            upstream_artifact_ids=[case_id, target_id, *[violation.guardrail_violation_id for violation in violations]],
            workflow_run_id=workflow_run_id,
            notes=notes,
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    red_team_case = RedTeamCase(
        red_team_case_id=case_id,
        name=name,
        scenario_name=scenario_name,
        target_type=target_type,
        target_id=target_id,
        adversarial_inputs=adversarial_inputs,
        expected_guardrails=expected_guardrails,
        outcome_status=status,
        guardrail_violation_ids=[violation.guardrail_violation_id for violation in violations],
        safety_finding_ids=[finding.safety_finding_id],
        executed_at=clock.now(),
        notes=[
            *notes,
            "Scenario executed against cloned in-memory artifacts only.",
        ],
        provenance=build_provenance(
            clock=clock,
            transformation_name="red_team_case",
            upstream_artifact_ids=[
                target_id,
                *[item.adversarial_input_id for item in adversarial_inputs],
                *[violation.guardrail_violation_id for violation in violations],
            ],
            workflow_run_id=workflow_run_id,
            notes=notes,
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )
    return ScenarioArtifacts(
        red_team_case=red_team_case,
        guardrail_violations=violations,
        safety_findings=[finding],
        notes=notes,
    )


def _adversarial_input(
    *,
    case_id: str,
    input_kind: str,
    description: str,
    target_type: str,
    target_id: str,
    related_artifact_ids: list[str],
    clock: Clock,
    workflow_run_id: str,
    fixture_path: str | None = None,
    payload_summary: str | None = None,
) -> AdversarialInput:
    """Build one typed adversarial input record."""

    return AdversarialInput(
        adversarial_input_id=make_canonical_id("ainput", case_id, input_kind, target_id),
        input_kind=input_kind,
        description=description,
        target_type=target_type,
        target_id=target_id,
        related_artifact_ids=related_artifact_ids,
        fixture_path=fixture_path,
        payload_summary=payload_summary,
        provenance=build_provenance(
            clock=clock,
            transformation_name="red_team_adversarial_input",
            upstream_artifact_ids=[target_id, *related_artifact_ids],
            workflow_run_id=workflow_run_id,
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )


def _mitigation(
    *,
    case_id: str,
    suffix: str,
    summary: str,
    required_action: str,
    owner_hint: str,
    blocking: bool,
    clock: Clock,
    workflow_run_id: str,
) -> RecommendedMitigation:
    """Build one concrete mitigation recommendation."""

    return RecommendedMitigation(
        recommended_mitigation_id=make_canonical_id("mitig", case_id, suffix),
        summary=summary,
        required_action=required_action,
        owner_hint=owner_hint,
        blocking=blocking,
        provenance=build_provenance(
            clock=clock,
            transformation_name="red_team_recommended_mitigation",
            upstream_artifact_ids=[case_id],
            workflow_run_id=workflow_run_id,
        ),
    )


def _violation(
    *,
    case_id: str,
    guardrail_name: str,
    target_type: str,
    target_id: str,
    severity: Severity,
    blocking: bool,
    message: str,
    related_artifact_ids: list[str],
    mitigations: list[RecommendedMitigation],
    clock: Clock,
    workflow_run_id: str,
) -> GuardrailViolation:
    """Build one typed guardrail violation."""

    return GuardrailViolation(
        guardrail_violation_id=make_canonical_id("gviol", case_id, guardrail_name, target_id),
        red_team_case_id=case_id,
        guardrail_name=guardrail_name,
        target_type=target_type,
        target_id=target_id,
        severity=severity,
        blocking=blocking,
        message=message,
        related_artifact_ids=related_artifact_ids,
        recommended_mitigations=mitigations,
        provenance=build_provenance(
            clock=clock,
            transformation_name="red_team_guardrail_violation",
            upstream_artifact_ids=[case_id, target_id, *related_artifact_ids],
            workflow_run_id=workflow_run_id,
        ),
        created_at=clock.now(),
        updated_at=clock.now(),
    )


def _case_id(*, workflow_run_id: str, scenario_name: str, target_id: str) -> str:
    return make_canonical_id("rtcase", workflow_run_id, scenario_name, target_id)


def _status_from_violations(violations: list[GuardrailViolation]) -> EvaluationStatus:
    """Derive a simple case status from recorded guardrail violations."""

    if any(violation.blocking for violation in violations):
        return EvaluationStatus.FAIL
    if violations:
        return EvaluationStatus.WARN
    return EvaluationStatus.PASS


def _strong_language_fragments(text: str) -> list[str]:
    """Return explicit overstrong language fragments present in a claim string."""

    lowered = text.lower()
    fragments = []
    for pattern in OVERSTRONG_LANGUAGE_PATTERNS:
        match = re.search(pattern, lowered)
        if match is not None:
            fragments.append(match.group(0))
    return fragments


def _first(items: list[TItem]) -> TItem | None:
    """Return the first item from a sequence when present."""

    return items[0] if items else None


def _as_list(item: TItem | None) -> list[TItem]:
    """Normalize an optional single item into a list."""

    return [] if item is None else [item]
