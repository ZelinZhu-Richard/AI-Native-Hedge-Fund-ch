from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

from pydantic import Field

from libraries.config import get_settings
from libraries.core import build_provenance
from libraries.core.service_framework import BaseService, ServiceCapability
from libraries.schemas import (
    ArtifactStorageLocation,
    Company,
    CompanyAlias,
    CompanyAliasKind,
    CrossSourceIdentifierKind,
    CrossSourceLink,
    Document,
    DocumentEntityLink,
    DocumentEntityLinkScope,
    EntityReference,
    NewsItem,
    ResolutionConfidence,
    ResolutionConflict,
    ResolutionConflictKind,
    ResolutionDecision,
    ResolutionDecisionStatus,
    StrictModel,
    TickerAlias,
)
from libraries.utils import make_canonical_id
from services.entity_resolution.loaders import (
    LoadedEntityResolutionWorkspace,
    RawSourceObservation,
    load_entity_resolution_workspace,
)
from services.entity_resolution.matchers import (
    build_alias_map,
    match_text_against_aliases,
    resolve_company_reference,
)
from services.entity_resolution.storage import LocalEntityResolutionArtifactStore
from services.ingestion.payloads import RawCompanyReference, RawPriceSeriesMetadataFixture


class ResolveEntityWorkspaceRequest(StrictModel):
    """Request to resolve canonical company identity across one local workspace slice."""

    ingestion_root: Path = Field(description="Root path containing normalized ingestion artifacts.")
    parsing_root: Path | None = Field(
        default=None,
        description="Optional parsing artifact root used for mention-level and evidence links.",
    )
    company_id: str | None = Field(
        default=None,
        description="Optional canonical company identifier used to narrow the workspace slice.",
    )
    document_ids: list[str] = Field(
        default_factory=list,
        description="Optional explicit document identifiers to refresh.",
    )
    output_root: Path | None = Field(
        default=None,
        description="Optional root for persisted entity-resolution artifacts.",
    )
    requested_by: str = Field(description="Requester identifier.")


class ResolveEntityWorkspaceResponse(StrictModel):
    """Structured resolution artifacts produced for one local workspace slice."""

    entity_references: list[EntityReference] = Field(default_factory=list)
    company_aliases: list[CompanyAlias] = Field(default_factory=list)
    ticker_aliases: list[TickerAlias] = Field(default_factory=list)
    document_entity_links: list[DocumentEntityLink] = Field(default_factory=list)
    cross_source_links: list[CrossSourceLink] = Field(default_factory=list)
    resolution_decisions: list[ResolutionDecision] = Field(default_factory=list)
    resolution_conflicts: list[ResolutionConflict] = Field(default_factory=list)
    storage_locations: list[ArtifactStorageLocation] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class EntityResolutionService(BaseService):
    """Resolve canonical companies, preserve aliases, and surface ambiguity explicitly."""

    capability_name = "entity_resolution"
    capability_description = (
        "Builds canonical company links, preserved aliases, and explicit ambiguity records."
    )

    def capability(self) -> ServiceCapability:
        """Return capability metadata for service discovery."""

        return ServiceCapability(
            name=self.capability_name,
            description=self.capability_description,
            consumes=["Company", "Document", "ParsedDocumentText", "raw fixture payload"],
            produces=[
                "EntityReference",
                "CompanyAlias",
                "TickerAlias",
                "DocumentEntityLink",
                "CrossSourceLink",
                "ResolutionDecision",
                "ResolutionConflict",
            ],
            api_routes=[],
        )

    def resolve_entity_workspace(
        self,
        request: ResolveEntityWorkspaceRequest,
    ) -> ResolveEntityWorkspaceResponse:
        """Resolve canonical company identity across one local ingestion/parsing workspace."""

        output_root = request.output_root or (
            get_settings().resolved_artifact_root / "entity_resolution"
        )
        workspace = load_entity_resolution_workspace(
            ingestion_root=request.ingestion_root,
            parsing_root=request.parsing_root,
        )
        now = self.clock.now()
        selected_document_ids = set(request.document_ids)

        company_aliases_by_id: dict[str, CompanyAlias] = {}
        ticker_aliases_by_id: dict[str, TickerAlias] = {}
        cross_source_links_by_id: dict[str, CrossSourceLink] = {}
        resolution_decisions_by_id: dict[str, ResolutionDecision] = {}
        resolution_conflicts_by_id: dict[str, ResolutionConflict] = {}
        document_entity_links_by_id: dict[str, DocumentEntityLink] = {}
        observed_aliases_by_company_id: dict[str, set[str]] = defaultdict(set)
        observed_tickers_by_company_id: dict[str, set[str]] = defaultdict(set)
        source_reference_ids_by_company_id: dict[str, set[str]] = defaultdict(set)
        latest_decision_id_by_company_id: dict[str, str] = {}
        source_decisions_by_source_reference_id: dict[str, ResolutionDecision] = {}

        for company in workspace.companies_by_id.values():
            observed_aliases_by_company_id[company.company_id].add(company.legal_name)
            if company.ticker is not None:
                observed_tickers_by_company_id[company.company_id].add(company.ticker)

        for observation in sorted(
            workspace.raw_observations_by_source_reference_id.values(),
            key=lambda candidate: candidate.source_reference_id,
        ):
            if observation.company_reference is None:
                continue
            company_alias_map = {
                normalize_alias: company_ids
                for normalize_alias, company_ids in build_alias_map(
                    canonical_names_by_company_id={
                        company.company_id: company.legal_name
                        for company in workspace.companies_by_id.values()
                    },
                    observed_aliases_by_company_id=observed_aliases_by_company_id,
                    observed_tickers_by_company_id={},
                ).items()
            }
            source_decision, source_conflicts = self._resolve_source_observation(
                observation=observation,
                workspace=workspace,
                company_alias_map=company_alias_map,
                now=now,
            )
            source_decisions_by_source_reference_id[observation.source_reference_id] = source_decision
            resolution_decisions_by_id[source_decision.resolution_decision_id] = source_decision
            for conflict in source_conflicts:
                resolution_conflicts_by_id[conflict.resolution_conflict_id] = conflict
            selected_company_id = source_decision.selected_company_id
            if selected_company_id is None:
                continue
            resolved_company = workspace.companies_by_id.get(selected_company_id)
            if resolved_company is None:
                continue
            latest_decision_id_by_company_id[resolved_company.company_id] = (
                source_decision.resolution_decision_id
            )
            source_reference_ids_by_company_id[resolved_company.company_id].add(
                observation.source_reference_id
            )
            self._register_company_aliases(
                company=resolved_company,
                observation=observation,
                company_aliases_by_id=company_aliases_by_id,
                ticker_aliases_by_id=ticker_aliases_by_id,
                cross_source_links_by_id=cross_source_links_by_id,
                observed_aliases_by_company_id=observed_aliases_by_company_id,
                observed_tickers_by_company_id=observed_tickers_by_company_id,
                source_reference_ids_by_company_id=source_reference_ids_by_company_id,
                workspace=workspace,
                now=now,
            )

        alias_map = build_alias_map(
            canonical_names_by_company_id={
                company.company_id: company.legal_name for company in workspace.companies_by_id.values()
            },
            observed_aliases_by_company_id=observed_aliases_by_company_id,
            observed_tickers_by_company_id=observed_tickers_by_company_id,
        )

        for document in sorted(
            workspace.documents_by_id.values(),
            key=lambda candidate: candidate.document_id,
        ):
            if selected_document_ids and document.document_id not in selected_document_ids:
                continue
            if request.company_id is not None and not selected_document_ids:
                document_source_decision = source_decisions_by_source_reference_id.get(
                    document.source_reference_id
                )
                if (
                    document.company_id != request.company_id
                    and document_source_decision is not None
                    and document_source_decision.selected_company_id != request.company_id
                ):
                    continue
            document_decision, document_conflicts, document_links = self._resolve_document(
                document=document,
                workspace=workspace,
                source_decisions_by_source_reference_id=source_decisions_by_source_reference_id,
                alias_map=alias_map,
                now=now,
            )
            resolution_decisions_by_id[document_decision.resolution_decision_id] = document_decision
            for conflict in document_conflicts:
                resolution_conflicts_by_id[conflict.resolution_conflict_id] = conflict
            for link in document_links:
                document_entity_links_by_id[link.document_entity_link_id] = link
            if document_decision.selected_company_id is not None:
                latest_decision_id_by_company_id[document_decision.selected_company_id] = (
                    document_decision.resolution_decision_id
                )

        entity_references = self._build_entity_references(
            workspace=workspace,
            company_aliases_by_id=company_aliases_by_id,
            ticker_aliases_by_id=ticker_aliases_by_id,
            cross_source_links_by_id=cross_source_links_by_id,
            latest_decision_id_by_company_id=latest_decision_id_by_company_id,
            source_reference_ids_by_company_id=source_reference_ids_by_company_id,
            now=now,
            company_id=request.company_id,
        )

        store = LocalEntityResolutionArtifactStore(root=output_root, clock=self.clock)
        storage_locations: list[ArtifactStorageLocation] = []
        for entity_reference in sorted(
            entity_references,
            key=lambda candidate: candidate.entity_reference_id,
        ):
            storage_locations.append(
                store.persist_model(
                    artifact_id=entity_reference.entity_reference_id,
                    category="entity_references",
                    model=entity_reference,
                    source_reference_ids=entity_reference.provenance.source_reference_ids,
                )
            )
        for company_alias in sorted(
            company_aliases_by_id.values(),
            key=lambda candidate: candidate.company_alias_id,
        ):
            if request.company_id is not None and company_alias.company_id != request.company_id:
                continue
            storage_locations.append(
                store.persist_model(
                    artifact_id=company_alias.company_alias_id,
                    category="company_aliases",
                    model=company_alias,
                    source_reference_ids=company_alias.provenance.source_reference_ids,
                )
            )
        for ticker_alias in sorted(
            ticker_aliases_by_id.values(),
            key=lambda candidate: candidate.ticker_alias_id,
        ):
            if request.company_id is not None and ticker_alias.company_id != request.company_id:
                continue
            storage_locations.append(
                store.persist_model(
                    artifact_id=ticker_alias.ticker_alias_id,
                    category="ticker_aliases",
                    model=ticker_alias,
                    source_reference_ids=ticker_alias.provenance.source_reference_ids,
                )
            )
        for cross_source_link in sorted(
            cross_source_links_by_id.values(),
            key=lambda candidate: candidate.cross_source_link_id,
        ):
            if (
                request.company_id is not None
                and cross_source_link.company_id != request.company_id
            ):
                continue
            storage_locations.append(
                store.persist_model(
                    artifact_id=cross_source_link.cross_source_link_id,
                    category="cross_source_links",
                    model=cross_source_link,
                    source_reference_ids=cross_source_link.provenance.source_reference_ids,
                )
            )
        for document_entity_link in sorted(
            document_entity_links_by_id.values(),
            key=lambda candidate: candidate.document_entity_link_id,
        ):
            storage_locations.append(
                store.persist_model(
                    artifact_id=document_entity_link.document_entity_link_id,
                    category="document_entity_links",
                    model=document_entity_link,
                    source_reference_ids=document_entity_link.provenance.source_reference_ids,
                )
            )
        for resolution_decision in sorted(
            resolution_decisions_by_id.values(),
            key=lambda candidate: candidate.resolution_decision_id,
        ):
            storage_locations.append(
                store.persist_model(
                    artifact_id=resolution_decision.resolution_decision_id,
                    category="resolution_decisions",
                    model=resolution_decision,
                    source_reference_ids=resolution_decision.provenance.source_reference_ids,
                )
            )
        for resolution_conflict in sorted(
            resolution_conflicts_by_id.values(),
            key=lambda candidate: candidate.resolution_conflict_id,
        ):
            storage_locations.append(
                store.persist_model(
                    artifact_id=resolution_conflict.resolution_conflict_id,
                    category="resolution_conflicts",
                    model=resolution_conflict,
                    source_reference_ids=resolution_conflict.provenance.source_reference_ids,
                )
            )

        notes = [
            f"resolved_entity_references={len(entity_references)}",
            f"document_entity_links={len(document_entity_links_by_id)}",
            f"resolution_decisions={len(resolution_decisions_by_id)}",
            f"resolution_conflicts={len(resolution_conflicts_by_id)}",
        ]
        if request.company_id is not None:
            notes.append(f"company_scope={request.company_id}")
        if request.document_ids:
            notes.append(f"document_scope={len(request.document_ids)}")

        return ResolveEntityWorkspaceResponse(
            entity_references=entity_references,
            company_aliases=sorted(company_aliases_by_id.values(), key=lambda model: model.company_alias_id),
            ticker_aliases=sorted(ticker_aliases_by_id.values(), key=lambda model: model.ticker_alias_id),
            document_entity_links=sorted(
                document_entity_links_by_id.values(),
                key=lambda model: model.document_entity_link_id,
            ),
            cross_source_links=sorted(
                cross_source_links_by_id.values(),
                key=lambda model: model.cross_source_link_id,
            ),
            resolution_decisions=sorted(
                resolution_decisions_by_id.values(),
                key=lambda model: model.resolution_decision_id,
            ),
            resolution_conflicts=sorted(
                resolution_conflicts_by_id.values(),
                key=lambda model: model.resolution_conflict_id,
            ),
            storage_locations=storage_locations,
            notes=notes,
        )

    def _resolve_source_observation(
        self,
        *,
        observation: RawSourceObservation,
        workspace: LoadedEntityResolutionWorkspace,
        company_alias_map: dict[str, set[str]],
        now: datetime,
    ) -> tuple[ResolutionDecision, list[ResolutionConflict]]:
        """Resolve one raw source observation carrying company metadata."""

        assert observation.company_reference is not None
        outcome = resolve_company_reference(
            raw_company=observation.company_reference,
            companies_by_id=workspace.companies_by_id,
            company_alias_map=company_alias_map,
        )
        conflicts: list[ResolutionConflict] = []
        if outcome.status is ResolutionDecisionStatus.AMBIGUOUS:
            conflicts.append(
                self._build_conflict(
                    target_type="source_reference",
                    target_id=observation.source_reference_id,
                    conflict_kind=ResolutionConflictKind.MULTIPLE_CANDIDATES,
                    candidate_company_ids=outcome.candidate_company_ids,
                    message=(
                        "Source metadata matched multiple canonical companies and could not be collapsed safely."
                    ),
                    blocking=True,
                    source_reference_ids=[observation.source_reference_id],
                    now=now,
                )
            )
        elif outcome.status is ResolutionDecisionStatus.UNRESOLVED:
            conflicts.append(
                self._build_conflict(
                    target_type="source_reference",
                    target_id=observation.source_reference_id,
                    conflict_kind=self._source_unresolved_conflict_kind(
                        company_reference=observation.company_reference,
                    ),
                    candidate_company_ids=[],
                    message=(
                        "Source metadata did not resolve to an existing canonical company."
                    ),
                    blocking=True,
                    source_reference_ids=[observation.source_reference_id],
                    now=now,
                )
            )

        decision = ResolutionDecision(
            resolution_decision_id=make_canonical_id(
                "rdec",
                "source_reference",
                observation.source_reference_id,
                outcome.rule_name,
                outcome.status.value,
                outcome.selected_company_id or "none",
                *outcome.candidate_company_ids,
            ),
            target_type="source_reference",
            target_id=observation.source_reference_id,
            candidate_company_ids=outcome.candidate_company_ids,
            selected_company_id=outcome.selected_company_id,
            status=outcome.status,
            confidence=outcome.confidence,
            rule_name=outcome.rule_name,
            rationale=outcome.rationale,
            related_conflict_ids=[conflict.resolution_conflict_id for conflict in conflicts],
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="day16_source_entity_resolution",
                source_reference_ids=[observation.source_reference_id],
                upstream_artifact_ids=[
                    observation.source_reference_id,
                    *outcome.candidate_company_ids,
                ],
            ),
            created_at=now,
            updated_at=now,
        )
        return decision, conflicts

    def _register_company_aliases(
        self,
        *,
        company: Company,
        observation: RawSourceObservation,
        company_aliases_by_id: dict[str, CompanyAlias],
        ticker_aliases_by_id: dict[str, TickerAlias],
        cross_source_links_by_id: dict[str, CrossSourceLink],
        observed_aliases_by_company_id: dict[str, set[str]],
        observed_tickers_by_company_id: dict[str, set[str]],
        source_reference_ids_by_company_id: dict[str, set[str]],
        workspace: LoadedEntityResolutionWorkspace,
        now: datetime,
    ) -> None:
        """Register preserved aliases and cross-source identifiers for one resolved company."""

        source_reference_ids_by_company_id[company.company_id].add(observation.source_reference_id)
        observed_aliases_by_company_id[company.company_id].add(company.legal_name)
        if company.ticker is not None:
            observed_tickers_by_company_id[company.company_id].add(company.ticker)

        self._upsert_company_alias(
            company_aliases_by_id=company_aliases_by_id,
            company_id=company.company_id,
            alias_text=company.legal_name,
            alias_kind=CompanyAliasKind.LEGAL_NAME,
            source_reference_id=observation.source_reference_id,
            confidence=ResolutionConfidence.HIGH,
            source_reference_ids=[observation.source_reference_id],
            now=now,
        )

        raw_company = observation.company_reference
        assert raw_company is not None
        observed_aliases_by_company_id[company.company_id].add(raw_company.legal_name)
        alias_kind = (
            CompanyAliasKind.LEGAL_NAME
            if raw_company.legal_name == company.legal_name
            else CompanyAliasKind.SOURCE_NAME
        )
        self._upsert_company_alias(
            company_aliases_by_id=company_aliases_by_id,
            company_id=company.company_id,
            alias_text=raw_company.legal_name,
            alias_kind=alias_kind,
            source_reference_id=observation.source_reference_id,
            confidence=ResolutionConfidence.HIGH,
            source_reference_ids=[observation.source_reference_id],
            now=now,
        )

        ticker_value = raw_company.ticker or company.ticker
        exchange_value = raw_company.exchange or company.exchange
        vendor_symbol = self._vendor_symbol_for_observation(
            observation=observation,
            workspace=workspace,
        )
        if ticker_value is not None:
            observed_tickers_by_company_id[company.company_id].add(ticker_value)
            self._upsert_ticker_alias(
                ticker_aliases_by_id=ticker_aliases_by_id,
                company_id=company.company_id,
                ticker=ticker_value,
                exchange=exchange_value,
                vendor_symbol=vendor_symbol,
                source_reference_id=observation.source_reference_id,
                confidence=ResolutionConfidence.HIGH,
                source_reference_ids=[observation.source_reference_id],
                now=now,
            )

        identifier_values = [
            (CrossSourceIdentifierKind.CIK, raw_company.cik, None),
            (CrossSourceIdentifierKind.FIGI, raw_company.figi, None),
            (CrossSourceIdentifierKind.ISIN, raw_company.isin, None),
            (CrossSourceIdentifierKind.LEI, raw_company.lei, None),
            (CrossSourceIdentifierKind.TICKER, ticker_value, exchange_value),
            (CrossSourceIdentifierKind.LEGAL_NAME, raw_company.legal_name, None),
            (CrossSourceIdentifierKind.VENDOR_SYMBOL, vendor_symbol, exchange_value),
        ]
        for identifier_kind, identifier_value, exchange in identifier_values:
            if identifier_value is None:
                continue
            cross_source_link_id = make_canonical_id(
                "xsrc",
                company.company_id,
                observation.source_reference_id,
                identifier_kind.value,
                identifier_value,
                exchange or "none",
            )
            cross_source_links_by_id[cross_source_link_id] = CrossSourceLink(
                cross_source_link_id=cross_source_link_id,
                company_id=company.company_id,
                source_type=observation.payload.source_type,
                identifier_kind=identifier_kind,
                identifier_value=identifier_value,
                exchange=exchange,
                source_reference_id=observation.source_reference_id,
                confidence=ResolutionConfidence.HIGH,
                active=True,
                provenance=build_provenance(
                    clock=self.clock,
                    transformation_name="day16_cross_source_link",
                    source_reference_ids=[observation.source_reference_id],
                    upstream_artifact_ids=[company.company_id],
                ),
                created_at=now,
                updated_at=now,
            )

    def _build_entity_references(
        self,
        *,
        workspace: LoadedEntityResolutionWorkspace,
        company_aliases_by_id: dict[str, CompanyAlias],
        ticker_aliases_by_id: dict[str, TickerAlias],
        cross_source_links_by_id: dict[str, CrossSourceLink],
        latest_decision_id_by_company_id: dict[str, str],
        source_reference_ids_by_company_id: dict[str, set[str]],
        now: datetime,
        company_id: str | None,
    ) -> list[EntityReference]:
        """Build one additive entity reference per canonical company."""

        entity_references: list[EntityReference] = []
        for company in sorted(workspace.companies_by_id.values(), key=lambda candidate: candidate.company_id):
            if company_id is not None and company.company_id != company_id:
                continue
            entity_reference_id = make_canonical_id("eref", company.company_id)
            entity_references.append(
                EntityReference(
                    entity_reference_id=entity_reference_id,
                    company_id=company.company_id,
                    legal_name=company.legal_name,
                    canonical_ticker=company.ticker,
                    exchange=company.exchange,
                    cik=company.cik,
                    isin=company.isin,
                    lei=company.lei,
                    figi=company.figi,
                    active=company.active,
                    company_alias_ids=sorted(
                        alias.company_alias_id
                        for alias in company_aliases_by_id.values()
                        if alias.company_id == company.company_id
                    ),
                    ticker_alias_ids=sorted(
                        alias.ticker_alias_id
                        for alias in ticker_aliases_by_id.values()
                        if alias.company_id == company.company_id
                    ),
                    cross_source_link_ids=sorted(
                        link.cross_source_link_id
                        for link in cross_source_links_by_id.values()
                        if link.company_id == company.company_id
                    ),
                    latest_resolution_decision_id=latest_decision_id_by_company_id.get(
                        company.company_id
                    ),
                    provenance=build_provenance(
                        clock=self.clock,
                        transformation_name="day16_entity_reference_aggregation",
                        source_reference_ids=sorted(source_reference_ids_by_company_id[company.company_id]),
                        upstream_artifact_ids=[company.company_id],
                    ),
                    created_at=now,
                    updated_at=now,
                )
            )
        return entity_references

    def _resolve_document(
        self,
        *,
        document: Document,
        workspace: LoadedEntityResolutionWorkspace,
        source_decisions_by_source_reference_id: dict[str, ResolutionDecision],
        alias_map: dict[str, set[str]],
        now: datetime,
    ) -> tuple[ResolutionDecision, list[ResolutionConflict], list[DocumentEntityLink]]:
        """Resolve one document to a canonical company, preserving ambiguity explicitly."""

        conflicts: list[ResolutionConflict] = []
        links: list[DocumentEntityLink] = []
        metadata_company_id = document.company_id
        source_decision = source_decisions_by_source_reference_id.get(document.source_reference_id)

        if metadata_company_id is not None and metadata_company_id not in workspace.companies_by_id:
            conflicts.append(
                self._build_conflict(
                    target_type="document",
                    target_id=document.document_id,
                    conflict_kind=ResolutionConflictKind.METADATA_MISMATCH,
                    candidate_company_ids=[metadata_company_id],
                    message="Document company_id did not resolve to a canonical company record.",
                    blocking=True,
                    source_reference_ids=[document.source_reference_id],
                    now=now,
                )
            )

        if (
            metadata_company_id is not None
            and source_decision is not None
            and source_decision.selected_company_id is not None
            and source_decision.selected_company_id != metadata_company_id
        ):
            conflicts.append(
                self._build_conflict(
                    target_type="document",
                    target_id=document.document_id,
                    conflict_kind=ResolutionConflictKind.METADATA_MISMATCH,
                    candidate_company_ids=sorted(
                        {metadata_company_id, source_decision.selected_company_id}
                    ),
                    message="Document metadata and source metadata resolved to different canonical companies.",
                    blocking=True,
                    source_reference_ids=[document.source_reference_id],
                    now=now,
                )
            )

        if conflicts:
            decision = self._build_resolution_decision(
                target_type="document",
                target_id=document.document_id,
                candidate_company_ids=sorted(
                    {
                        *([metadata_company_id] if metadata_company_id is not None else []),
                        *(
                            source_decision.candidate_company_ids
                            if source_decision is not None
                            else []
                        ),
                    }
                ),
                selected_company_id=None,
                status=ResolutionDecisionStatus.UNRESOLVED,
                confidence=ResolutionConfidence.UNRESOLVED,
                rule_name="document_metadata_conflict",
                rationale="Document and source metadata contradicted one another.",
                related_conflict_ids=[conflict.resolution_conflict_id for conflict in conflicts],
                source_reference_ids=[document.source_reference_id],
                now=now,
            )
            return decision, conflicts, links

        if metadata_company_id is not None and metadata_company_id in workspace.companies_by_id:
            parsing_conflict = self._build_parsing_conflict(
                document=document,
                company_id=metadata_company_id,
                workspace=workspace,
                now=now,
            )
            if parsing_conflict is not None:
                conflicts.append(parsing_conflict)
                decision = self._build_resolution_decision(
                    target_type="document",
                    target_id=document.document_id,
                    candidate_company_ids=sorted(
                        {
                            metadata_company_id,
                            *workspace.parsing_company_ids_by_document_id.get(
                                document.document_id,
                                set(),
                            ),
                        }
                    ),
                    selected_company_id=None,
                    status=ResolutionDecisionStatus.UNRESOLVED,
                    confidence=ResolutionConfidence.UNRESOLVED,
                    rule_name="document_company_id_parsing_conflict",
                    rationale=(
                        "Document metadata resolved canonically, but parsing artifacts "
                        "carried conflicting company identifiers."
                    ),
                    related_conflict_ids=[parsing_conflict.resolution_conflict_id],
                    source_reference_ids=[document.source_reference_id],
                    now=now,
                )
                return decision, conflicts, links
            decision = self._build_resolution_decision(
                target_type="document",
                target_id=document.document_id,
                candidate_company_ids=[metadata_company_id],
                selected_company_id=metadata_company_id,
                status=ResolutionDecisionStatus.RESOLVED,
                confidence=ResolutionConfidence.HIGH,
                rule_name="document_company_id",
                rationale="Document metadata already carried one canonical company_id.",
                related_conflict_ids=[],
                source_reference_ids=[document.source_reference_id],
                now=now,
            )
            links.append(
                self._build_document_link(
                    document=document,
                    company_id=metadata_company_id,
                    link_scope=DocumentEntityLinkScope.DOCUMENT_METADATA,
                    resolution_decision_id=decision.resolution_decision_id,
                    confidence=ResolutionConfidence.HIGH,
                    mention_text=None,
                    segment_id=None,
                    evidence_span_ids=[],
                    now=now,
                )
            )
            links.extend(
                self._build_evidence_inherited_links(
                    document=document,
                    company_id=metadata_company_id,
                    decision=decision,
                    workspace=workspace,
                    now=now,
                )
            )
            return decision, conflicts, links

        if source_decision is not None:
            if source_decision.status is ResolutionDecisionStatus.RESOLVED:
                assert source_decision.selected_company_id is not None
                parsing_conflict = self._build_parsing_conflict(
                    document=document,
                    company_id=source_decision.selected_company_id,
                    workspace=workspace,
                    now=now,
                )
                if parsing_conflict is not None:
                    conflicts.append(parsing_conflict)
                    decision = self._build_resolution_decision(
                        target_type="document",
                        target_id=document.document_id,
                        candidate_company_ids=sorted(
                            {
                                *source_decision.candidate_company_ids,
                                *workspace.parsing_company_ids_by_document_id.get(
                                    document.document_id,
                                    set(),
                                ),
                            }
                        ),
                        selected_company_id=None,
                        status=ResolutionDecisionStatus.UNRESOLVED,
                        confidence=ResolutionConfidence.UNRESOLVED,
                        rule_name="source_metadata_parsing_conflict",
                        rationale=(
                            "Source metadata resolved canonically, but parsing artifacts "
                            "carried conflicting company identifiers."
                        ),
                        related_conflict_ids=[parsing_conflict.resolution_conflict_id],
                        source_reference_ids=[document.source_reference_id],
                        now=now,
                    )
                    return decision, conflicts, links
                decision = self._build_resolution_decision(
                    target_type="document",
                    target_id=document.document_id,
                    candidate_company_ids=source_decision.candidate_company_ids,
                    selected_company_id=source_decision.selected_company_id,
                    status=ResolutionDecisionStatus.RESOLVED,
                    confidence=source_decision.confidence,
                    rule_name="source_metadata",
                    rationale="Document resolved from source-carried company metadata.",
                    related_conflict_ids=[],
                    source_reference_ids=[document.source_reference_id],
                    now=now,
                )
                links.append(
                    self._build_document_link(
                        document=document,
                        company_id=source_decision.selected_company_id,
                        link_scope=DocumentEntityLinkScope.DOCUMENT_METADATA,
                        resolution_decision_id=decision.resolution_decision_id,
                        confidence=source_decision.confidence,
                        mention_text=None,
                        segment_id=None,
                        evidence_span_ids=[],
                        now=now,
                    )
                )
                links.extend(
                    self._build_evidence_inherited_links(
                        document=document,
                        company_id=source_decision.selected_company_id,
                        decision=decision,
                        workspace=workspace,
                        now=now,
                    )
                )
                return decision, conflicts, links
            if source_decision.status is ResolutionDecisionStatus.AMBIGUOUS:
                conflicts.append(
                    self._build_conflict(
                        target_type="document",
                        target_id=document.document_id,
                        conflict_kind=ResolutionConflictKind.MULTIPLE_CANDIDATES,
                        candidate_company_ids=source_decision.candidate_company_ids,
                        message="Source-carried company metadata matched multiple canonical companies.",
                        blocking=True,
                        source_reference_ids=[document.source_reference_id],
                        now=now,
                    )
                )
                decision = self._build_resolution_decision(
                    target_type="document",
                    target_id=document.document_id,
                    candidate_company_ids=source_decision.candidate_company_ids,
                    selected_company_id=None,
                    status=ResolutionDecisionStatus.AMBIGUOUS,
                    confidence=ResolutionConfidence.AMBIGUOUS,
                    rule_name="source_metadata_ambiguous",
                    rationale="Source metadata remained ambiguous after exact matching.",
                    related_conflict_ids=[conflicts[0].resolution_conflict_id],
                    source_reference_ids=[document.source_reference_id],
                    now=now,
                )
                return decision, conflicts, links

        title_text = document.title
        headline_text = title_text
        if isinstance(document, NewsItem):
            headline_text = document.headline
        headline_outcome = match_text_against_aliases(
            text=headline_text,
            alias_map=alias_map,
            rule_name="headline_alias_unique",
            confidence=ResolutionConfidence.MEDIUM,
            rationale="Document headline or title matched one preserved alias exactly.",
        )
        if headline_outcome.status is ResolutionDecisionStatus.RESOLVED:
            assert headline_outcome.selected_company_id is not None
            parsing_conflict = self._build_parsing_conflict(
                document=document,
                company_id=headline_outcome.selected_company_id,
                workspace=workspace,
                now=now,
            )
            if parsing_conflict is not None:
                conflicts.append(parsing_conflict)
                decision = self._build_resolution_decision(
                    target_type="document",
                    target_id=document.document_id,
                    candidate_company_ids=sorted(
                        {
                            *headline_outcome.candidate_company_ids,
                            *workspace.parsing_company_ids_by_document_id.get(
                                document.document_id,
                                set(),
                            ),
                        }
                    ),
                    selected_company_id=None,
                    status=ResolutionDecisionStatus.UNRESOLVED,
                    confidence=ResolutionConfidence.UNRESOLVED,
                    rule_name="headline_alias_unique_parsing_conflict",
                    rationale=(
                        "A unique headline alias matched, but parsing artifacts "
                        "carried conflicting company identifiers."
                    ),
                    related_conflict_ids=[parsing_conflict.resolution_conflict_id],
                    source_reference_ids=[document.source_reference_id],
                    now=now,
                )
                return decision, conflicts, links
            decision = self._build_resolution_decision(
                target_type="document",
                target_id=document.document_id,
                candidate_company_ids=headline_outcome.candidate_company_ids,
                selected_company_id=headline_outcome.selected_company_id,
                status=headline_outcome.status,
                confidence=headline_outcome.confidence,
                rule_name=headline_outcome.rule_name,
                rationale=headline_outcome.rationale,
                related_conflict_ids=[],
                source_reference_ids=[document.source_reference_id],
                now=now,
            )
            links.append(
                self._build_document_link(
                    document=document,
                    company_id=headline_outcome.selected_company_id,
                    link_scope=DocumentEntityLinkScope.HEADLINE_MENTION,
                    resolution_decision_id=decision.resolution_decision_id,
                    confidence=headline_outcome.confidence,
                    mention_text=headline_outcome.matched_aliases[0],
                    segment_id=None,
                    evidence_span_ids=[],
                    now=now,
                )
            )
            links.extend(
                self._build_evidence_inherited_links(
                    document=document,
                    company_id=headline_outcome.selected_company_id,
                    decision=decision,
                    workspace=workspace,
                    now=now,
                )
            )
            return decision, conflicts, links
        if headline_outcome.status is ResolutionDecisionStatus.AMBIGUOUS:
            conflicts.append(
                self._build_conflict(
                    target_type="document",
                    target_id=document.document_id,
                    conflict_kind=ResolutionConflictKind.ALIAS_COLLISION,
                    candidate_company_ids=headline_outcome.candidate_company_ids,
                    message="Headline or title matched more than one preserved alias exactly.",
                    blocking=True,
                    source_reference_ids=[document.source_reference_id],
                    now=now,
                )
            )
            decision = self._build_resolution_decision(
                target_type="document",
                target_id=document.document_id,
                candidate_company_ids=headline_outcome.candidate_company_ids,
                selected_company_id=None,
                status=ResolutionDecisionStatus.AMBIGUOUS,
                confidence=ResolutionConfidence.AMBIGUOUS,
                rule_name=headline_outcome.rule_name,
                rationale=headline_outcome.rationale,
                related_conflict_ids=[conflicts[0].resolution_conflict_id],
                source_reference_ids=[document.source_reference_id],
                now=now,
            )
            return decision, conflicts, links

        parsed_text = workspace.parsed_texts_by_document_id.get(document.document_id)
        if parsed_text is not None:
            body_outcome = match_text_against_aliases(
                text=parsed_text.canonical_text,
                alias_map=alias_map,
                rule_name="body_alias_unique",
                confidence=ResolutionConfidence.LOW,
                rationale="Parser-owned body text matched one preserved alias exactly.",
            )
            if body_outcome.status is ResolutionDecisionStatus.RESOLVED:
                assert body_outcome.selected_company_id is not None
                parsing_conflict = self._build_parsing_conflict(
                    document=document,
                    company_id=body_outcome.selected_company_id,
                    workspace=workspace,
                    now=now,
                )
                if parsing_conflict is not None:
                    conflicts.append(parsing_conflict)
                    decision = self._build_resolution_decision(
                        target_type="document",
                        target_id=document.document_id,
                        candidate_company_ids=sorted(
                            {
                                *body_outcome.candidate_company_ids,
                                *workspace.parsing_company_ids_by_document_id.get(
                                    document.document_id,
                                    set(),
                                ),
                            }
                        ),
                        selected_company_id=None,
                        status=ResolutionDecisionStatus.UNRESOLVED,
                        confidence=ResolutionConfidence.UNRESOLVED,
                        rule_name="body_alias_unique_parsing_conflict",
                        rationale=(
                            "A unique body-text alias matched, but parsing artifacts "
                            "carried conflicting company identifiers."
                        ),
                        related_conflict_ids=[parsing_conflict.resolution_conflict_id],
                        source_reference_ids=[document.source_reference_id],
                        now=now,
                    )
                    return decision, conflicts, links
                decision = self._build_resolution_decision(
                    target_type="document",
                    target_id=document.document_id,
                    candidate_company_ids=body_outcome.candidate_company_ids,
                    selected_company_id=body_outcome.selected_company_id,
                    status=body_outcome.status,
                    confidence=body_outcome.confidence,
                    rule_name=body_outcome.rule_name,
                    rationale=body_outcome.rationale,
                    related_conflict_ids=[],
                    source_reference_ids=[document.source_reference_id],
                    now=now,
                )
                links.append(
                    self._build_document_link(
                        document=document,
                        company_id=body_outcome.selected_company_id,
                        link_scope=DocumentEntityLinkScope.BODY_MENTION,
                        resolution_decision_id=decision.resolution_decision_id,
                        confidence=body_outcome.confidence,
                        mention_text=body_outcome.matched_aliases[0],
                        segment_id=None,
                        evidence_span_ids=[],
                        now=now,
                    )
                )
                links.extend(
                    self._build_evidence_inherited_links(
                        document=document,
                        company_id=body_outcome.selected_company_id,
                        decision=decision,
                        workspace=workspace,
                        now=now,
                    )
                )
                return decision, conflicts, links
            if body_outcome.status is ResolutionDecisionStatus.AMBIGUOUS:
                conflicts.append(
                    self._build_conflict(
                        target_type="document",
                        target_id=document.document_id,
                        conflict_kind=ResolutionConflictKind.ALIAS_COLLISION,
                        candidate_company_ids=body_outcome.candidate_company_ids,
                        message="Body text matched more than one preserved alias exactly.",
                        blocking=True,
                        source_reference_ids=[document.source_reference_id],
                        now=now,
                    )
                )
                decision = self._build_resolution_decision(
                    target_type="document",
                    target_id=document.document_id,
                    candidate_company_ids=body_outcome.candidate_company_ids,
                    selected_company_id=None,
                    status=ResolutionDecisionStatus.AMBIGUOUS,
                    confidence=ResolutionConfidence.AMBIGUOUS,
                    rule_name=body_outcome.rule_name,
                    rationale=body_outcome.rationale,
                    related_conflict_ids=[conflicts[0].resolution_conflict_id],
                    source_reference_ids=[document.source_reference_id],
                    now=now,
                )
                return decision, conflicts, links

        conflicts.append(
            self._build_conflict(
                target_type="document",
                target_id=document.document_id,
                conflict_kind=ResolutionConflictKind.MISSING_METADATA,
                candidate_company_ids=[],
                message="Document had no canonical company metadata and no unique preserved-alias match.",
                blocking=True,
                source_reference_ids=[document.source_reference_id],
                now=now,
            )
        )
        decision = self._build_resolution_decision(
            target_type="document",
            target_id=document.document_id,
            candidate_company_ids=[],
            selected_company_id=None,
            status=ResolutionDecisionStatus.UNRESOLVED,
            confidence=ResolutionConfidence.UNRESOLVED,
            rule_name="no_document_entity_match",
            rationale="No canonical metadata or unique preserved-alias match resolved this document.",
            related_conflict_ids=[conflicts[0].resolution_conflict_id],
            source_reference_ids=[document.source_reference_id],
            now=now,
        )
        return decision, conflicts, links

    def _build_evidence_inherited_links(
        self,
        *,
        document: Document,
        company_id: str,
        decision: ResolutionDecision,
        workspace: LoadedEntityResolutionWorkspace,
        now: datetime,
    ) -> list[DocumentEntityLink]:
        """Build inherited evidence links when parsing artifacts remain consistent."""

        evidence_spans = workspace.evidence_spans_by_document_id.get(document.document_id, [])
        if not evidence_spans:
            return []
        return [
            self._build_document_link(
                document=document,
                company_id=company_id,
                link_scope=DocumentEntityLinkScope.EVIDENCE_INHERITED,
                resolution_decision_id=decision.resolution_decision_id,
                confidence=decision.confidence,
                mention_text=None,
                segment_id=None,
                evidence_span_ids=[span.evidence_span_id for span in evidence_spans],
                now=now,
            )
        ]

    def _build_parsing_conflict(
        self,
        *,
        document: Document,
        company_id: str,
        workspace: LoadedEntityResolutionWorkspace,
        now: datetime,
    ) -> ResolutionConflict | None:
        """Build an explicit blocking conflict when parsing company_ids disagree."""

        parsing_company_ids = workspace.parsing_company_ids_by_document_id.get(
            document.document_id,
            set(),
        )
        if not parsing_company_ids or parsing_company_ids == {company_id}:
            return None
        return self._build_conflict(
            target_type="document",
            target_id=document.document_id,
            conflict_kind=ResolutionConflictKind.METADATA_MISMATCH,
            candidate_company_ids=sorted({company_id, *parsing_company_ids}),
            message=(
                "Parsing artifacts carried conflicting company_ids for an otherwise "
                "resolved document."
            ),
            blocking=True,
            source_reference_ids=[document.source_reference_id],
            now=now,
        )

    def _build_document_link(
        self,
        *,
        document: Document,
        company_id: str,
        link_scope: DocumentEntityLinkScope,
        resolution_decision_id: str,
        confidence: ResolutionConfidence,
        mention_text: str | None,
        segment_id: str | None,
        evidence_span_ids: list[str],
        now: datetime,
    ) -> DocumentEntityLink:
        """Build one document-level entity link."""

        entity_reference_id = make_canonical_id("eref", company_id)
        return DocumentEntityLink(
            document_entity_link_id=make_canonical_id(
                "dlink",
                document.document_id,
                company_id,
                link_scope.value,
                mention_text or "none",
            ),
            document_id=document.document_id,
            source_reference_id=document.source_reference_id,
            company_id=company_id,
            entity_reference_id=entity_reference_id,
            link_scope=link_scope,
            mention_text=mention_text,
            segment_id=segment_id,
            evidence_span_ids=evidence_span_ids,
            resolution_decision_id=resolution_decision_id,
            confidence=confidence,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="day16_document_entity_link",
                source_reference_ids=[document.source_reference_id],
                upstream_artifact_ids=[document.document_id, company_id],
            ),
            created_at=now,
            updated_at=now,
        )

    def _build_resolution_decision(
        self,
        *,
        target_type: str,
        target_id: str,
        candidate_company_ids: list[str],
        selected_company_id: str | None,
        status: ResolutionDecisionStatus,
        confidence: ResolutionConfidence,
        rule_name: str,
        rationale: str,
        related_conflict_ids: list[str],
        source_reference_ids: list[str],
        now: datetime,
    ) -> ResolutionDecision:
        """Build one typed resolution decision."""

        return ResolutionDecision(
            resolution_decision_id=make_canonical_id(
                "rdec",
                target_type,
                target_id,
                rule_name,
                status.value,
                selected_company_id or "none",
                *candidate_company_ids,
            ),
            target_type=target_type,
            target_id=target_id,
            candidate_company_ids=candidate_company_ids,
            selected_company_id=selected_company_id,
            status=status,
            confidence=confidence,
            rule_name=rule_name,
            rationale=rationale,
            related_conflict_ids=related_conflict_ids,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="day16_resolution_decision",
                source_reference_ids=source_reference_ids,
                upstream_artifact_ids=[target_id, *candidate_company_ids],
            ),
            created_at=now,
            updated_at=now,
        )

    def _build_conflict(
        self,
        *,
        target_type: str,
        target_id: str,
        conflict_kind: ResolutionConflictKind,
        candidate_company_ids: list[str],
        message: str,
        blocking: bool,
        source_reference_ids: list[str],
        now: datetime,
    ) -> ResolutionConflict:
        """Build one explicit resolution conflict."""

        return ResolutionConflict(
            resolution_conflict_id=make_canonical_id(
                "rconf",
                target_type,
                target_id,
                conflict_kind.value,
                message,
                *candidate_company_ids,
            ),
            target_type=target_type,
            target_id=target_id,
            conflict_kind=conflict_kind,
            candidate_company_ids=candidate_company_ids,
            message=message,
            blocking=blocking,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="day16_resolution_conflict",
                source_reference_ids=source_reference_ids,
                upstream_artifact_ids=[target_id, *candidate_company_ids],
            ),
            created_at=now,
            updated_at=now,
        )

    def _upsert_company_alias(
        self,
        *,
        company_aliases_by_id: dict[str, CompanyAlias],
        company_id: str,
        alias_text: str,
        alias_kind: CompanyAliasKind,
        source_reference_id: str | None,
        confidence: ResolutionConfidence,
        source_reference_ids: list[str],
        now: datetime,
    ) -> None:
        """Insert or replace one preserved company alias deterministically."""

        alias_id = make_canonical_id(
            "calias",
            company_id,
            alias_kind.value,
            alias_text,
            source_reference_id or "none",
        )
        company_aliases_by_id[alias_id] = CompanyAlias(
            company_alias_id=alias_id,
            company_id=company_id,
            alias_text=alias_text,
            alias_kind=alias_kind,
            valid_from=None,
            valid_to=None,
            source_reference_id=source_reference_id,
            confidence=confidence,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="day16_company_alias",
                source_reference_ids=source_reference_ids,
                upstream_artifact_ids=[company_id],
            ),
            created_at=now,
            updated_at=now,
        )

    def _upsert_ticker_alias(
        self,
        *,
        ticker_aliases_by_id: dict[str, TickerAlias],
        company_id: str,
        ticker: str,
        exchange: str | None,
        vendor_symbol: str | None,
        source_reference_id: str | None,
        confidence: ResolutionConfidence,
        source_reference_ids: list[str],
        now: datetime,
    ) -> None:
        """Insert or replace one preserved ticker alias deterministically."""

        alias_id = make_canonical_id(
            "talias",
            company_id,
            ticker,
            exchange or "none",
            vendor_symbol or "none",
            source_reference_id or "none",
        )
        ticker_aliases_by_id[alias_id] = TickerAlias(
            ticker_alias_id=alias_id,
            company_id=company_id,
            ticker=ticker,
            exchange=exchange,
            vendor_symbol=vendor_symbol,
            active=True,
            valid_from=None,
            valid_to=None,
            source_reference_id=source_reference_id,
            confidence=confidence,
            provenance=build_provenance(
                clock=self.clock,
                transformation_name="day16_ticker_alias",
                source_reference_ids=source_reference_ids,
                upstream_artifact_ids=[company_id],
            ),
            created_at=now,
            updated_at=now,
        )

    def _vendor_symbol_for_observation(
        self,
        *,
        observation: RawSourceObservation,
        workspace: LoadedEntityResolutionWorkspace,
    ) -> str | None:
        """Return the best vendor symbol observed for one source reference when available."""

        if isinstance(observation.payload, RawPriceSeriesMetadataFixture):
            return observation.payload.vendor_symbol
        price_metadata = workspace.price_series_metadata_by_source_reference_id.get(
            observation.source_reference_id,
            [],
        )
        for metadata in price_metadata:
            if metadata.vendor_symbol is not None:
                return metadata.vendor_symbol
        return None

    def _source_unresolved_conflict_kind(
        self,
        *,
        company_reference: RawCompanyReference,
    ) -> ResolutionConflictKind:
        """Choose the most honest unresolved-conflict label for one source observation."""

        if any(
            [
                company_reference.cik,
                company_reference.figi,
                company_reference.isin,
                company_reference.lei,
                company_reference.ticker and company_reference.exchange,
            ]
        ):
            return ResolutionConflictKind.METADATA_MISMATCH
        return ResolutionConflictKind.MISSING_METADATA
