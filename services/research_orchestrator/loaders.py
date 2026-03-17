from __future__ import annotations

from pathlib import Path
from typing import TypeVar

from pydantic import Field

from libraries.schemas import (
    Company,
    Document,
    EarningsCall,
    EvidenceSpan,
    ExtractedClaim,
    ExtractedRiskFactor,
    Filing,
    GuidanceChange,
    NewsItem,
    SourceReference,
    StrictModel,
    ToneMarker,
)

T = TypeVar("T", bound=StrictModel)


class LoadedResearchArtifacts(StrictModel):
    """Typed input bundle for deterministic research workflows."""

    company_id: str = Field(description="Covered company identifier for the loaded artifacts.")
    company: Company | None = Field(
        default=None, description="Normalized company context when available."
    )
    documents: list[Document] = Field(
        default_factory=list,
        description="Normalized documents associated with the research workflow.",
    )
    source_references: list[SourceReference] = Field(
        default_factory=list,
        description="Source references associated with the loaded parsing artifacts.",
    )
    evidence_spans: list[EvidenceSpan] = Field(
        default_factory=list, description="Exact evidence spans available for research linking."
    )
    claims: list[ExtractedClaim] = Field(
        default_factory=list, description="Extracted claims available as hypothesis support."
    )
    risk_factors: list[ExtractedRiskFactor] = Field(
        default_factory=list, description="Extracted risk factors available for critique."
    )
    guidance_changes: list[GuidanceChange] = Field(
        default_factory=list,
        description="Guidance-change artifacts available for support grading and thesis building.",
    )
    tone_markers: list[ToneMarker] = Field(
        default_factory=list,
        description="Tone markers available as cautionary or contextual signals.",
    )


def load_research_artifacts(
    *,
    parsing_root: Path,
    ingestion_root: Path | None,
    company_id: str | None = None,
) -> LoadedResearchArtifacts:
    """Load parsing artifacts and optional company context for one company."""

    claims = _load_models(parsing_root / "claims", ExtractedClaim)
    risk_factors = _load_models(parsing_root / "risk_factors", ExtractedRiskFactor)
    guidance_changes = _load_models(parsing_root / "guidance_changes", GuidanceChange)
    tone_markers = _load_models(parsing_root / "tone_markers", ToneMarker)

    resolved_company_id = _resolve_company_id(
        company_id=company_id,
        claims=claims,
        risk_factors=risk_factors,
        guidance_changes=guidance_changes,
        tone_markers=tone_markers,
    )
    filtered_claims = [claim for claim in claims if claim.company_id == resolved_company_id]
    filtered_risk_factors = [
        risk_factor for risk_factor in risk_factors if risk_factor.company_id == resolved_company_id
    ]
    filtered_guidance_changes = [
        change for change in guidance_changes if change.company_id == resolved_company_id
    ]
    filtered_tone_markers = [
        marker for marker in tone_markers if marker.company_id == resolved_company_id
    ]

    document_ids = {
        artifact.document_id
        for artifact in [
            *filtered_claims,
            *filtered_risk_factors,
            *filtered_guidance_changes,
            *filtered_tone_markers,
        ]
    }
    source_reference_ids = {
        artifact.source_reference_id
        for artifact in [
            *filtered_claims,
            *filtered_risk_factors,
            *filtered_guidance_changes,
            *filtered_tone_markers,
        ]
    }
    evidence_span_ids = {
        span_id
        for artifact in [*filtered_claims, *filtered_risk_factors, *filtered_guidance_changes]
        for span_id in artifact.evidence_span_ids
    }
    evidence_spans = [
        span
        for span in _load_models(parsing_root / "evidence_spans", EvidenceSpan)
        if span.evidence_span_id in evidence_span_ids
    ]

    company = None
    documents: list[Document] = []
    source_references: list[SourceReference] = []
    if ingestion_root is not None:
        company = _load_company(ingestion_root=ingestion_root, company_id=resolved_company_id)
        documents = _load_documents(
            ingestion_root=ingestion_root,
            company_id=resolved_company_id,
            document_ids=document_ids,
        )
        source_references = [
            source_reference
            for source_reference in _load_models(
                ingestion_root / "normalized" / "source_references",
                SourceReference,
            )
            if source_reference.source_reference_id in source_reference_ids
        ]

    return LoadedResearchArtifacts(
        company_id=resolved_company_id,
        company=company,
        documents=documents,
        source_references=source_references,
        evidence_spans=evidence_spans,
        claims=filtered_claims,
        risk_factors=filtered_risk_factors,
        guidance_changes=filtered_guidance_changes,
        tone_markers=filtered_tone_markers,
    )


def _resolve_company_id(
    *,
    company_id: str | None,
    claims: list[ExtractedClaim],
    risk_factors: list[ExtractedRiskFactor],
    guidance_changes: list[GuidanceChange],
    tone_markers: list[ToneMarker],
) -> str:
    """Resolve the target company from persisted parsing artifacts."""

    available_company_ids = sorted(
        {
            artifact.company_id
            for artifact in [*claims, *risk_factors, *guidance_changes, *tone_markers]
            if artifact.company_id
        }
    )
    if company_id is not None:
        if company_id not in available_company_ids:
            raise ValueError(f"Company `{company_id}` was not found under the parsing root.")
        return company_id
    if len(available_company_ids) != 1:
        raise ValueError(
            "Research workflow requires an explicit company_id when parsing artifacts contain "
            "zero or multiple companies."
        )
    return available_company_ids[0]


def _load_company(*, ingestion_root: Path, company_id: str) -> Company | None:
    """Load one normalized company record when available."""

    company_path = ingestion_root / "normalized" / "companies" / f"{company_id}.json"
    if not company_path.exists():
        return None
    return Company.model_validate_json(company_path.read_text(encoding="utf-8"))


def _load_documents(
    *,
    ingestion_root: Path,
    company_id: str,
    document_ids: set[str],
) -> list[Document]:
    """Load normalized document records for one company."""

    documents: list[Document] = []
    for filing in _load_models(ingestion_root / "normalized" / "filings", Filing):
        if filing.company_id == company_id and (not document_ids or filing.document_id in document_ids):
            documents.append(filing)
    for earnings_call in _load_models(
        ingestion_root / "normalized" / "earnings_calls", EarningsCall
    ):
        if earnings_call.company_id == company_id and (
            not document_ids or earnings_call.document_id in document_ids
        ):
            documents.append(earnings_call)
    for news_item in _load_models(ingestion_root / "normalized" / "news_items", NewsItem):
        if news_item.company_id == company_id and (
            not document_ids or news_item.document_id in document_ids
        ):
            documents.append(news_item)
    return sorted(documents, key=lambda document: (document.effective_at or document.ingested_at))


def _load_models(directory: Path, model_cls: type[T]) -> list[T]:
    """Load JSON models from a category directory."""

    if not directory.exists():
        return []
    return [
        model_cls.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"))
    ]
