from __future__ import annotations

from collections.abc import Iterable

from pydantic import Field

from libraries.core import build_provenance
from libraries.schemas import (
    ClaimType,
    ConfidenceAssessment,
    EvidenceLinkRole,
    EvidenceSpan,
    ExtractedClaim,
    GuidanceChange,
    GuidanceDirection,
    Hypothesis,
    HypothesisStatus,
    ResearchReviewStatus,
    ResearchStance,
    ResearchValidationStatus,
    StrictModel,
    SupportingEvidenceLink,
    ToneMarkerType,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id
from services.research_orchestrator.loaders import LoadedResearchArtifacts


class HypothesisGenerationResult(StrictModel):
    """Outcome of deterministic hypothesis generation."""

    hypothesis: Hypothesis | None = Field(
        default=None, description="Generated hypothesis when support is sufficient."
    )
    supporting_evidence_links: list[SupportingEvidenceLink] = Field(
        default_factory=list,
        description="Evidence links assembled before final hypothesis generation.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Observations about support sufficiency or generation choices.",
    )


def generate_hypothesis(
    *,
    inputs: LoadedResearchArtifacts,
    clock: Clock,
    workflow_run_id: str,
    agent_run_id: str,
) -> HypothesisGenerationResult:
    """Build a single concise hypothesis from deterministic research evidence."""

    supporting_evidence_links = _build_supporting_evidence_links(
        inputs=inputs,
        clock=clock,
        workflow_run_id=workflow_run_id,
        agent_run_id=agent_run_id,
    )
    unique_documents = {link.document_id for link in supporting_evidence_links}
    unique_artifacts = {
        link.extracted_artifact_id for link in supporting_evidence_links if link.extracted_artifact_id
    }
    notes: list[str] = []
    if len(supporting_evidence_links) < 2:
        notes.append("At least two supporting evidence links are required.")
    if len(unique_documents) < 2:
        notes.append("Hypothesis generation requires support across at least two documents.")
    if len(unique_artifacts) < 2:
        notes.append("Hypothesis generation requires at least two extracted artifacts.")
    if notes:
        return HypothesisGenerationResult(
            hypothesis=None,
            supporting_evidence_links=supporting_evidence_links,
            notes=notes,
        )

    now = clock.now()
    claims_by_type = {claim.claim_type for claim in inputs.claims}
    guidance_directions = {change.direction for change in inputs.guidance_changes}
    has_caution = any(
        marker.marker_type in {ToneMarkerType.CAUTION, ToneMarkerType.UNCERTAINTY}
        for marker in inputs.tone_markers
    )

    title = _build_title(claims_by_type=claims_by_type, guidance_directions=guidance_directions)
    thesis = _build_thesis(
        claims_by_type=claims_by_type,
        guidance_changes=inputs.guidance_changes,
    )
    assumptions = _build_assumptions(
        claims_by_type=claims_by_type,
        guidance_changes=inputs.guidance_changes,
    )
    uncertainties = _build_uncertainties(
        claims_by_type=claims_by_type,
        has_caution=has_caution,
    )
    invalidation_conditions = _build_invalidation_conditions(
        claims_by_type=claims_by_type,
        guidance_changes=inputs.guidance_changes,
    )
    validation_steps = _build_validation_steps(
        claims_by_type=claims_by_type,
        guidance_changes=inputs.guidance_changes,
    )
    hypothesis_id = make_canonical_id("hyp", inputs.company_id, title, thesis)
    confidence = ConfidenceAssessment(
        confidence=0.58 if len(unique_documents) >= 3 else 0.52,
        uncertainty=0.42 if len(unique_documents) >= 3 else 0.48,
        method="deterministic_research_workflow",
        rationale=(
            "Support comes from exact-span filing, transcript, and news artifacts, "
            "but remains incomplete and management-sourced."
        ),
    )
    source_reference_ids = sorted({link.source_reference_id for link in supporting_evidence_links})
    upstream_artifact_ids = [
        artifact_id
        for artifact_id in {
            link.extracted_artifact_id for link in supporting_evidence_links if link.extracted_artifact_id
        }
    ] + [link.evidence_span_id for link in supporting_evidence_links]
    hypothesis = Hypothesis(
        hypothesis_id=hypothesis_id,
        company_id=inputs.company_id,
        title=title,
        thesis=thesis,
        stance=ResearchStance.POSITIVE,
        status=HypothesisStatus.UNDER_REVIEW,
        review_status=ResearchReviewStatus.PENDING_HUMAN_REVIEW,
        validation_status=ResearchValidationStatus.UNVALIDATED,
        time_horizon="next_2_4_quarters",
        catalyst="Subsequent earnings updates and pilot deployment progress.",
        invalidation_conditions=invalidation_conditions,
        supporting_evidence_links=supporting_evidence_links,
        assumptions=assumptions,
        uncertainties=uncertainties,
        validation_steps=validation_steps,
        evidence_assessment_id=None,
        confidence=confidence,
        provenance=build_provenance(
            clock=clock,
            transformation_name="deterministic_hypothesis_generation",
            source_reference_ids=source_reference_ids,
            upstream_artifact_ids=upstream_artifact_ids,
            workflow_run_id=workflow_run_id,
            agent_run_id=agent_run_id,
        ),
        created_at=now,
        updated_at=now,
    )
    return HypothesisGenerationResult(
        hypothesis=hypothesis,
        supporting_evidence_links=supporting_evidence_links,
        notes=[],
    )


def _build_supporting_evidence_links(
    *,
    inputs: LoadedResearchArtifacts,
    clock: Clock,
    workflow_run_id: str,
    agent_run_id: str,
) -> list[SupportingEvidenceLink]:
    """Assemble exact evidence links from supporting claims and guidance artifacts."""

    evidence_spans = {span.evidence_span_id: span for span in inputs.evidence_spans}
    links: list[SupportingEvidenceLink] = []
    for artifact in sorted(inputs.claims, key=_claim_priority):
        link = _build_link(
            document_id=artifact.document_id,
            source_reference_id=artifact.source_reference_id,
            evidence_span_ids=artifact.evidence_span_ids,
            extracted_artifact_id=artifact.extracted_claim_id,
            role=EvidenceLinkRole.SUPPORT,
            note=_support_note_for_claim_type(artifact.claim_type),
            evidence_spans=evidence_spans,
            clock=clock,
            workflow_run_id=workflow_run_id,
            agent_run_id=agent_run_id,
        )
        if link is not None:
            links.append(link)
    for change in inputs.guidance_changes:
        link = _build_link(
            document_id=change.document_id,
            source_reference_id=change.source_reference_id,
            evidence_span_ids=change.evidence_span_ids,
            extracted_artifact_id=change.guidance_change_id,
            role=EvidenceLinkRole.SUPPORT,
            note=f"Explicit {change.direction.value} guidance statement on {change.topic}.",
            evidence_spans=evidence_spans,
            clock=clock,
            workflow_run_id=workflow_run_id,
            agent_run_id=agent_run_id,
        )
        if link is not None:
            links.append(link)
    deduped_links: list[SupportingEvidenceLink] = []
    seen_span_ids: set[str] = set()
    for link in links:
        if link.evidence_span_id in seen_span_ids:
            continue
        deduped_links.append(link)
        seen_span_ids.add(link.evidence_span_id)
    return deduped_links


def _build_link(
    *,
    document_id: str,
    source_reference_id: str,
    evidence_span_ids: Iterable[str],
    extracted_artifact_id: str | None,
    role: EvidenceLinkRole,
    note: str,
    evidence_spans: dict[str, EvidenceSpan],
    clock: Clock,
    workflow_run_id: str,
    agent_run_id: str,
) -> SupportingEvidenceLink | None:
    """Create one exact evidence link from the first resolved evidence span."""

    span_id = next(iter(evidence_span_ids), None)
    if span_id is None:
        return None
    span = evidence_spans.get(span_id)
    if span is None:
        return None
    now = clock.now()
    return SupportingEvidenceLink(
        supporting_evidence_link_id=make_canonical_id(
            "sel",
            span_id,
            role.value,
            extracted_artifact_id or "no_artifact",
        ),
        source_reference_id=source_reference_id,
        document_id=document_id,
        evidence_span_id=span_id,
        extracted_artifact_id=extracted_artifact_id,
        role=role,
        quote=span.text,
        note=note,
        provenance=build_provenance(
            clock=clock,
            transformation_name="research_support_link_assembly",
            source_reference_ids=[source_reference_id],
            upstream_artifact_ids=[value for value in [span_id, extracted_artifact_id] if value],
            workflow_run_id=workflow_run_id,
            agent_run_id=agent_run_id,
        ),
        created_at=now,
        updated_at=now,
    )


def _claim_priority(claim: ExtractedClaim) -> tuple[int, str]:
    """Sort claims so the most thesis-relevant statements appear first."""
    priority = {
        ClaimType.FINANCIAL_RESULT: 0,
        ClaimType.OPERATIONAL_UPDATE: 1,
        ClaimType.OUTLOOK_STATEMENT: 2,
        ClaimType.PRODUCT_UPDATE: 3,
        ClaimType.TIMELINE_STATEMENT: 4,
    }[claim.claim_type]
    return (priority, claim.statement)


def _support_note_for_claim_type(claim_type: ClaimType) -> str:
    """Describe why a claim is included as direct support."""

    return {
        ClaimType.FINANCIAL_RESULT: "Direct operating result statement.",
        ClaimType.OPERATIONAL_UPDATE: "Direct operating execution statement.",
        ClaimType.OUTLOOK_STATEMENT: "Direct outlook statement.",
        ClaimType.PRODUCT_UPDATE: "Direct product expansion statement.",
        ClaimType.TIMELINE_STATEMENT: "Direct timeline statement tied to expected rollout.",
    }[claim_type]


def _build_title(
    *,
    claims_by_type: set[ClaimType],
    guidance_directions: set[GuidanceDirection],
) -> str:
    """Generate a concise deterministic title."""

    if ClaimType.FINANCIAL_RESULT in claims_by_type and guidance_directions:
        return "Execution Strength With Maintained Outlook"
    if ClaimType.PRODUCT_UPDATE in claims_by_type and ClaimType.TIMELINE_STATEMENT in claims_by_type:
        return "Product Expansion With Near-Term Deployment Path"
    return "Evidence-Backed Operating Thesis"


def _build_thesis(
    *,
    claims_by_type: set[ClaimType],
    guidance_changes: list[GuidanceChange],
) -> str:
    """Generate the concise thesis statement from the available evidence types."""

    segments = ["Current evidence suggests"]
    if {
        ClaimType.FINANCIAL_RESULT,
        ClaimType.OPERATIONAL_UPDATE,
    } <= claims_by_type:
        segments.append("near-term execution remains on plan")
    elif ClaimType.FINANCIAL_RESULT in claims_by_type:
        segments.append("reported operating momentum is holding")
    elif ClaimType.PRODUCT_UPDATE in claims_by_type:
        segments.append("product expansion could support future adoption")
    else:
        segments.append("the company retains a reviewable operating setup")
    if guidance_changes:
        segments.append("with management maintaining full-year outlook")
    if ClaimType.PRODUCT_UPDATE in claims_by_type:
        segments.append("and product expansion adding a secondary support")
    return " ".join(segments) + "."


def _build_assumptions(
    *,
    claims_by_type: set[ClaimType],
    guidance_changes: list[GuidanceChange],
) -> list[str]:
    """Make cross-document and forward-looking leaps explicit."""

    assumptions = ["Management commentary continues to reflect underlying operating conditions."]
    if {
        ClaimType.FINANCIAL_RESULT,
        ClaimType.OPERATIONAL_UPDATE,
    } & claims_by_type:
        assumptions.append(
            "Backlog and demand commentary convert into realized revenue and margin follow-through."
        )
    if ClaimType.PRODUCT_UPDATE in claims_by_type or ClaimType.TIMELINE_STATEMENT in claims_by_type:
        assumptions.append("Pilot deployments convert into broader customer adoption.")
    if guidance_changes:
        assumptions.append("Ongoing investment spending does not derail the maintained outlook.")
    return assumptions


def _build_uncertainties(*, claims_by_type: set[ClaimType], has_caution: bool) -> list[str]:
    """Surface current uncertainty explicitly."""

    uncertainties = ["Current support is concentrated in company-controlled disclosures."]
    if ClaimType.PRODUCT_UPDATE in claims_by_type:
        uncertainties.append("Commercial adoption of the new product remains unproven.")
    if has_caution:
        uncertainties.append("Current commentary still contains caution around ongoing investment.")
    else:
        uncertainties.append("Independent validation of demand durability is still limited.")
    return uncertainties


def _build_invalidation_conditions(
    *,
    claims_by_type: set[ClaimType],
    guidance_changes: list[GuidanceChange],
) -> list[str]:
    """Define simple observable invalidation points."""

    invalidators = []
    if guidance_changes:
        invalidators.append("Management lowers or withdraws full-year outlook.")
    if ClaimType.OPERATIONAL_UPDATE in claims_by_type:
        invalidators.append("Backlog conversion or industrial demand weakens in later disclosures.")
    if ClaimType.PRODUCT_UPDATE in claims_by_type:
        invalidators.append("Pilot deployments slip or fail to expand beyond existing customers.")
    return invalidators or ["Later disclosures fail to confirm the current operating narrative."]


def _build_validation_steps(
    *,
    claims_by_type: set[ClaimType],
    guidance_changes: list[GuidanceChange],
) -> list[str]:
    """Define concrete next validation checks for a researcher."""

    steps = ["Review the next company update for confirmation of current operating commentary."]
    if guidance_changes:
        steps.append("Check whether management maintains, raises, or lowers outlook next quarter.")
    if ClaimType.OPERATIONAL_UPDATE in claims_by_type:
        steps.append("Track whether backlog commentary converts into reported revenue and margins.")
    if ClaimType.PRODUCT_UPDATE in claims_by_type or ClaimType.TIMELINE_STATEMENT in claims_by_type:
        steps.append("Track whether pilot deployments move into broader customer rollout.")
    return steps
