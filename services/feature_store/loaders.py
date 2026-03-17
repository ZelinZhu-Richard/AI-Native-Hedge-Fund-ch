from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import Field

from libraries.schemas import (
    CounterHypothesis,
    EvidenceAssessment,
    ExtractedRiskFactor,
    GuidanceChange,
    Hypothesis,
    ResearchBrief,
    StrictModel,
    ToneMarker,
)

T = TypeVar("T", bound=StrictModel)


class LoadedFeatureMappingInputs(StrictModel):
    """Typed bundle of research and parsing artifacts used for Day 5 feature mapping."""

    company_id: str = Field(description="Covered company identifier.")
    hypothesis: Hypothesis | None = Field(
        default=None, description="Primary hypothesis when research support was sufficient."
    )
    counter_hypothesis: CounterHypothesis | None = Field(
        default=None, description="Primary critique artifact when available."
    )
    evidence_assessment: EvidenceAssessment = Field(
        description="Evidence assessment for the current research slice."
    )
    research_brief: ResearchBrief | None = Field(
        default=None, description="Memo-ready research brief when a full research workflow completed."
    )
    guidance_changes: list[GuidanceChange] = Field(
        default_factory=list,
        description="Guidance artifacts reloaded from parsing output for deterministic feature mapping.",
    )
    risk_factors: list[ExtractedRiskFactor] = Field(
        default_factory=list,
        description="Risk-factor artifacts reloaded from parsing output for deterministic feature mapping.",
    )
    tone_markers: list[ToneMarker] = Field(
        default_factory=list,
        description="Tone-marker artifacts reloaded from parsing output for deterministic feature mapping.",
    )


def load_feature_mapping_inputs(
    *,
    research_root: Path,
    parsing_root: Path | None,
    company_id: str | None = None,
) -> LoadedFeatureMappingInputs:
    """Load the best available research slice and optional parsing context for one company."""

    research_briefs = _load_models(research_root / "research_briefs", ResearchBrief)
    evidence_assessments = _load_models(
        research_root / "evidence_assessments", EvidenceAssessment
    )
    hypotheses = _load_models(research_root / "hypotheses", Hypothesis)
    counter_hypotheses = _load_models(
        research_root / "counter_hypotheses", CounterHypothesis
    )

    resolved_company_id = _resolve_company_id(
        company_id=company_id,
        research_briefs=research_briefs,
        evidence_assessments=evidence_assessments,
    )

    company_briefs = [
        brief for brief in research_briefs if brief.company_id == resolved_company_id
    ]
    company_assessments = [
        assessment
        for assessment in evidence_assessments
        if assessment.company_id == resolved_company_id
    ]
    if not company_assessments:
        raise ValueError(
            f"Feature mapping requires at least one evidence assessment for `{resolved_company_id}`."
        )

    latest_brief = max(company_briefs, key=lambda brief: brief.created_at) if company_briefs else None
    if latest_brief is not None:
        hypothesis = _find_by_id(
            hypotheses, "hypothesis_id", latest_brief.hypothesis_id, resolved_company_id
        )
        counter_hypothesis = _find_by_id(
            counter_hypotheses,
            "counter_hypothesis_id",
            latest_brief.counter_hypothesis_id,
            resolved_company_id,
        )
        evidence_assessment = _find_by_id(
            company_assessments,
            "evidence_assessment_id",
            latest_brief.evidence_assessment_id,
            resolved_company_id,
        )
    else:
        hypothesis = None
        counter_hypothesis = None
        evidence_assessment = max(company_assessments, key=lambda assessment: assessment.created_at)

    guidance_changes: list[GuidanceChange] = []
    risk_factors: list[ExtractedRiskFactor] = []
    tone_markers: list[ToneMarker] = []
    if parsing_root is not None and parsing_root.exists():
        guidance_changes = [
            change
            for change in _load_models(parsing_root / "guidance_changes", GuidanceChange)
            if change.company_id == resolved_company_id
        ]
        risk_factors = [
            risk_factor
            for risk_factor in _load_models(parsing_root / "risk_factors", ExtractedRiskFactor)
            if risk_factor.company_id == resolved_company_id
        ]
        tone_markers = [
            tone_marker
            for tone_marker in _load_models(parsing_root / "tone_markers", ToneMarker)
            if tone_marker.company_id == resolved_company_id
        ]

    return LoadedFeatureMappingInputs(
        company_id=resolved_company_id,
        hypothesis=hypothesis,
        counter_hypothesis=counter_hypothesis,
        evidence_assessment=evidence_assessment,
        research_brief=latest_brief,
        guidance_changes=guidance_changes,
        risk_factors=risk_factors,
        tone_markers=tone_markers,
    )


def _resolve_company_id(
    *,
    company_id: str | None,
    research_briefs: list[ResearchBrief],
    evidence_assessments: list[EvidenceAssessment],
) -> str:
    """Resolve a single company identifier from persisted research artifacts."""

    available_company_ids = sorted(
        {
            *(brief.company_id for brief in research_briefs if brief.company_id),
            *(assessment.company_id for assessment in evidence_assessments if assessment.company_id),
        }
    )
    if company_id is not None:
        if company_id not in available_company_ids:
            raise ValueError(f"Company `{company_id}` was not found under the research root.")
        return company_id
    if len(available_company_ids) != 1:
        raise ValueError(
            "Feature mapping requires an explicit company_id when research artifacts contain "
            "zero or multiple companies."
        )
    return available_company_ids[0]


def _find_by_id(
    artifacts: list[T],
    attribute: str,
    identifier: str,
    company_id: str,
) -> T:
    """Find one artifact by identifier and raise a clear error if it is missing."""

    for artifact in artifacts:
        if getattr(artifact, attribute) == identifier:
            return artifact
    raise ValueError(
        f"Required artifact `{identifier}` referenced by company `{company_id}` was not found."
    )


def _load_models(directory: Path, model_cls: type[T]) -> list[T]:
    """Load JSON models from a category directory."""

    if not directory.exists():
        return []
    return [
        model_cls.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]
