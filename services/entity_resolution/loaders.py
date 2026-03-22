from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from libraries.core import ensure_directory_exists, load_local_models
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
    ParsedDocumentText,
    PriceSeriesMetadata,
    SourceReference,
    StrictModel,
    ToneMarker,
)
from services.ingestion.fixture_loader import load_raw_fixture
from services.ingestion.payloads import RawCompanyReference, RawFixturePayload

TModel = TypeVar("TModel", bound=StrictModel)


@dataclass(frozen=True)
class RawSourceObservation:
    """One persisted raw fixture observation keyed by source reference."""

    source_reference_id: str
    fixture_path: Path
    payload: RawFixturePayload
    company_reference: RawCompanyReference | None


@dataclass(frozen=True)
class LoadedEntityResolutionWorkspace:
    """Resolved ingestion and parsing artifacts used for entity resolution."""

    companies_by_id: dict[str, Company]
    source_references_by_id: dict[str, SourceReference]
    documents_by_id: dict[str, Document]
    price_series_metadata_by_source_reference_id: dict[str, list[PriceSeriesMetadata]]
    raw_observations_by_source_reference_id: dict[str, RawSourceObservation]
    parsed_texts_by_document_id: dict[str, ParsedDocumentText]
    evidence_spans_by_document_id: dict[str, list[EvidenceSpan]]
    parsing_company_ids_by_document_id: dict[str, set[str]]


def load_entity_resolution_workspace(
    *,
    ingestion_root: Path,
    parsing_root: Path | None,
) -> LoadedEntityResolutionWorkspace:
    """Load the persisted ingestion and parsing artifacts needed for entity resolution."""

    ensure_directory_exists(ingestion_root, label="ingestion root")
    companies = _load_models(ingestion_root / "normalized" / "companies", Company)
    source_references = _load_models(
        ingestion_root / "normalized" / "source_references",
        SourceReference,
    )
    documents = [
        *_load_models(ingestion_root / "normalized" / "filings", Filing),
        *_load_models(ingestion_root / "normalized" / "earnings_calls", EarningsCall),
        *_load_models(ingestion_root / "normalized" / "news_items", NewsItem),
    ]
    price_metadata = _load_models(
        ingestion_root / "normalized" / "price_series_metadata",
        PriceSeriesMetadata,
    )
    raw_observations = _load_raw_observations(ingestion_root=ingestion_root)
    parsed_texts: dict[str, ParsedDocumentText] = {}
    evidence_spans_by_document_id: dict[str, list[EvidenceSpan]] = {}
    parsing_company_ids_by_document_id: dict[str, set[str]] = {}
    if parsing_root is not None:
        parsed_texts = {
            artifact.document_id: artifact
            for artifact in _load_models(parsing_root / "parsed_text", ParsedDocumentText)
        }
        for span in _load_models(parsing_root / "evidence_spans", EvidenceSpan):
            if span.document_id is None:
                continue
            evidence_spans_by_document_id.setdefault(span.document_id, []).append(span)
        parsing_company_ids_by_document_id = _load_parsing_company_ids_by_document(
            parsing_root=parsing_root
        )

    price_series_metadata_by_source_reference_id: dict[str, list[PriceSeriesMetadata]] = {}
    for metadata in price_metadata:
        price_series_metadata_by_source_reference_id.setdefault(
            metadata.source_reference_id, []
        ).append(metadata)

    return LoadedEntityResolutionWorkspace(
        companies_by_id={company.company_id: company for company in companies},
        source_references_by_id={
            source_reference.source_reference_id: source_reference
            for source_reference in source_references
        },
        documents_by_id={document.document_id: document for document in documents},
        price_series_metadata_by_source_reference_id=price_series_metadata_by_source_reference_id,
        raw_observations_by_source_reference_id=raw_observations,
        parsed_texts_by_document_id=parsed_texts,
        evidence_spans_by_document_id=evidence_spans_by_document_id,
        parsing_company_ids_by_document_id=parsing_company_ids_by_document_id,
    )


def _load_raw_observations(*, ingestion_root: Path) -> dict[str, RawSourceObservation]:
    """Load raw ingestion fixtures keyed by persisted source reference identifier."""

    raw_root = ingestion_root / "raw"
    if not raw_root.exists():
        return {}
    observations: dict[str, RawSourceObservation] = {}
    for path in sorted(raw_root.rglob("*.json")):
        if not path.is_file():
            continue
        payload = load_raw_fixture(path)
        company_reference = getattr(payload, "company", None)
        observations[path.stem] = RawSourceObservation(
            source_reference_id=path.stem,
            fixture_path=path,
            payload=payload,
            company_reference=company_reference,
        )
    return observations


def _load_parsing_company_ids_by_document(
    *,
    parsing_root: Path,
) -> dict[str, set[str]]:
    """Collect any company identifiers carried by parsing artifacts for one document."""

    company_ids_by_document_id: dict[str, set[str]] = {}
    parsed_texts = _load_models(parsing_root / "parsed_text", ParsedDocumentText)
    for parsed_text in parsed_texts:
        if parsed_text.company_id is not None:
            company_ids_by_document_id.setdefault(parsed_text.document_id, set()).add(
                parsed_text.company_id
            )
    for claim in _load_models(parsing_root / "claims", ExtractedClaim):
        if claim.company_id is not None:
            company_ids_by_document_id.setdefault(claim.document_id, set()).add(
                claim.company_id
            )
    for risk_factor in _load_models(parsing_root / "risk_factors", ExtractedRiskFactor):
        if risk_factor.company_id is not None:
            company_ids_by_document_id.setdefault(risk_factor.document_id, set()).add(
                risk_factor.company_id
            )
    for guidance_change in _load_models(parsing_root / "guidance_changes", GuidanceChange):
        if guidance_change.company_id is not None:
            company_ids_by_document_id.setdefault(guidance_change.document_id, set()).add(
                guidance_change.company_id
            )
    for tone_marker in _load_models(parsing_root / "tone_markers", ToneMarker):
        if tone_marker.company_id is not None:
            company_ids_by_document_id.setdefault(tone_marker.document_id, set()).add(
                tone_marker.company_id
            )
    return company_ids_by_document_id


def _load_models(directory: Path, model_cls: type[TModel]) -> list[TModel]:
    """Load JSON models from one category directory when present."""

    return load_local_models(directory, model_cls)
