from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from libraries.core import ensure_file_exists
from libraries.schemas import DocumentKind, EarningsCall, Filing, NewsItem, SourceReference
from services.ingestion.fixture_loader import load_raw_fixture
from services.ingestion.payloads import RawFilingFixture, RawNewsFixture, RawTranscriptFixture

ParsableDocument = Filing | EarningsCall | NewsItem
ParsableRawPayload = RawFilingFixture | RawTranscriptFixture | RawNewsFixture


@dataclass(frozen=True)
class LoadedParsingInputs:
    """Resolved document, source-reference, and raw-payload inputs for parsing."""

    document_path: Path
    source_reference_path: Path
    raw_payload_path: Path
    document: ParsableDocument
    source_reference: SourceReference
    raw_payload: ParsableRawPayload


def discover_parseable_document_paths(ingestion_root: Path) -> list[Path]:
    """Discover normalized filing, transcript, and news artifacts under an ingestion root."""

    normalized_root = ingestion_root / "normalized"
    categories = ("filings", "earnings_calls", "news_items")
    paths: list[Path] = []
    for category in categories:
        category_root = normalized_root / category
        if category_root.exists():
            paths.extend(sorted(path for path in category_root.glob("*.json") if path.is_file()))
    return sorted(paths)


def load_parseable_document(path: Path) -> ParsableDocument:
    """Load a normalized filing, transcript, or news document from disk."""

    ensure_file_exists(path, label="normalized document")
    payload = json.loads(path.read_text(encoding="utf-8"))
    kind = payload.get("kind")
    if kind == DocumentKind.FILING.value:
        return Filing.model_validate(payload)
    if kind == DocumentKind.EARNINGS_CALL.value:
        return EarningsCall.model_validate(payload)
    if kind == DocumentKind.NEWS_ITEM.value:
        return NewsItem.model_validate(payload)
    raise ValueError(f"Unsupported parseable document kind at {path}: {kind!r}")


def load_parsing_inputs(
    *,
    document_path: Path,
    source_reference_path: Path,
    raw_payload_path: Path,
) -> LoadedParsingInputs:
    """Load and cross-check the explicit artifacts required for document parsing."""

    ensure_file_exists(document_path, label="document path")
    ensure_file_exists(source_reference_path, label="source reference path")
    ensure_file_exists(raw_payload_path, label="raw payload path")
    document = load_parseable_document(document_path)
    source_reference = SourceReference.model_validate_json(
        source_reference_path.read_text(encoding="utf-8")
    )
    raw_payload = load_raw_fixture(raw_payload_path)

    if source_reference.source_reference_id != document.source_reference_id:
        raise ValueError("source_reference_path does not match the document source_reference_id.")

    expected_fixture_type = fixture_type_for_document_kind(document.kind)
    if raw_payload.fixture_type != expected_fixture_type:
        raise ValueError(
            "raw_payload_path does not match the expected fixture type for the normalized document."
        )

    if document.kind == DocumentKind.FILING:
        return LoadedParsingInputs(
            document_path=document_path,
            source_reference_path=source_reference_path,
            raw_payload_path=raw_payload_path,
            document=document,
            source_reference=source_reference,
            raw_payload=cast(RawFilingFixture, raw_payload),
        )
    if document.kind == DocumentKind.EARNINGS_CALL:
        return LoadedParsingInputs(
            document_path=document_path,
            source_reference_path=source_reference_path,
            raw_payload_path=raw_payload_path,
            document=document,
            source_reference=source_reference,
            raw_payload=cast(RawTranscriptFixture, raw_payload),
        )
    if document.kind == DocumentKind.NEWS_ITEM:
        return LoadedParsingInputs(
            document_path=document_path,
            source_reference_path=source_reference_path,
            raw_payload_path=raw_payload_path,
            document=document,
            source_reference=source_reference,
            raw_payload=cast(RawNewsFixture, raw_payload),
        )
    raise ValueError(f"Unsupported document kind for parsing: {document.kind}")


def resolve_source_reference_path(*, ingestion_root: Path, source_reference_id: str) -> Path:
    """Resolve the normalized source-reference artifact for a parsed document."""

    return ingestion_root / "normalized" / "source_references" / f"{source_reference_id}.json"


def resolve_raw_payload_path(
    *,
    ingestion_root: Path,
    document_kind: DocumentKind,
    source_reference_id: str,
) -> Path:
    """Resolve the raw fixture payload path for a parseable document."""

    fixture_type = fixture_type_for_document_kind(document_kind)
    return ingestion_root / "raw" / fixture_type / f"{source_reference_id}.json"


def fixture_type_for_document_kind(document_kind: DocumentKind) -> str:
    """Map normalized document kinds to the Day 2 raw fixture layout."""

    if document_kind == DocumentKind.FILING:
        return "filing"
    if document_kind == DocumentKind.EARNINGS_CALL:
        return "earnings_call"
    if document_kind == DocumentKind.NEWS_ITEM:
        return "news_item"
    raise ValueError(f"Unsupported document kind for raw-payload resolution: {document_kind}")
