from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field, model_validator

from libraries.schemas.base import (
    ConfidenceAssessment,
    DataLayer,
    DocumentKind,
    DocumentStatus,
    FilingForm,
    MarketEventType,
    PriceSeriesStatus,
    ProvenanceRecord,
    SourceType,
    TimestampedModel,
)
from libraries.schemas.timing import PublicationTiming


class Company(TimestampedModel):
    """Canonical company entity used across documents, signals, and portfolios."""

    company_id: str = Field(description="Canonical company identifier, for example `co_...`.")
    legal_name: str = Field(description="Full legal entity name.")
    ticker: str | None = Field(default=None, description="Primary listed ticker when available.")
    exchange: str | None = Field(default=None, description="Primary exchange code when listed.")
    cik: str | None = Field(default=None, description="SEC Central Index Key.")
    isin: str | None = Field(default=None, description="ISIN identifier when available.")
    lei: str | None = Field(default=None, description="Legal Entity Identifier when available.")
    figi: str | None = Field(default=None, description="FIGI identifier when available.")
    sector: str | None = Field(default=None, description="Standardized sector classification.")
    industry: str | None = Field(default=None, description="Standardized industry classification.")
    country_of_risk: str | None = Field(
        default=None, description="Country of risk or primary domicile."
    )
    active: bool = Field(
        default=True, description="Whether the company is currently active in coverage."
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the company record.")


class SourceReference(TimestampedModel):
    """Source-level metadata for raw or normalized upstream content."""

    source_reference_id: str = Field(description="Canonical source reference identifier.")
    source_type: SourceType = Field(description="Source system category.")
    external_id: str | None = Field(default=None, description="Upstream source identifier.")
    uri: str = Field(description="Canonical URI for retrieval or traceability.")
    title: str | None = Field(default=None, description="Source title if known.")
    publisher: str | None = Field(default=None, description="Source publisher or vendor.")
    content_hash: str | None = Field(
        default=None, description="Hash of raw retrieved content when available."
    )
    published_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the source was published or first visible.",
    )
    retrieved_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the source content was retrieved.",
    )
    effective_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when the information became actionable, if distinct from publication.",
    )
    publication_timing: PublicationTiming | None = Field(
        default=None,
        description="Normalized publication and internal availability timing when resolved.",
    )
    license: str | None = Field(
        default=None, description="Usage or redistribution license if applicable."
    )
    provenance: ProvenanceRecord = Field(
        description="Traceability for how the source reference was registered or normalized."
    )

    @model_validator(mode="after")
    def validate_temporal_order(self) -> SourceReference:
        """Ensure source timestamps do not imply impossible ordering."""

        if self.published_at is not None and self.retrieved_at is not None:
            if self.retrieved_at < self.published_at:
                raise ValueError("retrieved_at must be greater than or equal to published_at.")
        return self


class EvidenceSpan(TimestampedModel):
    """A traceable snippet of evidence linked back to a source document."""

    evidence_span_id: str = Field(description="Canonical evidence span identifier.")
    source_reference_id: str = Field(description="Source reference that contains the evidence.")
    document_id: str | None = Field(
        default=None, description="Canonical document identifier if registered."
    )
    segment_id: str | None = Field(
        default=None,
        description="Parser-owned segment identifier when the span is anchored to parsed text.",
    )
    text: str = Field(description="Quoted or normalized evidence text used in reasoning.")
    start_char: int | None = Field(
        default=None, ge=0, description="Start character offset in normalized text."
    )
    end_char: int | None = Field(
        default=None, ge=0, description="End character offset in normalized text."
    )
    page_number: int | None = Field(default=None, ge=1, description="Page number when available.")
    speaker: str | None = Field(default=None, description="Speaker label for transcripts or calls.")
    captured_at: datetime = Field(description="UTC timestamp when the evidence span was extracted.")
    confidence: ConfidenceAssessment | None = Field(
        default=None,
        description="Confidence in the extraction and linkage.",
    )
    provenance: ProvenanceRecord = Field(
        description="Traceability for extraction and normalization."
    )

    @model_validator(mode="after")
    def validate_offsets(self) -> EvidenceSpan:
        """Ensure evidence offsets are internally consistent when present."""

        if (self.start_char is None) != (self.end_char is None):
            raise ValueError("start_char and end_char must be provided together.")
        if (
            self.start_char is not None
            and self.end_char is not None
            and self.end_char < self.start_char
        ):
            raise ValueError("end_char must be greater than or equal to start_char.")
        if self.segment_id is not None and (self.start_char is None or self.end_char is None):
            raise ValueError("segment-linked evidence spans must include exact char offsets.")
        return self


class Document(TimestampedModel):
    """Generic normalized document tracked by the platform."""

    document_id: str = Field(description="Canonical document identifier.")
    kind: DocumentKind = Field(default=DocumentKind.DOCUMENT, description="Document category.")
    company_id: str | None = Field(
        default=None, description="Covered company identifier when applicable."
    )
    title: str = Field(description="Normalized document title.")
    source_reference_id: str = Field(description="Source reference used to ingest this document.")
    external_id: str | None = Field(default=None, description="Upstream identifier if applicable.")
    data_layer: DataLayer = Field(description="Current artifact layer for the document.")
    language: str = Field(default="en", description="ISO language code for normalized text.")
    storage_uri: str | None = Field(
        default=None, description="URI to stored raw or normalized document payload."
    )
    content_hash: str | None = Field(
        default=None, description="Content hash of the current stored artifact."
    )
    source_published_at: datetime | None = Field(
        default=None,
        description="UTC publication time from the source system.",
    )
    effective_at: datetime | None = Field(
        default=None,
        description="UTC time when the information should be considered effective.",
    )
    publication_timing: PublicationTiming | None = Field(
        default=None,
        description="Normalized publication and internal availability timing when resolved.",
    )
    ingested_at: datetime = Field(
        description="UTC timestamp when the platform ingested the document."
    )
    processed_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when normalization or parsing completed.",
    )
    status: DocumentStatus = Field(description="Document lifecycle status.")
    tags: list[str] = Field(default_factory=list, description="Normalized document tags.")
    provenance: ProvenanceRecord = Field(description="Traceability for the document.")

    @model_validator(mode="after")
    def validate_document_times(self) -> Document:
        """Ensure document lifecycle timestamps remain internally coherent."""

        if self.processed_at is not None and self.processed_at < self.ingested_at:
            raise ValueError("processed_at must be greater than or equal to ingested_at.")
        return self


class Filing(Document):
    """Structured representation of a regulatory filing."""

    kind: Literal[DocumentKind.FILING] = DocumentKind.FILING
    form_type: FilingForm = Field(description="Filing form classification.")
    accession_number: str | None = Field(
        default=None, description="SEC accession number or equivalent."
    )
    filing_date: date | None = Field(default=None, description="Official filing date.")
    period_end_date: date | None = Field(
        default=None, description="Period end date referenced by the filing."
    )
    amendment: bool = Field(default=False, description="Whether this filing amends a prior filing.")
    exhibit_ids: list[str] = Field(
        default_factory=list, description="Referenced exhibit identifiers if tracked."
    )
    raw_html_uri: str | None = Field(
        default=None, description="URI for raw filing HTML or source payload."
    )
    normalized_text_uri: str | None = Field(
        default=None,
        description="URI for normalized filing text used by downstream parsers.",
    )


class EarningsCall(Document):
    """Structured representation of an earnings call transcript or event."""

    kind: Literal[DocumentKind.EARNINGS_CALL] = DocumentKind.EARNINGS_CALL
    call_datetime: datetime = Field(description="UTC timestamp of the earnings call event.")
    fiscal_year: int | None = Field(
        default=None, ge=1900, description="Fiscal year discussed on the call."
    )
    fiscal_quarter: int | None = Field(
        default=None, ge=1, le=4, description="Fiscal quarter discussed."
    )
    prepared_remarks_uri: str | None = Field(
        default=None,
        description="URI for prepared remarks section if stored separately.",
    )
    q_and_a_uri: str | None = Field(
        default=None,
        description="URI for Q&A section if stored separately.",
    )
    participants: list[str] = Field(
        default_factory=list,
        description="Participants extracted or curated for the call.",
    )


class NewsItem(Document):
    """Structured representation of a news article or alert."""

    kind: Literal[DocumentKind.NEWS_ITEM] = DocumentKind.NEWS_ITEM
    publisher: str = Field(description="Publisher or newswire name.")
    author_names: list[str] = Field(
        default_factory=list, description="Author bylines when available."
    )
    headline: str = Field(description="Normalized news headline.")
    summary: str | None = Field(
        default=None, description="Short normalized summary of the article."
    )
    relevance_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional normalized relevance score for the tracked company or theme.",
    )
    embargo_lifted_at: datetime | None = Field(
        default=None,
        description="UTC time when an embargo ended, if applicable.",
    )


class MarketEvent(TimestampedModel):
    """Structured market or corporate event used for research timelines."""

    market_event_id: str = Field(description="Canonical market event identifier.")
    company_id: str | None = Field(
        default=None, description="Associated company identifier if applicable."
    )
    event_type: MarketEventType = Field(description="Canonical event type.")
    event_time: datetime = Field(description="UTC event time.")
    announcement_time: datetime | None = Field(
        default=None,
        description="UTC timestamp when the event was first announced or surfaced.",
    )
    description: str = Field(description="Short structured description of the event.")
    source_reference_ids: list[str] = Field(
        default_factory=list,
        description="Source references supporting the event.",
    )
    impact_summary: str | None = Field(
        default=None,
        description="Short explanation of why the event matters to research.",
    )
    tags: list[str] = Field(default_factory=list, description="Normalized event tags.")
    provenance: ProvenanceRecord = Field(description="Traceability for the event record.")


class DataSnapshot(TimestampedModel):
    """Point-in-time snapshot describing a dataset version available to research workflows."""

    data_snapshot_id: str = Field(description="Canonical snapshot identifier.")
    dataset_name: str = Field(description="Canonical dataset name.")
    dataset_version: str = Field(description="Dataset version or snapshot label.")
    dataset_manifest_id: str | None = Field(
        default=None,
        description="Dataset manifest identifier when a manifest exists for the snapshot.",
    )
    data_layer: DataLayer = Field(description="Data layer represented by the snapshot.")
    snapshot_time: datetime = Field(description="UTC time the snapshot is materialized for access.")
    event_time_start: datetime | None = Field(
        default=None,
        description="Earliest event time included in the snapshot when known.",
    )
    watermark_time: datetime | None = Field(
        default=None,
        description="Latest source event time safely included in the snapshot.",
    )
    ingestion_cutoff_time: datetime | None = Field(
        default=None,
        description="Latest ingestion or materialization cutoff included in the snapshot.",
    )
    information_cutoff_time: datetime | None = Field(
        default=None,
        description="Latest time that downstream workflows are allowed to assume is available.",
    )
    storage_uri: str = Field(description="URI of the snapshot manifest or storage root.")
    row_count: int | None = Field(
        default=None, ge=0, description="Approximate row count in the snapshot."
    )
    schema_version: str = Field(description="Schema version attached to the snapshot.")
    partition_key: str | None = Field(
        default=None,
        description="Logical partitioning key for future reproducible dataset slicing.",
    )
    source_count: int | None = Field(
        default=None, ge=0, description="Number of contributing upstream sources."
    )
    source_families: list[str] = Field(
        default_factory=list,
        description="Canonical source-family labels represented by the snapshot.",
    )
    completeness_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Estimated completeness ratio for the snapshot.",
    )
    created_by_process: str = Field(description="Workflow or process that generated the snapshot.")
    provenance: ProvenanceRecord = Field(description="Traceability for the snapshot.")

    @model_validator(mode="after")
    def validate_snapshot_times(self) -> DataSnapshot:
        """Ensure snapshot watermarks do not exceed explicit information cutoffs."""

        if (
            self.event_time_start is not None
            and self.watermark_time is not None
            and self.watermark_time < self.event_time_start
        ):
            raise ValueError("watermark_time must be greater than or equal to event_time_start.")
        if (
            self.watermark_time is not None
            and self.information_cutoff_time is not None
            and self.watermark_time > self.information_cutoff_time
        ):
            raise ValueError(
                "watermark_time must be less than or equal to information_cutoff_time."
            )
        if (
            self.information_cutoff_time is not None
            and self.information_cutoff_time > self.snapshot_time
        ):
            raise ValueError(
                "information_cutoff_time must be less than or equal to snapshot_time."
            )
        if (
            self.ingestion_cutoff_time is not None
            and self.ingestion_cutoff_time > self.snapshot_time
        ):
            raise ValueError("ingestion_cutoff_time must be less than or equal to snapshot_time.")
        return self


class PriceSeriesMetadata(TimestampedModel):
    """Metadata describing a canonical price series without storing the prices themselves."""

    price_series_metadata_id: str = Field(description="Canonical price series metadata identifier.")
    company_id: str | None = Field(default=None, description="Associated company identifier.")
    symbol: str = Field(description="Primary tradable symbol for the series.")
    exchange: str | None = Field(default=None, description="Primary exchange code for the series.")
    currency: str = Field(description="Quoted currency for the series.")
    frequency: str = Field(description="Series frequency, for example `daily`.")
    timezone: str = Field(description="Timezone used by the upstream market data source.")
    dataset_name: str = Field(description="Canonical dataset name for the series.")
    source_reference_id: str = Field(description="Source reference backing the metadata.")
    vendor_symbol: str | None = Field(default=None, description="Vendor-specific symbol if different.")
    first_price_date: date | None = Field(
        default=None,
        description="First date known to exist in the upstream series.",
    )
    last_price_date: date | None = Field(
        default=None,
        description="Most recent date known to exist in the upstream series.",
    )
    status: PriceSeriesStatus = Field(description="Lifecycle status for the metadata record.")
    provenance: ProvenanceRecord = Field(description="Traceability for the price series metadata.")

    @model_validator(mode="after")
    def validate_date_range(self) -> PriceSeriesMetadata:
        """Ensure the known date range is internally consistent."""

        if (
            self.first_price_date is not None
            and self.last_price_date is not None
            and self.last_price_date < self.first_price_date
        ):
            raise ValueError("last_price_date must be greater than or equal to first_price_date.")
        return self
