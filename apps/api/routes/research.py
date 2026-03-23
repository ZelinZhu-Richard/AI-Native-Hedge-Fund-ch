from __future__ import annotations

from fastapi import APIRouter

from apps.api.builders import build_response_envelope
from apps.api.contracts import HypothesisListPayload, ResearchBriefListPayload
from apps.api.state import api_clock, artifact_root, load_persisted_models
from libraries.schemas import APIResponseEnvelope, Hypothesis, ResearchBrief

router = APIRouter(tags=["research"])


@router.get("/research/hypotheses", response_model=APIResponseEnvelope[HypothesisListPayload])
@router.get(
    "/hypotheses",
    response_model=APIResponseEnvelope[HypothesisListPayload],
    include_in_schema=False,
)
def list_hypotheses() -> APIResponseEnvelope[HypothesisListPayload]:
    """Return persisted research hypotheses when they exist."""

    items = load_persisted_models(
        artifact_root() / "research" / "hypotheses",
        Hypothesis,
    )
    return build_response_envelope(
        data=HypothesisListPayload(items=items, total=len(items)),
        generated_at=api_clock.now(),
    )


@router.get("/research/briefs", response_model=APIResponseEnvelope[ResearchBriefListPayload])
def list_research_briefs() -> APIResponseEnvelope[ResearchBriefListPayload]:
    """Return persisted research briefs when they exist."""

    items = load_persisted_models(
        artifact_root() / "research" / "research_briefs",
        ResearchBrief,
    )
    return build_response_envelope(
        data=ResearchBriefListPayload(items=items, total=len(items)),
        generated_at=api_clock.now(),
    )
