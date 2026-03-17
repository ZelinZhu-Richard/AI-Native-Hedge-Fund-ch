from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import Field

from libraries.schemas import (
    EvidenceAssessment,
    Feature,
    Hypothesis,
    ResearchBrief,
    StrictModel,
)
from libraries.schemas.base import TimestampedModel

T = TypeVar("T", bound=TimestampedModel)


class LoadedSignalGenerationInputs(StrictModel):
    """Typed bundle of features and optional research context used for Day 5 signals."""

    company_id: str = Field(description="Covered company identifier.")
    features: list[Feature] = Field(
        default_factory=list,
        description="Candidate features eligible for the requested ablation view.",
    )
    hypothesis: Hypothesis | None = Field(
        default=None, description="Upstream hypothesis used to summarize the signal."
    )
    evidence_assessment: EvidenceAssessment | None = Field(
        default=None,
        description="Upstream evidence assessment used to carry support gaps and confidence context.",
    )
    research_brief: ResearchBrief | None = Field(
        default=None,
        description="Upstream research brief used for memo-ready context when available.",
    )


def load_signal_generation_inputs(
    *,
    feature_root: Path,
    research_root: Path | None,
    company_id: str | None = None,
) -> LoadedSignalGenerationInputs:
    """Load Day 5 candidate features and optional Day 4 research context for one company."""

    features = _load_models(feature_root / "features", Feature)
    resolved_company_id = _resolve_company_id(company_id=company_id, features=features)
    company_features = [feature for feature in features if feature.company_id == resolved_company_id]
    if not company_features:
        raise ValueError(f"No features were found for `{resolved_company_id}`.")

    hypothesis = None
    evidence_assessment = None
    research_brief = None
    if research_root is not None and research_root.exists():
        research_briefs = _load_models(research_root / "research_briefs", ResearchBrief)
        evidence_assessments = _load_models(
            research_root / "evidence_assessments", EvidenceAssessment
        )
        hypotheses = _load_models(research_root / "hypotheses", Hypothesis)

        research_brief = _find_latest(
            [brief for brief in research_briefs if brief.company_id == resolved_company_id]
        )
        if research_brief is not None:
            hypothesis = _find_by_id(
                hypotheses, "hypothesis_id", research_brief.hypothesis_id
            )
            evidence_assessment = _find_by_id(
                evidence_assessments,
                "evidence_assessment_id",
                research_brief.evidence_assessment_id,
            )

    return LoadedSignalGenerationInputs(
        company_id=resolved_company_id,
        features=company_features,
        hypothesis=hypothesis,
        evidence_assessment=evidence_assessment,
        research_brief=research_brief,
    )


def _resolve_company_id(*, company_id: str | None, features: list[Feature]) -> str:
    """Resolve a single company identifier from persisted feature artifacts."""

    available_company_ids = sorted(
        {feature.company_id for feature in features if feature.company_id is not None}
    )
    if company_id is not None:
        if company_id not in available_company_ids:
            raise ValueError(f"Company `{company_id}` was not found under the feature root.")
        return company_id
    if len(available_company_ids) != 1:
        raise ValueError(
            "Signal generation requires an explicit company_id when features contain zero or multiple companies."
        )
    return available_company_ids[0]


def _find_latest(artifacts: list[T]) -> T | None:
    """Return the latest artifact by creation time when one exists."""

    if not artifacts:
        return None
    return max(artifacts, key=lambda artifact: artifact.created_at)


def _find_by_id(artifacts: list[T], attribute: str, identifier: str) -> T | None:
    """Return one artifact by identifier if present."""

    for artifact in artifacts:
        if getattr(artifact, attribute) == identifier:
            return artifact
    return None


def _load_models(directory: Path, model_cls: type[T]) -> list[T]:
    """Load JSON models from a category directory."""

    if not directory.exists():
        return []
    return [
        model_cls.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]
