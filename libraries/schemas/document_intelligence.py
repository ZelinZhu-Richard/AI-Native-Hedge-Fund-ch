from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from libraries.schemas.base import (
    ConfidenceAssessment,
    DocumentKind,
    ProvenanceRecord,
    StrictModel,
    TimestampedModel,
)
from libraries.schemas.market import EvidenceSpan


class SegmentKind(StrEnum):
    """Kinds of parser-owned document segments."""

    SECTION = "section"
    PARAGRAPH = "paragraph"
    SPEAKER_TURN = "speaker_turn"
    HEADLINE = "headline"
    BODY = "body"


class ClaimType(StrEnum):
    """Structured claim categories emitted by the extraction layer."""

    FINANCIAL_RESULT = "financial_result"
    OPERATIONAL_UPDATE = "operational_update"
    PRODUCT_UPDATE = "product_update"
    OUTLOOK_STATEMENT = "outlook_statement"
    TIMELINE_STATEMENT = "timeline_statement"


class RiskCategory(StrEnum):
    """Explicit risk-factor categories supported by the first-pass extractor."""

    EXECUTION = "execution"
    INVESTMENT = "investment"
    DEMAND = "demand"
    MARGIN = "margin"
    OPERATIONAL = "operational"
    REGULATORY = "regulatory"
    OTHER = "other"


class GuidanceDirection(StrEnum):
    """Guidance or outlook direction inferred from explicit source language."""

    INITIATED = "initiated"
    MAINTAINED = "maintained"
    RAISED = "raised"
    LOWERED = "lowered"
    WITHDREW = "withdrew"


class ToneMarkerType(StrEnum):
    """Narrow lexical tone-marker categories supported by Day 3 extraction."""

    CONFIDENCE = "confidence"
    CAUTION = "caution"
    UNCERTAINTY = "uncertainty"
    IMPROVEMENT = "improvement"


class ParsedDocumentText(TimestampedModel):
    """Parser-owned canonical text representation used as the offset coordinate space."""

    parsed_document_text_id: str = Field(description="Canonical parsed-text artifact identifier.")
    document_id: str = Field(description="Canonical document identifier.")
    source_reference_id: str = Field(description="Source reference backing the parsed text.")
    company_id: str | None = Field(
        default=None, description="Associated company identifier when applicable."
    )
    document_kind: DocumentKind = Field(description="Document type the parsed text belongs to.")
    canonical_text: str = Field(
        description="Parser-owned canonical text used as the global offset coordinate space."
    )
    headline_text: str | None = Field(
        default=None, description="Headline text when the source has a distinct headline."
    )
    body_text: str | None = Field(
        default=None, description="Normalized body text when separable from the headline."
    )
    provenance: ProvenanceRecord = Field(description="Traceability for parsed-text creation.")

    @model_validator(mode="after")
    def validate_text(self) -> Self:
        """Ensure the parsed text artifact always carries usable text."""

        if not self.canonical_text:
            raise ValueError("canonical_text must be non-empty.")
        return self


class DocumentSegment(TimestampedModel):
    """A parser-owned segment anchored to exact offsets in parsed document text."""

    document_segment_id: str = Field(description="Canonical segment identifier.")
    parsed_document_text_id: str = Field(description="Parsed-text artifact that owns the segment.")
    document_id: str = Field(description="Canonical document identifier.")
    source_reference_id: str = Field(description="Source reference backing the segment.")
    parent_segment_id: str | None = Field(
        default=None, description="Parent segment identifier when the segment is nested."
    )
    segment_kind: SegmentKind = Field(description="Segment class emitted by the parser.")
    sequence_index: int = Field(ge=0, description="Stable sequence index in parsed-text order.")
    label: str | None = Field(default=None, description="Semantic label such as `body` or `Q&A`.")
    speaker: str | None = Field(default=None, description="Speaker name for transcript turns.")
    text: str = Field(description="Exact segment text from canonical parsed text.")
    start_char: int = Field(ge=0, description="Inclusive start offset in canonical parsed text.")
    end_char: int = Field(description="Exclusive end offset in canonical parsed text.")
    provenance: ProvenanceRecord = Field(description="Traceability for segmentation.")

    @model_validator(mode="after")
    def validate_offsets(self) -> Self:
        """Ensure the segment offsets and text are coherent."""

        if self.end_char < self.start_char:
            raise ValueError("end_char must be greater than or equal to start_char.")
        if not self.text:
            raise ValueError("text must be non-empty.")
        return self


class EvidenceDerivedArtifact(TimestampedModel):
    """Shared fields for extracted artifacts grounded in exact evidence spans."""

    document_id: str = Field(description="Canonical document identifier.")
    source_reference_id: str = Field(description="Source reference backing the artifact.")
    company_id: str | None = Field(
        default=None, description="Associated company identifier when applicable."
    )
    segment_id: str = Field(description="Document segment that contains the extracted artifact.")
    statement: str = Field(description="Exact extracted statement text, not a paraphrase.")
    evidence_span_ids: list[str] = Field(
        default_factory=list,
        description="Evidence spans that directly ground the extracted artifact.",
    )
    speaker: str | None = Field(
        default=None, description="Speaker when the artifact comes from a transcript turn."
    )
    confidence: ConfidenceAssessment | None = Field(
        default=None,
        description="Optional confidence assessment when deterministically available.",
    )
    provenance: ProvenanceRecord = Field(description="Traceability for the extracted artifact.")

    @model_validator(mode="after")
    def validate_evidence_links(self) -> Self:
        """Require at least one evidence span for every extracted artifact."""

        if not self.evidence_span_ids:
            raise ValueError("evidence_span_ids must contain at least one span identifier.")
        return self


class ExtractedClaim(EvidenceDerivedArtifact):
    """Exact-span claim extracted from a parsed document."""

    extracted_claim_id: str = Field(description="Canonical extracted-claim identifier.")
    claim_type: ClaimType = Field(description="Structured claim category.")


class ExtractedRiskFactor(EvidenceDerivedArtifact):
    """Exact-span risk-factor statement extracted from a parsed document."""

    risk_factor_id: str = Field(description="Canonical extracted risk-factor identifier.")
    risk_category: RiskCategory = Field(description="Structured risk-factor category.")


class GuidanceChange(EvidenceDerivedArtifact):
    """Explicit guidance or outlook statement with a structured direction label."""

    guidance_change_id: str = Field(description="Canonical guidance-change identifier.")
    direction: GuidanceDirection = Field(description="Structured guidance direction.")
    topic: str = Field(description="Extracted guidance or outlook topic phrase.")


class ToneMarker(EvidenceDerivedArtifact):
    """Exact lexical tone cue anchored to a specific evidence span."""

    tone_marker_id: str = Field(description="Canonical tone-marker identifier.")
    marker_type: ToneMarkerType = Field(description="Structured tone-marker category.")
    cue_phrase: str = Field(description="Exact lexical cue phrase that triggered the marker.")


class DocumentEvidenceEvaluation(StrictModel):
    """Simple extraction-eval report for a document evidence bundle."""

    document_id: str = Field(description="Canonical document identifier.")
    evaluated_at: datetime = Field(description="UTC timestamp when the bundle was evaluated.")
    segment_count: int = Field(ge=0, description="Number of segments in the bundle.")
    evidence_span_count: int = Field(ge=0, description="Number of evidence spans in the bundle.")
    claim_count: int = Field(ge=0, description="Number of extracted claims.")
    risk_factor_count: int = Field(ge=0, description="Number of extracted risk factors.")
    guidance_change_count: int = Field(ge=0, description="Number of extracted guidance changes.")
    tone_marker_count: int = Field(ge=0, description="Number of extracted tone markers.")
    provenance_complete: bool = Field(description="Whether provenance was present where required.")
    reference_integrity_ok: bool = Field(
        description="Whether all segment and evidence references resolved cleanly."
    )
    span_text_alignment_ok: bool = Field(
        description="Whether every evidence span matches its canonical text slice."
    )
    passed: bool = Field(description="Whether the bundle passed the current lightweight eval.")
    notes: list[str] = Field(
        default_factory=list,
        description="Eval notes describing failures, warnings, or coverage observations.",
    )


class DocumentEvidenceBundle(StrictModel):
    """Reusable bundle of parsed text, segments, evidence spans, and extracted artifacts."""

    document_id: str = Field(description="Canonical document identifier.")
    source_reference_id: str = Field(description="Source reference backing the bundle.")
    company_id: str | None = Field(
        default=None, description="Associated company identifier when applicable."
    )
    document_kind: DocumentKind = Field(description="Document type represented by the bundle.")
    parsed_document_text: ParsedDocumentText = Field(description="Parser-owned canonical text.")
    segments: list[DocumentSegment] = Field(default_factory=list, description="Document segments.")
    evidence_spans: list[EvidenceSpan] = Field(
        default_factory=list,
        description="Evidence spans emitted from the parsed text.",
    )
    claims: list[ExtractedClaim] = Field(
        default_factory=list, description="Extracted exact-span claims."
    )
    risk_factors: list[ExtractedRiskFactor] = Field(
        default_factory=list, description="Extracted explicit risk factors."
    )
    guidance_changes: list[GuidanceChange] = Field(
        default_factory=list, description="Extracted guidance or outlook changes."
    )
    tone_markers: list[ToneMarker] = Field(
        default_factory=list, description="Extracted narrow lexical tone markers."
    )
    evaluation: DocumentEvidenceEvaluation = Field(
        description="Lightweight eval report for the evidence bundle."
    )
