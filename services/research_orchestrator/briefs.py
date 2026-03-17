from __future__ import annotations

from libraries.core import build_provenance
from libraries.schemas import (
    Company,
    CounterHypothesis,
    EvidenceAssessment,
    Hypothesis,
    ResearchBrief,
    ResearchReviewStatus,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id
from services.research_orchestrator.loaders import LoadedResearchArtifacts


def build_research_brief(
    *,
    hypothesis: Hypothesis,
    counter_hypothesis: CounterHypothesis,
    evidence_assessment: EvidenceAssessment,
    inputs: LoadedResearchArtifacts,
    clock: Clock,
    workflow_run_id: str,
    agent_run_id: str,
) -> ResearchBrief:
    """Build a memo-ready structured research brief from hypothesis and critique artifacts."""

    now = clock.now()
    company_name = _company_name(inputs.company)
    document_labels = ", ".join(document.kind.value for document in inputs.documents) or "parsed evidence"
    key_counterarguments = list(
        dict.fromkeys(
            [
                *counter_hypothesis.missing_evidence[:2],
                *counter_hypothesis.causal_gaps[:1],
            ]
        )
    )
    source_reference_ids = sorted(
        {
            *hypothesis.provenance.source_reference_ids,
            *counter_hypothesis.provenance.source_reference_ids,
            *evidence_assessment.provenance.source_reference_ids,
        }
    )
    upstream_artifact_ids = [
        hypothesis.hypothesis_id,
        counter_hypothesis.counter_hypothesis_id,
        evidence_assessment.evidence_assessment_id,
        *[link.supporting_evidence_link_id for link in hypothesis.supporting_evidence_links],
    ]
    return ResearchBrief(
        research_brief_id=make_canonical_id(
            "rbrief",
            hypothesis.hypothesis_id,
            counter_hypothesis.counter_hypothesis_id,
        ),
        company_id=inputs.company_id,
        title=f"{company_name}: {hypothesis.title}",
        context_summary=(
            f"{company_name} review built from {document_labels} covering the current fixture "
            "evidence set and exact-span extracted artifacts."
        ),
        core_hypothesis=hypothesis.thesis,
        counter_hypothesis_summary=counter_hypothesis.thesis,
        hypothesis_id=hypothesis.hypothesis_id,
        counter_hypothesis_id=counter_hypothesis.counter_hypothesis_id,
        evidence_assessment_id=evidence_assessment.evidence_assessment_id,
        supporting_evidence_links=hypothesis.supporting_evidence_links,
        key_counterarguments=key_counterarguments,
        confidence=hypothesis.confidence,
        uncertainty_summary="; ".join(hypothesis.uncertainties),
        review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
        next_validation_steps=hypothesis.validation_steps,
        provenance=build_provenance(
            clock=clock,
            transformation_name="research_brief_builder",
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=upstream_artifact_ids,
            workflow_run_id=workflow_run_id,
            agent_run_id=agent_run_id,
        ),
        created_at=now,
        updated_at=now,
    )


def _company_name(company: Company | None) -> str:
    """Return a human-readable company label for the brief."""

    if company is not None:
        return company.legal_name
    return "Covered company"
