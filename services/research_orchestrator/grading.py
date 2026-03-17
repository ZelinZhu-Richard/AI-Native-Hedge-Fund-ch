from __future__ import annotations

from libraries.core import build_provenance
from libraries.schemas import (
    ClaimType,
    ConfidenceAssessment,
    EvidenceAssessment,
    EvidenceGrade,
    Hypothesis,
    ResearchReviewStatus,
    SupportingEvidenceLink,
    ToneMarkerType,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id
from services.research_orchestrator.loaders import LoadedResearchArtifacts


def build_evidence_assessment(
    *,
    company_id: str,
    hypothesis: Hypothesis | None,
    supporting_evidence_links: list[SupportingEvidenceLink],
    generation_notes: list[str],
    inputs: LoadedResearchArtifacts,
    clock: Clock,
    workflow_run_id: str,
    agent_run_id: str,
) -> EvidenceAssessment:
    """Grade the current support level for a research thesis."""

    unique_documents = {link.document_id for link in supporting_evidence_links}
    claim_types = {claim.claim_type for claim in inputs.claims}
    has_direct_financial_or_outlook = bool(
        {ClaimType.FINANCIAL_RESULT, ClaimType.OUTLOOK_STATEMENT} & claim_types
        or inputs.guidance_changes
    )
    if len(supporting_evidence_links) >= 3 and len(unique_documents) >= 2 and has_direct_financial_or_outlook:
        grade = EvidenceGrade.STRONG
    elif len(supporting_evidence_links) >= 2 and len(unique_documents) >= 2:
        grade = EvidenceGrade.MODERATE
    elif supporting_evidence_links:
        grade = EvidenceGrade.WEAK
    else:
        grade = EvidenceGrade.INSUFFICIENT

    key_gaps = [
        "Evidence remains concentrated in company-controlled disclosures.",
        "Independent demand or adoption validation is not yet available.",
    ]
    if ClaimType.PRODUCT_UPDATE in claim_types:
        key_gaps.append("The new product launch is not yet supported by observed customer uptake.")
    contradiction_notes = [risk_factor.statement for risk_factor in inputs.risk_factors[:2]]
    contradiction_notes.extend(
        f"Tone marker suggests {marker.marker_type.value}: {marker.statement}"
        for marker in inputs.tone_markers
        if marker.marker_type in {ToneMarkerType.CAUTION, ToneMarkerType.UNCERTAINTY}
    )
    contradiction_notes.extend(generation_notes)

    support_summary = (
        f"Support currently rests on {len(supporting_evidence_links)} exact-span links "
        f"across {len(unique_documents)} document(s), including direct claim or outlook evidence."
        if supporting_evidence_links
        else "Current evidence is too thin to support a reviewable thesis."
    )
    confidence = ConfidenceAssessment(
        confidence={
            EvidenceGrade.STRONG: 0.62,
            EvidenceGrade.MODERATE: 0.55,
            EvidenceGrade.WEAK: 0.44,
            EvidenceGrade.INSUFFICIENT: 0.28,
        }[grade],
        uncertainty={
            EvidenceGrade.STRONG: 0.38,
            EvidenceGrade.MODERATE: 0.45,
            EvidenceGrade.WEAK: 0.56,
            EvidenceGrade.INSUFFICIENT: 0.72,
        }[grade],
        method="deterministic_research_workflow",
        rationale="Evidence grade is based on support breadth, document diversity, and explicit gaps.",
    )
    now = clock.now()
    source_reference_ids = sorted({link.source_reference_id for link in supporting_evidence_links})
    upstream_artifact_ids = sorted(
        {
            value
            for link in supporting_evidence_links
            for value in [link.supporting_evidence_link_id, link.extracted_artifact_id, link.evidence_span_id]
            if value is not None
        }
    )
    support_key = hypothesis.hypothesis_id if hypothesis is not None else "insufficient"
    return EvidenceAssessment(
        evidence_assessment_id=make_canonical_id("eass", company_id, support_key, grade.value),
        company_id=company_id,
        hypothesis_id=hypothesis.hypothesis_id if hypothesis is not None else None,
        grade=grade,
        supporting_evidence_link_ids=[
            link.supporting_evidence_link_id for link in supporting_evidence_links
        ],
        support_summary=support_summary,
        key_gaps=key_gaps,
        contradiction_notes=contradiction_notes,
        review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
        confidence=confidence,
        provenance=build_provenance(
            clock=clock,
            transformation_name="deterministic_evidence_grading",
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=upstream_artifact_ids,
            workflow_run_id=workflow_run_id,
            agent_run_id=agent_run_id,
        ),
        created_at=now,
        updated_at=now,
    )
