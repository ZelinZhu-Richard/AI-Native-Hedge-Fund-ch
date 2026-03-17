from __future__ import annotations

from libraries.core import build_provenance
from libraries.schemas import (
    ConfidenceAssessment,
    CounterHypothesis,
    CritiqueKind,
    EvidenceAssessment,
    EvidenceLinkRole,
    EvidenceSpan,
    Hypothesis,
    ResearchReviewStatus,
    ResearchValidationStatus,
    SupportingEvidenceLink,
    ToneMarkerType,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id
from services.research_orchestrator.loaders import LoadedResearchArtifacts


def generate_counter_hypothesis(
    *,
    hypothesis: Hypothesis,
    evidence_assessment: EvidenceAssessment,
    inputs: LoadedResearchArtifacts,
    clock: Clock,
    workflow_run_id: str,
    agent_run_id: str,
) -> CounterHypothesis:
    """Generate a deterministic critique for a single hypothesis."""

    critique_links = _build_critique_links(
        inputs=inputs,
        clock=clock,
        workflow_run_id=workflow_run_id,
        agent_run_id=agent_run_id,
    )
    critique_kinds = {
        CritiqueKind.MISSING_EVIDENCE,
        CritiqueKind.ASSUMPTION_RISK,
        CritiqueKind.CAUSAL_GAP,
    }
    if critique_links:
        critique_kinds.add(CritiqueKind.CONTRADICTORY_EVIDENCE)

    challenged_assumptions = list(hypothesis.assumptions[:2])
    if not challenged_assumptions:
        challenged_assumptions = ["The current evidence base is assumed to represent durable demand."]
    missing_evidence = [
        "Independent evidence that backlog and demand commentary convert into reported outcomes.",
        "Observed customer adoption beyond planned pilots or launch announcements.",
    ]
    causal_gaps = [
        "Reported strength does not yet prove that current demand durability will persist.",
        "A new product launch does not by itself prove commercial monetization.",
    ]
    unresolved_questions = [
        "Will continued platform migration and channel spending offset margin gains?",
        "Will pilot deployments convert into broader customer rollout on the expected timeline?",
    ]
    thesis = (
        "The thesis may overstate durability because current support is still management-sourced, "
        "ongoing investment could pressure margins, and product adoption remains unproven beyond "
        "planned pilots."
    )
    now = clock.now()
    source_reference_ids = sorted(
        {
            *[link.source_reference_id for link in critique_links],
            *evidence_assessment.provenance.source_reference_ids,
        }
    )
    upstream_artifact_ids = sorted(
        {
            hypothesis.hypothesis_id,
            evidence_assessment.evidence_assessment_id,
            *[
                value
                for link in critique_links
                for value in [
                    link.supporting_evidence_link_id,
                    link.extracted_artifact_id,
                    link.evidence_span_id,
                ]
                if value is not None
            ],
        }
    )
    return CounterHypothesis(
        counter_hypothesis_id=make_canonical_id(
            "chyp",
            hypothesis.hypothesis_id,
            thesis,
        ),
        hypothesis_id=hypothesis.hypothesis_id,
        title="Durability And Adoption Are Still Unproven",
        thesis=thesis,
        critique_kinds=sorted(critique_kinds, key=lambda kind: kind.value),
        supporting_evidence_links=critique_links,
        challenged_assumptions=challenged_assumptions,
        missing_evidence=missing_evidence,
        causal_gaps=causal_gaps,
        unresolved_questions=unresolved_questions,
        review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
        validation_status=ResearchValidationStatus.UNVALIDATED,
        confidence=ConfidenceAssessment(
            confidence=0.51,
            uncertainty=0.49,
            method="deterministic_research_workflow",
            rationale="The critique is grounded in explicit gaps and cautionary evidence, but not all downside mechanisms are directly observed.",
        ),
        provenance=build_provenance(
            clock=clock,
            transformation_name="deterministic_thesis_critique",
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=upstream_artifact_ids,
            workflow_run_id=workflow_run_id,
            agent_run_id=agent_run_id,
        ),
        created_at=now,
        updated_at=now,
    )


def _build_critique_links(
    *,
    inputs: LoadedResearchArtifacts,
    clock: Clock,
    workflow_run_id: str,
    agent_run_id: str,
) -> list[SupportingEvidenceLink]:
    """Build critique links from explicit risk and caution artifacts."""

    evidence_spans = {span.evidence_span_id: span for span in inputs.evidence_spans}
    links: list[SupportingEvidenceLink] = []
    for risk_factor in inputs.risk_factors:
        link = _build_link(
            document_id=risk_factor.document_id,
            source_reference_id=risk_factor.source_reference_id,
            evidence_span_ids=risk_factor.evidence_span_ids,
            extracted_artifact_id=risk_factor.risk_factor_id,
            role=EvidenceLinkRole.CONTRADICT,
            note=f"Explicit {risk_factor.risk_category.value} risk factor.",
            evidence_spans=evidence_spans,
            clock=clock,
            workflow_run_id=workflow_run_id,
            agent_run_id=agent_run_id,
        )
        if link is not None:
            links.append(link)
    for marker in inputs.tone_markers:
        if marker.marker_type not in {ToneMarkerType.CAUTION, ToneMarkerType.UNCERTAINTY}:
            continue
        link = _build_link(
            document_id=marker.document_id,
            source_reference_id=marker.source_reference_id,
            evidence_span_ids=marker.evidence_span_ids,
            extracted_artifact_id=marker.tone_marker_id,
            role=EvidenceLinkRole.CONTEXT,
            note=f"Tone marker indicates {marker.marker_type.value}.",
            evidence_spans=evidence_spans,
            clock=clock,
            workflow_run_id=workflow_run_id,
            agent_run_id=agent_run_id,
        )
        if link is not None:
            links.append(link)
    return links


def _build_link(
    *,
    document_id: str,
    source_reference_id: str,
    evidence_span_ids: list[str],
    extracted_artifact_id: str | None,
    role: EvidenceLinkRole,
    note: str,
    evidence_spans: dict[str, EvidenceSpan],
    clock: Clock,
    workflow_run_id: str,
    agent_run_id: str,
) -> SupportingEvidenceLink | None:
    """Create one critique evidence link from the first available span."""

    if not evidence_span_ids:
        return None
    span = evidence_spans.get(evidence_span_ids[0])
    if span is None:
        return None
    now = clock.now()
    return SupportingEvidenceLink(
        supporting_evidence_link_id=make_canonical_id(
            "sel",
            evidence_span_ids[0],
            role.value,
            extracted_artifact_id or "no_artifact",
        ),
        source_reference_id=source_reference_id,
        document_id=document_id,
        evidence_span_id=evidence_span_ids[0],
        extracted_artifact_id=extracted_artifact_id,
        role=role,
        quote=span.text,
        note=note,
        provenance=build_provenance(
            clock=clock,
            transformation_name="research_critique_link_assembly",
            source_reference_ids=[source_reference_id],
            upstream_artifact_ids=[
                value for value in [evidence_span_ids[0], extracted_artifact_id] if value
            ],
            workflow_run_id=workflow_run_id,
            agent_run_id=agent_run_id,
        ),
        created_at=now,
        updated_at=now,
    )
