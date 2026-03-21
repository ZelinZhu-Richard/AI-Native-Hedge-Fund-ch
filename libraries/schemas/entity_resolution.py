from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from libraries.schemas.base import ProvenanceRecord, SourceType, TimestampedModel


class ResolutionConfidence(StrEnum):
    """Confidence label for deterministic entity-resolution outcomes."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class CompanyAliasKind(StrEnum):
    """Kinds of preserved company-name aliases."""

    LEGAL_NAME = "legal_name"
    FORMER_NAME = "former_name"
    SOURCE_NAME = "source_name"
    TRADE_NAME = "trade_name"


class DocumentEntityLinkScope(StrEnum):
    """How a document-level entity link was established."""

    DOCUMENT_METADATA = "document_metadata"
    HEADLINE_MENTION = "headline_mention"
    BODY_MENTION = "body_mention"
    EVIDENCE_INHERITED = "evidence_inherited"


class CrossSourceIdentifierKind(StrEnum):
    """Identifier categories used for cross-source linking."""

    CIK = "cik"
    ISIN = "isin"
    LEI = "lei"
    FIGI = "figi"
    TICKER = "ticker"
    LEGAL_NAME = "legal_name"
    VENDOR_SYMBOL = "vendor_symbol"


class ResolutionDecisionStatus(StrEnum):
    """Lifecycle state for one deterministic resolution decision."""

    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class ResolutionConflictKind(StrEnum):
    """Kinds of explicit entity-resolution conflicts."""

    MULTIPLE_CANDIDATES = "multiple_candidates"
    METADATA_MISMATCH = "metadata_mismatch"
    ALIAS_COLLISION = "alias_collision"
    MISSING_METADATA = "missing_metadata"


class EntityReference(TimestampedModel):
    """Canonical company-facing entity reference used by downstream services."""

    entity_reference_id: str = Field(description="Canonical entity-reference identifier.")
    company_id: str = Field(description="Canonical company identifier.")
    entity_kind: Literal["company"] = Field(
        default="company",
        description="Entity kind carried by this reference.",
    )
    legal_name: str = Field(description="Canonical legal name for the company.")
    canonical_ticker: str | None = Field(
        default=None,
        description="Primary canonical ticker when available.",
    )
    exchange: str | None = Field(default=None, description="Primary exchange when available.")
    cik: str | None = Field(default=None, description="SEC Central Index Key when available.")
    isin: str | None = Field(default=None, description="ISIN identifier when available.")
    lei: str | None = Field(default=None, description="LEI identifier when available.")
    figi: str | None = Field(default=None, description="FIGI identifier when available.")
    active: bool = Field(default=True, description="Whether the canonical entity is active.")
    company_alias_ids: list[str] = Field(
        default_factory=list,
        description="Preserved company-alias identifiers linked to the entity.",
    )
    ticker_alias_ids: list[str] = Field(
        default_factory=list,
        description="Preserved ticker-alias identifiers linked to the entity.",
    )
    cross_source_link_ids: list[str] = Field(
        default_factory=list,
        description="Cross-source identifier links attached to the entity.",
    )
    latest_resolution_decision_id: str | None = Field(
        default=None,
        description="Most recent deterministic resolution decision linked to the entity.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the entity reference.")


class CompanyAlias(TimestampedModel):
    """Preserved company-name alias attached to one canonical company."""

    company_alias_id: str = Field(description="Canonical company-alias identifier.")
    company_id: str = Field(description="Canonical company identifier.")
    alias_text: str = Field(description="Observed company-name alias text.")
    alias_kind: CompanyAliasKind = Field(description="Meaning of the preserved alias.")
    valid_from: datetime | None = Field(
        default=None,
        description="Optional UTC timestamp when the alias became valid.",
    )
    valid_to: datetime | None = Field(
        default=None,
        description="Optional UTC timestamp when the alias stopped being valid.",
    )
    source_reference_id: str | None = Field(
        default=None,
        description="Source reference that exposed the alias when applicable.",
    )
    confidence: ResolutionConfidence = Field(description="Confidence in the alias attachment.")
    provenance: ProvenanceRecord = Field(description="Traceability for the alias record.")

    @model_validator(mode="after")
    def validate_validity_window(self) -> Self:
        """Ensure alias validity windows remain internally coherent."""

        if self.valid_from is not None and self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to must be greater than or equal to valid_from.")
        return self


class TickerAlias(TimestampedModel):
    """Preserved ticker or vendor symbol attached to one canonical company."""

    ticker_alias_id: str = Field(description="Canonical ticker-alias identifier.")
    company_id: str = Field(description="Canonical company identifier.")
    ticker: str = Field(description="Observed ticker or tradable symbol.")
    exchange: str | None = Field(default=None, description="Observed exchange when available.")
    vendor_symbol: str | None = Field(
        default=None,
        description="Vendor-specific symbol when distinct from ticker.",
    )
    active: bool = Field(default=True, description="Whether the alias is currently active.")
    valid_from: datetime | None = Field(
        default=None,
        description="Optional UTC timestamp when the ticker alias became valid.",
    )
    valid_to: datetime | None = Field(
        default=None,
        description="Optional UTC timestamp when the ticker alias stopped being valid.",
    )
    source_reference_id: str | None = Field(
        default=None,
        description="Source reference that exposed the ticker alias when applicable.",
    )
    confidence: ResolutionConfidence = Field(description="Confidence in the ticker attachment.")
    provenance: ProvenanceRecord = Field(description="Traceability for the ticker alias.")

    @model_validator(mode="after")
    def validate_validity_window(self) -> Self:
        """Ensure ticker validity windows remain internally coherent."""

        if self.valid_from is not None and self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to must be greater than or equal to valid_from.")
        return self


class DocumentEntityLink(TimestampedModel):
    """Explicit link from one document or its evidence to a canonical entity."""

    document_entity_link_id: str = Field(description="Canonical document-entity-link identifier.")
    document_id: str = Field(description="Canonical document identifier.")
    source_reference_id: str = Field(description="Source reference backing the document.")
    company_id: str = Field(description="Canonical company identifier.")
    entity_reference_id: str = Field(description="Canonical entity-reference identifier.")
    link_scope: DocumentEntityLinkScope = Field(
        description="How this document-level entity link was established."
    )
    mention_text: str | None = Field(
        default=None,
        description="Observed mention text when the link came from title, headline, or body text.",
    )
    segment_id: str | None = Field(
        default=None,
        description="Parser-owned segment identifier when the link comes from one segment.",
    )
    evidence_span_ids: list[str] = Field(
        default_factory=list,
        description="Evidence spans inherited by this link when applicable.",
    )
    resolution_decision_id: str = Field(description="Resolution decision that justified the link.")
    confidence: ResolutionConfidence = Field(description="Confidence in the document entity link.")
    provenance: ProvenanceRecord = Field(description="Traceability for the link.")

    @model_validator(mode="after")
    def validate_scope_requirements(self) -> Self:
        """Require explicit inherited evidence when the link scope says so."""

        if self.link_scope is DocumentEntityLinkScope.EVIDENCE_INHERITED and not self.evidence_span_ids:
            raise ValueError("evidence_inherited links must reference at least one evidence span.")
        return self


class CrossSourceLink(TimestampedModel):
    """Cross-source identifier attached to one canonical company."""

    cross_source_link_id: str = Field(description="Canonical cross-source-link identifier.")
    company_id: str = Field(description="Canonical company identifier.")
    source_type: SourceType = Field(description="Source family that carried the identifier.")
    identifier_kind: CrossSourceIdentifierKind = Field(
        description="Identifier category carried by the source."
    )
    identifier_value: str = Field(description="Observed identifier value.")
    exchange: str | None = Field(
        default=None,
        description="Observed exchange when relevant for symbol-level identifiers.",
    )
    source_reference_id: str | None = Field(
        default=None,
        description="Source reference that carried the identifier when applicable.",
    )
    confidence: ResolutionConfidence = Field(description="Confidence in the identifier attachment.")
    active: bool = Field(default=True, description="Whether the cross-source link is active.")
    provenance: ProvenanceRecord = Field(description="Traceability for the cross-source link.")


class ResolutionConflict(TimestampedModel):
    """Explicit conflict emitted when entity resolution cannot remain trustworthy."""

    resolution_conflict_id: str = Field(description="Canonical resolution-conflict identifier.")
    target_type: str = Field(description="Type of target that encountered the conflict.")
    target_id: str = Field(description="Identifier of the target that encountered the conflict.")
    conflict_kind: ResolutionConflictKind = Field(description="Kind of explicit conflict detected.")
    candidate_company_ids: list[str] = Field(
        default_factory=list,
        description="Canonical company candidates implicated in the conflict.",
    )
    message: str = Field(description="Human-readable explanation of the conflict.")
    blocking: bool = Field(description="Whether the conflict should block confident resolution.")
    provenance: ProvenanceRecord = Field(description="Traceability for the conflict.")

    @model_validator(mode="after")
    def validate_candidate_requirements(self) -> Self:
        """Require multiple candidates for multi-candidate conflict kinds."""

        if (
            self.conflict_kind in {ResolutionConflictKind.MULTIPLE_CANDIDATES, ResolutionConflictKind.ALIAS_COLLISION}
            and len(self.candidate_company_ids) < 2
        ):
            raise ValueError("Multiple-candidate conflicts must include at least two candidates.")
        return self


class ResolutionDecision(TimestampedModel):
    """Deterministic decision that resolved, left ambiguous, or left unresolved one target."""

    resolution_decision_id: str = Field(description="Canonical resolution-decision identifier.")
    target_type: str = Field(description="Type of entity or artifact being resolved.")
    target_id: str = Field(description="Identifier of the entity or artifact being resolved.")
    candidate_company_ids: list[str] = Field(
        default_factory=list,
        description="Canonical company candidates considered by the resolver.",
    )
    selected_company_id: str | None = Field(
        default=None,
        description="Selected canonical company when the decision resolved cleanly.",
    )
    status: ResolutionDecisionStatus = Field(description="Outcome of the deterministic resolution.")
    confidence: ResolutionConfidence = Field(description="Confidence label for the decision.")
    rule_name: str = Field(description="Deterministic rule that produced the outcome.")
    rationale: str = Field(description="Short explanation of why the rule led to this result.")
    related_conflict_ids: list[str] = Field(
        default_factory=list,
        description="Explicit conflicts linked to the decision when applicable.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the resolution decision.")

    @model_validator(mode="after")
    def validate_status_and_confidence(self) -> Self:
        """Keep decision status, selected company, and confidence internally coherent."""

        if self.status is ResolutionDecisionStatus.RESOLVED:
            if self.selected_company_id is None:
                raise ValueError("Resolved decisions must include a selected_company_id.")
            if self.confidence in {
                ResolutionConfidence.AMBIGUOUS,
                ResolutionConfidence.UNRESOLVED,
            }:
                raise ValueError("Resolved decisions must use high, medium, or low confidence.")
        if self.status is ResolutionDecisionStatus.AMBIGUOUS:
            if self.selected_company_id is not None:
                raise ValueError("Ambiguous decisions must not select one company.")
            if len(self.candidate_company_ids) < 2:
                raise ValueError("Ambiguous decisions must include at least two candidates.")
            if self.confidence is not ResolutionConfidence.AMBIGUOUS:
                raise ValueError("Ambiguous decisions must use ambiguous confidence.")
        if self.status is ResolutionDecisionStatus.UNRESOLVED:
            if self.selected_company_id is not None:
                raise ValueError("Unresolved decisions must not select one company.")
            if self.confidence is not ResolutionConfidence.UNRESOLVED:
                raise ValueError("Unresolved decisions must use unresolved confidence.")
        return self
