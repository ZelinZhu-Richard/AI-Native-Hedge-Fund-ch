from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from libraries.schemas.base import DocumentKind, ProvenanceRecord, StrictModel


class MemoryScope(StrEnum):
    """Searchable artifact scopes supported by the Day 18 memory layer."""

    EVIDENCE = "evidence"
    EVIDENCE_ASSESSMENT = "evidence_assessment"
    HYPOTHESIS = "hypothesis"
    COUNTER_HYPOTHESIS = "counter_hypothesis"
    RESEARCH_BRIEF = "research_brief"
    MEMO = "memo"
    EXPERIMENT = "experiment"
    REVIEW_NOTE = "review_note"


class ResearchArtifactReference(StrictModel):
    """Stable reference to one real persisted research-memory artifact."""

    research_artifact_reference_id: str = Field(
        description="Canonical retrieval reference identifier."
    )
    scope: MemoryScope = Field(description="Top-level memory scope for the artifact.")
    artifact_type: str = Field(description="Concrete artifact model name.")
    artifact_id: str = Field(description="Concrete artifact identifier.")
    storage_uri: str = Field(description="Real URI to the stored artifact payload.")
    company_id: str | None = Field(
        default=None,
        description="Canonical company identifier when the artifact resolves cleanly to one company.",
    )
    document_id: str | None = Field(
        default=None,
        description="Concrete document identifier when document lineage resolves to one document.",
    )
    document_kind: DocumentKind | None = Field(
        default=None,
        description="Resolved document kind when lineage is concrete enough to determine one.",
    )
    primary_timestamp: datetime = Field(
        description="Primary time used for search filtering and ordering."
    )
    title: str | None = Field(
        default=None,
        description="Short title for display when the artifact exposes one.",
    )
    summary: str | None = Field(
        default=None,
        description="Short summary or excerpt for display when one is derivable.",
    )
    source_reference_ids: list[str] = Field(
        default_factory=list,
        description="Source references attached to the stored artifact provenance.",
    )
    provenance: ProvenanceRecord = Field(
        description="Traceability for how the reference was assembled."
    )

    @model_validator(mode="after")
    def validate_reference(self) -> ResearchArtifactReference:
        """Require explicit real-artifact linkage."""

        if not self.research_artifact_reference_id:
            raise ValueError("research_artifact_reference_id must be non-empty.")
        if not self.artifact_type:
            raise ValueError("artifact_type must be non-empty.")
        if not self.artifact_id:
            raise ValueError("artifact_id must be non-empty.")
        if not self.storage_uri:
            raise ValueError("storage_uri must be non-empty.")
        return self


class RetrievalQuery(StrictModel):
    """Structured metadata-first query over persisted research artifacts."""

    retrieval_query_id: str = Field(description="Canonical retrieval-query identifier.")
    scopes: list[MemoryScope] = Field(
        default_factory=list,
        description="Memory scopes included in the search.",
    )
    company_id: str | None = Field(
        default=None,
        description="Canonical company identifier filter when one company is targeted.",
    )
    document_kinds: list[DocumentKind] = Field(
        default_factory=list,
        description="Optional document-kind filters when document lineage is available.",
    )
    artifact_types: list[str] = Field(
        default_factory=list,
        description="Optional concrete artifact-type filters.",
    )
    keyword_terms: list[str] = Field(
        default_factory=list,
        description="Case-insensitive substring terms matched against explicit searchable fields.",
    )
    time_start: datetime | None = Field(
        default=None,
        description="Inclusive lower bound for the primary timestamp filter.",
    )
    time_end: datetime | None = Field(
        default=None,
        description="Inclusive upper bound for the primary timestamp filter.",
    )
    metadata_filters: dict[str, str] = Field(
        default_factory=dict,
        description="Exact-match metadata filters over supported scalar fields.",
    )
    limit: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Maximum number of matching artifacts returned across all scopes.",
    )

    @model_validator(mode="after")
    def validate_query(self) -> RetrievalQuery:
        """Require a coherent bounded query."""

        if not self.retrieval_query_id:
            raise ValueError("retrieval_query_id must be non-empty.")
        if not self.scopes:
            raise ValueError("scopes must contain at least one memory scope.")
        if self.time_start is not None and self.time_end is not None and self.time_end < self.time_start:
            raise ValueError("time_end must be greater than or equal to time_start.")
        if any(not artifact_type for artifact_type in self.artifact_types):
            raise ValueError("artifact_types must not contain empty values.")
        if any(not keyword_term for keyword_term in self.keyword_terms):
            raise ValueError("keyword_terms must not contain empty values.")
        if any(not key or not value for key, value in self.metadata_filters.items()):
            raise ValueError("metadata_filters keys and values must be non-empty.")
        return self


class RetrievalResult(StrictModel):
    """Structured search result for one non-evidence artifact."""

    retrieval_result_id: str = Field(description="Canonical retrieval-result identifier.")
    artifact_reference: ResearchArtifactReference = Field(
        description="Reference to the matching stored artifact."
    )
    scope: MemoryScope = Field(description="Scope returned by the match.")
    rank: int = Field(ge=1, description="1-based rank within the result set.")
    matched_fields: list[str] = Field(
        default_factory=list,
        description="Fields or filters that contributed to the match.",
    )
    snippet: str | None = Field(
        default=None,
        description="Short display snippet when one is available.",
    )
    score: float | None = Field(
        default=None,
        description="Deterministic score used for ranking when a score is meaningful.",
    )
    provenance: ProvenanceRecord = Field(
        description="Traceability for how the retrieval result was assembled."
    )


class EvidenceSearchResult(StrictModel):
    """Evidence-specific retrieval result with citing-artifact context."""

    evidence_search_result_id: str = Field(
        description="Canonical evidence-search-result identifier."
    )
    artifact_reference: ResearchArtifactReference = Field(
        description="Reference to the matching stored EvidenceSpan artifact."
    )
    quote: str = Field(description="Quoted evidence text from the stored EvidenceSpan.")
    source_reference_id: str = Field(description="Source reference that contains the evidence.")
    document_id: str = Field(description="Document that contains the evidence.")
    document_kind: DocumentKind | None = Field(
        default=None,
        description="Resolved document kind when the evidence is linked to one document.",
    )
    citing_artifact_references: list[ResearchArtifactReference] = Field(
        default_factory=list,
        description="Stored artifacts that explicitly cite the evidence span.",
    )
    rank: int = Field(ge=1, description="1-based rank within the result set.")
    matched_fields: list[str] = Field(
        default_factory=list,
        description="Fields or filters that contributed to the evidence match.",
    )
    score: float | None = Field(
        default=None,
        description="Deterministic score used for ranking when a score is meaningful.",
    )
    provenance: ProvenanceRecord = Field(
        description="Traceability for how the evidence result was assembled."
    )

    @model_validator(mode="after")
    def validate_evidence_result(self) -> EvidenceSearchResult:
        """Require that evidence results reference real EvidenceSpan artifacts."""

        if self.artifact_reference.scope is not MemoryScope.EVIDENCE:
            raise ValueError("EvidenceSearchResult requires artifact_reference.scope == evidence.")
        if self.artifact_reference.artifact_type != "EvidenceSpan":
            raise ValueError(
                "EvidenceSearchResult requires artifact_reference.artifact_type == `EvidenceSpan`."
            )
        if not self.quote:
            raise ValueError("quote must be non-empty.")
        if not self.source_reference_id:
            raise ValueError("source_reference_id must be non-empty.")
        if not self.document_id:
            raise ValueError("document_id must be non-empty.")
        return self


class RetrievalContext(StrictModel):
    """Advisory retrieval context attached to a workflow or operator read model."""

    query: RetrievalQuery = Field(description="Query used to build the context.")
    results: list[RetrievalResult] = Field(
        default_factory=list,
        description="Non-evidence retrieval results.",
    )
    evidence_results: list[EvidenceSearchResult] = Field(
        default_factory=list,
        description="Evidence-specific retrieval results.",
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Operational notes about the retrieval behavior or limitations.",
    )
    semantic_retrieval_used: bool = Field(
        default=False,
        description="Whether semantic retrieval was used. Day 18 keeps this false.",
    )
