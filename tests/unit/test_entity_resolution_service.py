from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from libraries.schemas import (
    CrossSourceIdentifierKind,
    DocumentEntityLink,
    DocumentEntityLinkScope,
    ResolutionConflict,
    ResolutionConflictKind,
    ResolutionDecision,
    ResolutionDecisionStatus,
)
from libraries.time import FrozenClock
from services.entity_resolution import (
    EntityResolutionService,
    ResolveEntityWorkspaceRequest,
)
from services.entity_resolution.storage import load_models
from services.ingestion import (
    FixtureIngestionRequest,
    FixtureIngestionResponse,
    IngestionService,
)
from services.parsing import (
    ExtractDocumentEvidenceRequest,
    ParsingService,
)

FIXED_NOW = datetime(2026, 3, 20, 10, 0, tzinfo=UTC)
INGESTION_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
ENTITY_FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "entity_resolution"


def test_entity_resolution_preserves_aliases_and_vendor_symbols(tmp_path: Path) -> None:
    ingestion_root = tmp_path / "ingestion"
    responses = _ingest_fixtures(
        ingestion_root=ingestion_root,
        fixture_paths=[
            ENTITY_FIXTURE_ROOT / "companies" / "apex_company_reference_alt_name.json",
            INGESTION_FIXTURE_ROOT / "companies" / "apex_company_reference.json",
            INGESTION_FIXTURE_ROOT / "market_data" / "apex_price_series_metadata.json",
        ],
    )

    response = EntityResolutionService(clock=FrozenClock(FIXED_NOW)).resolve_entity_workspace(
        ResolveEntityWorkspaceRequest(
            ingestion_root=ingestion_root,
            output_root=tmp_path / "entity_resolution_refresh",
            requested_by="unit_test",
        )
    )

    canonical_company = responses["apex_company_reference"].company
    assert canonical_company is not None
    canonical_company_id = canonical_company.company_id
    assert any(
        alias.company_id == canonical_company_id
        and alias.alias_text == "Apex Instrument Systems, Inc."
        for alias in response.company_aliases
    )
    assert any(
        alias.company_id == canonical_company_id and alias.vendor_symbol == "APEX.O"
        for alias in response.ticker_aliases
    )
    assert any(
        link.company_id == canonical_company_id
        and link.identifier_kind is CrossSourceIdentifierKind.VENDOR_SYMBOL
        and link.identifier_value == "APEX.O"
        for link in response.cross_source_links
    )


def test_entity_resolution_uses_exact_ticker_exchange_when_cik_is_missing(tmp_path: Path) -> None:
    ingestion_root = tmp_path / "ingestion"
    responses = _ingest_fixtures(
        ingestion_root=ingestion_root,
        fixture_paths=[
            INGESTION_FIXTURE_ROOT / "companies" / "apex_company_reference.json",
            ENTITY_FIXTURE_ROOT / "companies" / "apex_biosystems_lse_company_reference.json",
        ],
    )

    response = EntityResolutionService(clock=FrozenClock(FIXED_NOW)).resolve_entity_workspace(
        ResolveEntityWorkspaceRequest(
            ingestion_root=ingestion_root,
            output_root=tmp_path / "entity_resolution_refresh",
            requested_by="unit_test",
        )
    )

    lse_source_reference_id = responses["apex_biosystems_lse_company_reference"].source_reference.source_reference_id
    lse_company = responses["apex_biosystems_lse_company_reference"].company
    assert lse_company is not None
    lse_company_id = lse_company.company_id
    decision = next(
        model
        for model in response.resolution_decisions
        if model.target_type == "source_reference" and model.target_id == lse_source_reference_id
    )

    assert decision.status is ResolutionDecisionStatus.RESOLVED
    assert decision.rule_name == "exact_ticker_exchange"
    assert decision.selected_company_id == lse_company_id


def test_entity_resolution_records_ambiguous_and_unresolved_news_cases(tmp_path: Path) -> None:
    ingestion_root = tmp_path / "ingestion"
    responses = _ingest_fixtures(
        ingestion_root=ingestion_root,
        fixture_paths=[
            INGESTION_FIXTURE_ROOT / "companies" / "apex_company_reference.json",
            ENTITY_FIXTURE_ROOT / "companies" / "apex_biosystems_lse_company_reference.json",
            ENTITY_FIXTURE_ROOT / "news" / "apex_ambiguous_news.json",
            ENTITY_FIXTURE_ROOT / "news" / "industry_roundup_unresolved_news.json",
        ],
    )

    response = EntityResolutionService(clock=FrozenClock(FIXED_NOW)).resolve_entity_workspace(
        ResolveEntityWorkspaceRequest(
            ingestion_root=ingestion_root,
            output_root=tmp_path / "entity_resolution_refresh",
            requested_by="unit_test",
        )
    )

    ambiguous_news = responses["apex_ambiguous_news"].news_item
    unresolved_news = responses["industry_roundup_unresolved_news"].news_item
    assert ambiguous_news is not None
    assert unresolved_news is not None
    ambiguous_document_id = ambiguous_news.document_id
    ambiguous_decision = next(
        model
        for model in response.resolution_decisions
        if model.target_type == "document" and model.target_id == ambiguous_document_id
    )
    assert ambiguous_decision.status is ResolutionDecisionStatus.AMBIGUOUS
    assert ambiguous_decision.selected_company_id is None
    assert any(
        conflict.target_id == ambiguous_document_id
        and conflict.conflict_kind is ResolutionConflictKind.ALIAS_COLLISION
        for conflict in response.resolution_conflicts
    )

    unresolved_document_id = unresolved_news.document_id
    unresolved_decision = next(
        model
        for model in response.resolution_decisions
        if model.target_type == "document" and model.target_id == unresolved_document_id
    )
    assert unresolved_decision.status is ResolutionDecisionStatus.UNRESOLVED
    assert unresolved_decision.selected_company_id is None
    assert not any(
        link.document_id == unresolved_document_id for link in response.document_entity_links
    )


def test_entity_resolution_keeps_parsing_conflicts_unresolved(tmp_path: Path) -> None:
    ingestion_root = tmp_path / "ingestion"
    parsing_root = tmp_path / "parsing"
    responses = _ingest_fixtures(
        ingestion_root=ingestion_root,
        fixture_paths=[
            INGESTION_FIXTURE_ROOT / "filings" / "apex_q1_2026_10q.json",
            ENTITY_FIXTURE_ROOT / "companies" / "apex_biosystems_lse_company_reference.json",
        ],
    )
    filing_response = responses["apex_q1_2026_10q"]
    lse_company = responses["apex_biosystems_lse_company_reference"].company
    assert lse_company is not None
    lse_company_id = lse_company.company_id
    assert filing_response.filing is not None

    ParsingService(clock=FrozenClock(FIXED_NOW)).extract_document_evidence(
        ExtractDocumentEvidenceRequest(
            document_path=ingestion_root
            / "normalized"
            / "filings"
            / f"{filing_response.filing.document_id}.json",
            source_reference_path=ingestion_root
            / "normalized"
            / "source_references"
            / f"{filing_response.source_reference.source_reference_id}.json",
            raw_payload_path=ingestion_root
            / "raw"
            / "filing"
            / f"{filing_response.source_reference.source_reference_id}.json",
            output_root=parsing_root,
            requested_by="unit_test",
        )
    )

    parsed_text_path = next((parsing_root / "parsed_text").glob("*.json"))
    parsed_text_payload = json.loads(parsed_text_path.read_text(encoding="utf-8"))
    parsed_text_payload["company_id"] = lse_company_id
    parsed_text_path.write_text(json.dumps(parsed_text_payload, indent=2), encoding="utf-8")

    explicit_root = tmp_path / "entity_resolution_refresh"
    response = EntityResolutionService(clock=FrozenClock(FIXED_NOW)).resolve_entity_workspace(
        ResolveEntityWorkspaceRequest(
            ingestion_root=ingestion_root,
            parsing_root=parsing_root,
            document_ids=[filing_response.filing.document_id],
            output_root=explicit_root,
            requested_by="unit_test",
        )
    )

    decision = next(
        model
        for model in response.resolution_decisions
        if model.target_type == "document"
        and model.target_id == filing_response.filing.document_id
    )
    assert decision.status is ResolutionDecisionStatus.UNRESOLVED
    assert decision.selected_company_id is None
    assert any(
        conflict.target_id == filing_response.filing.document_id
        and conflict.conflict_kind is ResolutionConflictKind.METADATA_MISMATCH
        for conflict in response.resolution_conflicts
    )
    assert not any(
        link.document_id == filing_response.filing.document_id
        and link.link_scope is DocumentEntityLinkScope.EVIDENCE_INHERITED
        for link in response.document_entity_links
    )

    persisted_links = load_models(
        root=explicit_root,
        category="document_entity_links",
        model_cls=DocumentEntityLink,
    )
    persisted_decisions = load_models(
        root=explicit_root,
        category="resolution_decisions",
        model_cls=ResolutionDecision,
    )
    persisted_conflicts = load_models(
        root=explicit_root,
        category="resolution_conflicts",
        model_cls=ResolutionConflict,
    )
    assert all(link.document_id == filing_response.filing.document_id for link in persisted_links)
    assert any(
        model.target_id == filing_response.filing.document_id
        and model.status is ResolutionDecisionStatus.UNRESOLVED
        for model in persisted_decisions
    )
    assert any(
        model.target_id == filing_response.filing.document_id
        and model.conflict_kind is ResolutionConflictKind.METADATA_MISMATCH
        for model in persisted_conflicts
    )


def _ingest_fixtures(
    *,
    ingestion_root: Path,
    fixture_paths: list[Path],
) -> dict[str, FixtureIngestionResponse]:
    service = IngestionService(clock=FrozenClock(FIXED_NOW))
    responses: dict[str, FixtureIngestionResponse] = {}
    for path in fixture_paths:
        responses[path.stem] = service.ingest_fixture(
            FixtureIngestionRequest(
                fixture_path=path,
                output_root=ingestion_root,
                requested_by="unit_test",
            )
        )
    return responses
