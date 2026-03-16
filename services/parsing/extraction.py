from __future__ import annotations

import re

from libraries.core import build_provenance
from libraries.schemas import (
    ClaimType,
    DocumentEvidenceBundle,
    DocumentSegment,
    EvidenceSpan,
    ExtractedClaim,
    ExtractedRiskFactor,
    GuidanceChange,
    GuidanceDirection,
    ParsedDocumentText,
    RiskCategory,
    SegmentKind,
    ToneMarker,
    ToneMarkerType,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id
from services.parsing.evals import evaluate_document_evidence_bundle
from services.parsing.loaders import LoadedParsingInputs

_GUIDANCE_DIRECTIONS: tuple[tuple[GuidanceDirection, tuple[str, ...]], ...] = (
    (GuidanceDirection.MAINTAINED, ("reiterated", "maintaining", "maintained")),
    (GuidanceDirection.RAISED, ("raised", "increased", "increase")),
    (GuidanceDirection.LOWERED, ("lowered", "reduced", "cut")),
    (GuidanceDirection.WITHDREW, ("withdrew", "withdrawn")),
    (GuidanceDirection.INITIATED, ("initiated", "introduced")),
)

_TONE_MARKERS: tuple[tuple[ToneMarkerType, tuple[str, ...]], ...] = (
    (ToneMarkerType.CONFIDENCE, ("well ahead", "ahead of plan", "ahead of our", "reiterated", "maintaining")),
    (ToneMarkerType.CAUTION, ("pressure", "challenge", "headwind", "continuing to fund")),
    (ToneMarkerType.UNCERTAINTY, ("uncertain", "could", "may")),
    (ToneMarkerType.IMPROVEMENT, ("increase", "improved", "up ", "expansion")),
)


def build_document_evidence_bundle(
    *,
    parsed_document_text: ParsedDocumentText,
    segments: list[DocumentSegment],
    inputs: LoadedParsingInputs,
    clock: Clock,
    workflow_run_id: str,
    notes: list[str],
) -> DocumentEvidenceBundle:
    """Build a complete evidence bundle from parsed text and parser-owned segments."""

    evidence_spans, claims, risk_factors, guidance_changes, tone_markers = extract_evidence_objects(
        parsed_document_text=parsed_document_text,
        segments=segments,
        inputs=inputs,
        clock=clock,
        workflow_run_id=workflow_run_id,
        notes=notes,
    )
    bundle = DocumentEvidenceBundle(
        document_id=inputs.document.document_id,
        source_reference_id=inputs.source_reference.source_reference_id,
        company_id=inputs.document.company_id,
        document_kind=inputs.document.kind,
        parsed_document_text=parsed_document_text,
        segments=segments,
        evidence_spans=evidence_spans,
        claims=claims,
        risk_factors=risk_factors,
        guidance_changes=guidance_changes,
        tone_markers=tone_markers,
        evaluation=evaluate_document_evidence_bundle(
            parsed_document_text=parsed_document_text,
            segments=segments,
            evidence_spans=evidence_spans,
            claims=claims,
            risk_factors=risk_factors,
            guidance_changes=guidance_changes,
            tone_markers=tone_markers,
            clock=clock,
        ),
    )
    return bundle


def extract_evidence_objects(
    *,
    parsed_document_text: ParsedDocumentText,
    segments: list[DocumentSegment],
    inputs: LoadedParsingInputs,
    clock: Clock,
    workflow_run_id: str,
    notes: list[str],
) -> tuple[
    list[EvidenceSpan],
    list[ExtractedClaim],
    list[ExtractedRiskFactor],
    list[GuidanceChange],
    list[ToneMarker],
]:
    """Extract sentence-level evidence spans and modest structured artifacts."""

    evidence_spans: list[EvidenceSpan] = []
    claims: list[ExtractedClaim] = []
    risk_factors: list[ExtractedRiskFactor] = []
    guidance_changes: list[GuidanceChange] = []
    tone_markers: list[ToneMarker] = []

    for segment in _leaf_segments(segments):
        for start_char, end_char in _sentence_spans(segment):
            span_text = parsed_document_text.canonical_text[start_char:end_char]
            evidence_span = _build_evidence_span(
                parsed_document_text=parsed_document_text,
                segment=segment,
                start_char=start_char,
                end_char=end_char,
                span_text=span_text,
                inputs=inputs,
                clock=clock,
                workflow_run_id=workflow_run_id,
                notes=notes,
            )
            evidence_spans.append(evidence_span)

            claim = _build_claim(
                evidence_span=evidence_span,
                segment=segment,
                inputs=inputs,
                clock=clock,
                workflow_run_id=workflow_run_id,
                notes=notes,
            )
            if claim is not None:
                claims.append(claim)

            risk_factor = _build_risk_factor(
                evidence_span=evidence_span,
                segment=segment,
                inputs=inputs,
                clock=clock,
                workflow_run_id=workflow_run_id,
                notes=notes,
            )
            if risk_factor is not None:
                risk_factors.append(risk_factor)

            guidance_change = _build_guidance_change(
                evidence_span=evidence_span,
                segment=segment,
                inputs=inputs,
                clock=clock,
                workflow_run_id=workflow_run_id,
                notes=notes,
            )
            if guidance_change is not None:
                guidance_changes.append(guidance_change)

            tone_markers.extend(
                _build_tone_markers(
                    evidence_span=evidence_span,
                    segment=segment,
                    inputs=inputs,
                    clock=clock,
                    workflow_run_id=workflow_run_id,
                    notes=notes,
                )
            )
    return evidence_spans, claims, risk_factors, guidance_changes, tone_markers


def _build_evidence_span(
    *,
    parsed_document_text: ParsedDocumentText,
    segment: DocumentSegment,
    start_char: int,
    end_char: int,
    span_text: str,
    inputs: LoadedParsingInputs,
    clock: Clock,
    workflow_run_id: str,
    notes: list[str],
) -> EvidenceSpan:
    """Create a sentence-level evidence span from a leaf parser segment."""

    captured_at = clock.now()
    return EvidenceSpan(
        evidence_span_id=make_canonical_id(
            "evd",
            inputs.document.document_id,
            segment.document_segment_id,
            str(start_char),
            str(end_char),
        ),
        source_reference_id=inputs.source_reference.source_reference_id,
        document_id=inputs.document.document_id,
        segment_id=segment.document_segment_id,
        text=span_text,
        start_char=start_char,
        end_char=end_char,
        page_number=None,
        speaker=segment.speaker,
        captured_at=captured_at,
        confidence=None,
        provenance=build_provenance(
            clock=clock,
            transformation_name="sentence_span_extraction",
            source_reference_ids=[inputs.source_reference.source_reference_id],
            upstream_artifact_ids=[
                parsed_document_text.parsed_document_text_id,
                segment.document_segment_id,
            ],
            workflow_run_id=workflow_run_id,
            ingestion_time=inputs.document.ingested_at,
            notes=notes,
        ),
        created_at=captured_at,
        updated_at=captured_at,
    )


def _build_claim(
    *,
    evidence_span: EvidenceSpan,
    segment: DocumentSegment,
    inputs: LoadedParsingInputs,
    clock: Clock,
    workflow_run_id: str,
    notes: list[str],
) -> ExtractedClaim | None:
    """Create an exact-span claim when the sentence contains a supported claim pattern."""

    claim_type = _classify_claim_type(evidence_span.text)
    if claim_type is None:
        return None

    now = clock.now()
    return ExtractedClaim(
        extracted_claim_id=make_canonical_id(
            "claim",
            inputs.document.document_id,
            claim_type.value,
            segment.document_segment_id,
            evidence_span.text,
        ),
        document_id=inputs.document.document_id,
        source_reference_id=inputs.source_reference.source_reference_id,
        company_id=inputs.document.company_id,
        segment_id=segment.document_segment_id,
        statement=evidence_span.text,
        evidence_span_ids=[evidence_span.evidence_span_id],
        speaker=segment.speaker,
        confidence=None,
        claim_type=claim_type,
        provenance=build_provenance(
            clock=clock,
            transformation_name="claim_extraction",
            source_reference_ids=[inputs.source_reference.source_reference_id],
            upstream_artifact_ids=[evidence_span.evidence_span_id],
            workflow_run_id=workflow_run_id,
            ingestion_time=inputs.document.ingested_at,
            notes=notes,
        ),
        created_at=now,
        updated_at=now,
    )


def _build_risk_factor(
    *,
    evidence_span: EvidenceSpan,
    segment: DocumentSegment,
    inputs: LoadedParsingInputs,
    clock: Clock,
    workflow_run_id: str,
    notes: list[str],
) -> ExtractedRiskFactor | None:
    """Create a risk-factor artifact only for explicit constraint or risk language."""

    risk_category = _classify_risk_category(evidence_span.text)
    if risk_category is None:
        return None

    now = clock.now()
    return ExtractedRiskFactor(
        risk_factor_id=make_canonical_id(
            "rfact",
            inputs.document.document_id,
            risk_category.value,
            segment.document_segment_id,
            evidence_span.text,
        ),
        document_id=inputs.document.document_id,
        source_reference_id=inputs.source_reference.source_reference_id,
        company_id=inputs.document.company_id,
        segment_id=segment.document_segment_id,
        statement=evidence_span.text,
        evidence_span_ids=[evidence_span.evidence_span_id],
        speaker=segment.speaker,
        confidence=None,
        risk_category=risk_category,
        provenance=build_provenance(
            clock=clock,
            transformation_name="risk_factor_extraction",
            source_reference_ids=[inputs.source_reference.source_reference_id],
            upstream_artifact_ids=[evidence_span.evidence_span_id],
            workflow_run_id=workflow_run_id,
            ingestion_time=inputs.document.ingested_at,
            notes=notes,
        ),
        created_at=now,
        updated_at=now,
    )


def _build_guidance_change(
    *,
    evidence_span: EvidenceSpan,
    segment: DocumentSegment,
    inputs: LoadedParsingInputs,
    clock: Clock,
    workflow_run_id: str,
    notes: list[str],
) -> GuidanceChange | None:
    """Create a structured guidance-change artifact from explicit guidance language."""

    guidance = _guidance_direction_and_topic(evidence_span.text)
    if guidance is None:
        return None
    direction, topic = guidance

    now = clock.now()
    return GuidanceChange(
        guidance_change_id=make_canonical_id(
            "gchg",
            inputs.document.document_id,
            direction.value,
            topic,
            segment.document_segment_id,
            evidence_span.text,
        ),
        document_id=inputs.document.document_id,
        source_reference_id=inputs.source_reference.source_reference_id,
        company_id=inputs.document.company_id,
        segment_id=segment.document_segment_id,
        statement=evidence_span.text,
        evidence_span_ids=[evidence_span.evidence_span_id],
        speaker=segment.speaker,
        confidence=None,
        direction=direction,
        topic=topic,
        provenance=build_provenance(
            clock=clock,
            transformation_name="guidance_change_extraction",
            source_reference_ids=[inputs.source_reference.source_reference_id],
            upstream_artifact_ids=[evidence_span.evidence_span_id],
            workflow_run_id=workflow_run_id,
            ingestion_time=inputs.document.ingested_at,
            notes=notes,
        ),
        created_at=now,
        updated_at=now,
    )


def _build_tone_markers(
    *,
    evidence_span: EvidenceSpan,
    segment: DocumentSegment,
    inputs: LoadedParsingInputs,
    clock: Clock,
    workflow_run_id: str,
    notes: list[str],
) -> list[ToneMarker]:
    """Create narrow lexical tone markers from explicit cue phrases only."""

    tone_markers: list[ToneMarker] = []
    now = clock.now()
    for marker_type, cues in _TONE_MARKERS:
        cue_phrase = _find_cue_phrase(evidence_span.text, cues)
        if cue_phrase is None:
            continue
        tone_markers.append(
            ToneMarker(
                tone_marker_id=make_canonical_id(
                    "tone",
                    inputs.document.document_id,
                    marker_type.value,
                    cue_phrase,
                    segment.document_segment_id,
                    evidence_span.text,
                ),
                document_id=inputs.document.document_id,
                source_reference_id=inputs.source_reference.source_reference_id,
                company_id=inputs.document.company_id,
                segment_id=segment.document_segment_id,
                statement=evidence_span.text,
                evidence_span_ids=[evidence_span.evidence_span_id],
                speaker=segment.speaker,
                confidence=None,
                marker_type=marker_type,
                cue_phrase=cue_phrase,
                provenance=build_provenance(
                    clock=clock,
                    transformation_name="tone_marker_extraction",
                    source_reference_ids=[inputs.source_reference.source_reference_id],
                    upstream_artifact_ids=[evidence_span.evidence_span_id],
                    workflow_run_id=workflow_run_id,
                    ingestion_time=inputs.document.ingested_at,
                    notes=notes,
                ),
                created_at=now,
                updated_at=now,
            )
        )
    return tone_markers


def _leaf_segments(segments: list[DocumentSegment]) -> list[DocumentSegment]:
    """Return leaf parser segments suitable for sentence-level evidence extraction."""

    parent_ids = {segment.parent_segment_id for segment in segments if segment.parent_segment_id}
    leaf_segments = [
        segment
        for segment in segments
        if segment.document_segment_id not in parent_ids and segment.segment_kind != SegmentKind.SECTION
    ]
    return sorted(leaf_segments, key=lambda segment: segment.sequence_index)


def _sentence_spans(segment: DocumentSegment) -> list[tuple[int, int]]:
    """Return exact sentence spans for a leaf segment."""

    spans: list[tuple[int, int]] = []
    for match in re.finditer(r"\S.*?(?:[.!?](?=\s|$)|$)", segment.text, re.S):
        local_start = match.start()
        local_end = match.end()
        text = segment.text[local_start:local_end]
        stripped = text.strip()
        if not stripped:
            continue
        leading_trim = len(text) - len(text.lstrip())
        trailing_trim = len(text) - len(text.rstrip())
        start_char = segment.start_char + local_start + leading_trim
        end_char = segment.start_char + local_end - trailing_trim
        if end_char > start_char:
            spans.append((start_char, end_char))
    return spans


def _classify_claim_type(text: str) -> ClaimType | None:
    """Classify an exact-span sentence into a narrow supported claim category."""

    lowered = text.lower()
    if "guidance" in lowered or "outlook" in lowered:
        return ClaimType.OUTLOOK_STATEMENT
    if any(token in lowered for token in ("revenue", "gross margin", "free cash flow", "$", "%")):
        return ClaimType.FINANCIAL_RESULT
    if any(token in lowered for token in ("launch", "launches", "predictive maintenance suite", "product", "platform")):
        return ClaimType.PRODUCT_UPDATE
    if any(token in lowered for token in ("expects", "expected", "begin", "available", "later this quarter")):
        return ClaimType.TIMELINE_STATEMENT
    if any(
        token in lowered
        for token in ("backlog", "conversion", "demand", "attach expansion", "pilot deployments", "channel expansion")
    ):
        return ClaimType.OPERATIONAL_UPDATE
    return None


def _classify_risk_category(text: str) -> RiskCategory | None:
    """Classify an exact-span sentence into a narrow supported risk-factor category."""

    lowered = text.lower()
    if not any(
        token in lowered
        for token in (
            "risk",
            "pressure",
            "challenge",
            "headwind",
            "uncertain",
            "delay",
            "constrained",
            "continuing to fund",
            "fund the",
        )
    ):
        return None
    if any(token in lowered for token in ("regulatory", "compliance")):
        return RiskCategory.REGULATORY
    if any(token in lowered for token in ("margin pressure", "gross margin pressure")):
        return RiskCategory.MARGIN
    if any(token in lowered for token in ("demand pressure", "slowdown in demand")):
        return RiskCategory.DEMAND
    if any(token in lowered for token in ("fund", "funding", "investment", "migration")):
        return RiskCategory.INVESTMENT
    if any(token in lowered for token in ("delay", "challenge", "constrained")):
        return RiskCategory.EXECUTION
    if "operational" in lowered:
        return RiskCategory.OPERATIONAL
    return RiskCategory.OTHER


def _guidance_direction_and_topic(text: str) -> tuple[GuidanceDirection, str] | None:
    """Return a structured guidance direction and topic when explicit guidance language exists."""

    lowered = text.lower()
    if "guidance" not in lowered and "outlook" not in lowered:
        return None
    for direction, cues in _GUIDANCE_DIRECTIONS:
        if any(cue in lowered for cue in cues):
            topic_match = re.search(
                r"([A-Za-z0-9\-$%][A-Za-z0-9\-$% ,\-]*(?:guidance|outlook))",
                text,
                re.I,
            )
            topic = topic_match.group(1).strip() if topic_match is not None else "guidance"
            return direction, topic
    return None


def _find_cue_phrase(text: str, cues: tuple[str, ...]) -> str | None:
    """Find the first explicit lexical cue phrase present in the sentence."""

    lowered = text.lower()
    for cue in cues:
        index = lowered.find(cue)
        if index >= 0:
            return text[index : index + len(cue)]
    return None
