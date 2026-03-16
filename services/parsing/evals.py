from __future__ import annotations

from libraries.schemas import (
    DocumentEvidenceEvaluation,
    DocumentSegment,
    EvidenceSpan,
    ExtractedClaim,
    ExtractedRiskFactor,
    GuidanceChange,
    ParsedDocumentText,
    ToneMarker,
)
from libraries.time import Clock


def evaluate_document_evidence_bundle(
    *,
    parsed_document_text: ParsedDocumentText,
    segments: list[DocumentSegment],
    evidence_spans: list[EvidenceSpan],
    claims: list[ExtractedClaim],
    risk_factors: list[ExtractedRiskFactor],
    guidance_changes: list[GuidanceChange],
    tone_markers: list[ToneMarker],
    clock: Clock,
) -> DocumentEvidenceEvaluation:
    """Run lightweight integrity checks over a document evidence bundle."""

    notes: list[str] = []
    segment_ids = {segment.document_segment_id for segment in segments}
    evidence_span_ids = {span.evidence_span_id for span in evidence_spans}

    if not evidence_spans:
        notes.append("No evidence spans were extracted from the parsed document.")

    provenance_complete = _provenance_complete(
        parsed_document_text=parsed_document_text,
        segments=segments,
        evidence_spans=evidence_spans,
        claims=claims,
        risk_factors=risk_factors,
        guidance_changes=guidance_changes,
        tone_markers=tone_markers,
    )
    if not provenance_complete:
        notes.append("One or more artifacts had incomplete provenance.")

    reference_integrity_ok = True
    for span in evidence_spans:
        if span.segment_id is None or span.segment_id not in segment_ids:
            reference_integrity_ok = False
            notes.append(f"Unresolved segment reference for evidence span {span.evidence_span_id}.")
    for artifact_name, artifacts in (
        ("claim", claims),
        ("risk_factor", risk_factors),
        ("guidance_change", guidance_changes),
        ("tone_marker", tone_markers),
    ):
        for artifact in artifacts:
            if artifact.segment_id not in segment_ids:
                reference_integrity_ok = False
                notes.append(
                    f"Unresolved segment reference for {artifact_name} {_artifact_identifier(artifact)}."
                )
            for evidence_span_id in artifact.evidence_span_ids:
                if evidence_span_id not in evidence_span_ids:
                    reference_integrity_ok = False
                    notes.append(
                        f"Unresolved evidence span reference `{evidence_span_id}` in {artifact_name}."
                    )

    span_text_alignment_ok = True
    for span in evidence_spans:
        if span.start_char is None or span.end_char is None:
            span_text_alignment_ok = False
            notes.append(f"Evidence span {span.evidence_span_id} is missing exact char offsets.")
            continue
        expected_text = parsed_document_text.canonical_text[span.start_char : span.end_char]
        if expected_text != span.text:
            span_text_alignment_ok = False
            notes.append(f"Evidence span {span.evidence_span_id} does not align to canonical text.")

    passed = provenance_complete and reference_integrity_ok and span_text_alignment_ok and bool(
        evidence_spans
    )
    return DocumentEvidenceEvaluation(
        document_id=parsed_document_text.document_id,
        evaluated_at=clock.now(),
        segment_count=len(segments),
        evidence_span_count=len(evidence_spans),
        claim_count=len(claims),
        risk_factor_count=len(risk_factors),
        guidance_change_count=len(guidance_changes),
        tone_marker_count=len(tone_markers),
        provenance_complete=provenance_complete,
        reference_integrity_ok=reference_integrity_ok,
        span_text_alignment_ok=span_text_alignment_ok,
        passed=passed,
        notes=notes,
    )


def _provenance_complete(
    *,
    parsed_document_text: ParsedDocumentText,
    segments: list[DocumentSegment],
    evidence_spans: list[EvidenceSpan],
    claims: list[ExtractedClaim],
    risk_factors: list[ExtractedRiskFactor],
    guidance_changes: list[GuidanceChange],
    tone_markers: list[ToneMarker],
) -> bool:
    """Check that all artifacts carry minimum provenance fields."""

    for artifact in (
        [parsed_document_text]
        + segments
        + evidence_spans
        + claims
        + risk_factors
        + guidance_changes
        + tone_markers
    ):
        if not _artifact_has_complete_provenance(artifact, parsed_document_text.source_reference_id):
            return False
    return True


def _artifact_identifier(
    artifact: ExtractedClaim | ExtractedRiskFactor | GuidanceChange | ToneMarker,
) -> str:
    """Return the canonical identifier for an extracted artifact."""

    if isinstance(artifact, ExtractedClaim):
        return artifact.extracted_claim_id
    if isinstance(artifact, ExtractedRiskFactor):
        return artifact.risk_factor_id
    if isinstance(artifact, GuidanceChange):
        return artifact.guidance_change_id
    return artifact.tone_marker_id


def _artifact_has_complete_provenance(
    artifact: ParsedDocumentText
    | DocumentSegment
    | EvidenceSpan
    | ExtractedClaim
    | ExtractedRiskFactor
    | GuidanceChange
    | ToneMarker,
    source_reference_id: str,
) -> bool:
    """Check minimum provenance completeness for a parsing artifact."""

    provenance = artifact.provenance
    if provenance.processing_time is None:
        return False
    if not provenance.transformation_name:
        return False
    return source_reference_id in provenance.source_reference_ids
