from __future__ import annotations

import re

from libraries.core import build_provenance
from libraries.schemas import (
    DocumentSegment,
    EarningsCall,
    Filing,
    NewsItem,
    ParsedDocumentText,
    SegmentKind,
)
from libraries.time import Clock
from libraries.utils import make_canonical_id
from services.parsing.loaders import LoadedParsingInputs


def build_parsed_document_text(
    *,
    inputs: LoadedParsingInputs,
    clock: Clock,
    workflow_run_id: str,
    notes: list[str],
) -> ParsedDocumentText:
    """Build the parser-owned canonical text artifact for a parseable document."""

    now = clock.now()
    document = inputs.document
    if isinstance(document, Filing):
        body_text = _normalize_inline_text(inputs.raw_payload.raw_text)
        canonical_text = body_text
        headline_text = None
    elif isinstance(document, EarningsCall):
        body_text = _normalize_inline_text(inputs.raw_payload.raw_text)
        canonical_text = body_text
        headline_text = None
    else:
        assert isinstance(document, NewsItem)
        headline_text = _normalize_inline_text(document.headline)
        body_text = _normalize_inline_text(inputs.raw_payload.raw_text)
        canonical_text = f"{headline_text}\n\n{body_text}"

    return ParsedDocumentText(
        parsed_document_text_id=make_canonical_id(
            "pdoc",
            document.document_id,
            inputs.source_reference.source_reference_id,
        ),
        document_id=document.document_id,
        source_reference_id=inputs.source_reference.source_reference_id,
        company_id=document.company_id,
        document_kind=document.kind,
        canonical_text=canonical_text,
        headline_text=headline_text,
        body_text=body_text,
        provenance=build_provenance(
            clock=clock,
            transformation_name="parsed_document_text",
            source_reference_ids=[inputs.source_reference.source_reference_id],
            upstream_artifact_ids=[document.document_id],
            workflow_run_id=workflow_run_id,
            ingestion_time=document.ingested_at,
            notes=notes,
        ),
        created_at=now,
        updated_at=now,
    )


def segment_document(
    *,
    parsed_document_text: ParsedDocumentText,
    inputs: LoadedParsingInputs,
    clock: Clock,
    workflow_run_id: str,
    notes: list[str],
) -> list[DocumentSegment]:
    """Segment parser-owned text into structured sections for downstream evidence extraction."""

    document = inputs.document
    if isinstance(document, Filing):
        return _segment_filing(
            parsed_document_text=parsed_document_text,
            document=document,
            clock=clock,
            workflow_run_id=workflow_run_id,
            notes=notes,
        )
    if isinstance(document, EarningsCall):
        return _segment_transcript(
            parsed_document_text=parsed_document_text,
            document=document,
            clock=clock,
            workflow_run_id=workflow_run_id,
            notes=notes,
        )
    assert isinstance(document, NewsItem)
    return _segment_news(
        parsed_document_text=parsed_document_text,
        document=document,
        clock=clock,
        workflow_run_id=workflow_run_id,
        notes=notes,
    )


def _segment_filing(
    *,
    parsed_document_text: ParsedDocumentText,
    document: Filing,
    clock: Clock,
    workflow_run_id: str,
    notes: list[str],
) -> list[DocumentSegment]:
    """Create a body section plus paragraph segments for a filing."""

    segments: list[DocumentSegment] = []
    sequence_index = 0
    section = _make_segment(
        parsed_document_text=parsed_document_text,
        document_id=document.document_id,
        source_reference_id=document.source_reference_id,
        parent_segment_id=None,
        segment_kind=SegmentKind.SECTION,
        sequence_index=sequence_index,
        label="body",
        speaker=None,
        start_char=0,
        end_char=len(parsed_document_text.canonical_text),
        clock=clock,
        workflow_run_id=workflow_run_id,
        notes=notes,
    )
    segments.append(section)
    sequence_index += 1

    for start_char, end_char in _paragraph_spans(parsed_document_text.canonical_text):
        segments.append(
            _make_segment(
                parsed_document_text=parsed_document_text,
                document_id=document.document_id,
                source_reference_id=document.source_reference_id,
                parent_segment_id=section.document_segment_id,
                segment_kind=SegmentKind.PARAGRAPH,
                sequence_index=sequence_index,
                label="paragraph",
                speaker=None,
                start_char=start_char,
                end_char=end_char,
                clock=clock,
                workflow_run_id=workflow_run_id,
                notes=notes,
            )
        )
        sequence_index += 1
    return segments


def _segment_transcript(
    *,
    parsed_document_text: ParsedDocumentText,
    document: EarningsCall,
    clock: Clock,
    workflow_run_id: str,
    notes: list[str],
) -> list[DocumentSegment]:
    """Create a prepared-remarks section plus speaker turns for a transcript."""

    segments: list[DocumentSegment] = []
    sequence_index = 0
    section_label = "q_and_a" if _contains_q_and_a(parsed_document_text.canonical_text) else "prepared_remarks"
    section = _make_segment(
        parsed_document_text=parsed_document_text,
        document_id=document.document_id,
        source_reference_id=document.source_reference_id,
        parent_segment_id=None,
        segment_kind=SegmentKind.SECTION,
        sequence_index=sequence_index,
        label=section_label,
        speaker=None,
        start_char=0,
        end_char=len(parsed_document_text.canonical_text),
        clock=clock,
        workflow_run_id=workflow_run_id,
        notes=notes,
    )
    segments.append(section)
    sequence_index += 1

    for start_char, end_char, label, speaker in _speaker_turn_spans(parsed_document_text.canonical_text):
        segments.append(
            _make_segment(
                parsed_document_text=parsed_document_text,
                document_id=document.document_id,
                source_reference_id=document.source_reference_id,
                parent_segment_id=section.document_segment_id,
                segment_kind=SegmentKind.SPEAKER_TURN,
                sequence_index=sequence_index,
                label=label,
                speaker=speaker,
                start_char=start_char,
                end_char=end_char,
                clock=clock,
                workflow_run_id=workflow_run_id,
                notes=notes,
            )
        )
        sequence_index += 1
    return segments


def _segment_news(
    *,
    parsed_document_text: ParsedDocumentText,
    document: NewsItem,
    clock: Clock,
    workflow_run_id: str,
    notes: list[str],
) -> list[DocumentSegment]:
    """Create headline, body, and body paragraph segments for a news item."""

    segments: list[DocumentSegment] = []
    sequence_index = 0
    assert parsed_document_text.headline_text is not None
    headline_end = len(parsed_document_text.headline_text)
    headline = _make_segment(
        parsed_document_text=parsed_document_text,
        document_id=document.document_id,
        source_reference_id=document.source_reference_id,
        parent_segment_id=None,
        segment_kind=SegmentKind.HEADLINE,
        sequence_index=sequence_index,
        label="headline",
        speaker=None,
        start_char=0,
        end_char=headline_end,
        clock=clock,
        workflow_run_id=workflow_run_id,
        notes=notes,
    )
    segments.append(headline)
    sequence_index += 1

    body_start = headline_end + 2
    body = _make_segment(
        parsed_document_text=parsed_document_text,
        document_id=document.document_id,
        source_reference_id=document.source_reference_id,
        parent_segment_id=None,
        segment_kind=SegmentKind.BODY,
        sequence_index=sequence_index,
        label="body",
        speaker=None,
        start_char=body_start,
        end_char=len(parsed_document_text.canonical_text),
        clock=clock,
        workflow_run_id=workflow_run_id,
        notes=notes,
    )
    segments.append(body)
    sequence_index += 1

    assert parsed_document_text.body_text is not None
    for paragraph_start, paragraph_end in _paragraph_spans(parsed_document_text.body_text):
        segments.append(
            _make_segment(
                parsed_document_text=parsed_document_text,
                document_id=document.document_id,
                source_reference_id=document.source_reference_id,
                parent_segment_id=body.document_segment_id,
                segment_kind=SegmentKind.PARAGRAPH,
                sequence_index=sequence_index,
                label="paragraph",
                speaker=None,
                start_char=body_start + paragraph_start,
                end_char=body_start + paragraph_end,
                clock=clock,
                workflow_run_id=workflow_run_id,
                notes=notes,
            )
        )
        sequence_index += 1
    return segments


def _make_segment(
    *,
    parsed_document_text: ParsedDocumentText,
    document_id: str,
    source_reference_id: str,
    parent_segment_id: str | None,
    segment_kind: SegmentKind,
    sequence_index: int,
    label: str | None,
    speaker: str | None,
    start_char: int,
    end_char: int,
    clock: Clock,
    workflow_run_id: str,
    notes: list[str],
) -> DocumentSegment:
    """Create a single parser-owned segment with exact offsets."""

    now = clock.now()
    text = parsed_document_text.canonical_text[start_char:end_char]
    return DocumentSegment(
        document_segment_id=make_canonical_id(
            "seg",
            parsed_document_text.parsed_document_text_id,
            segment_kind.value,
            str(sequence_index),
            str(start_char),
            str(end_char),
            label or "",
            speaker or "",
        ),
        parsed_document_text_id=parsed_document_text.parsed_document_text_id,
        document_id=document_id,
        source_reference_id=source_reference_id,
        parent_segment_id=parent_segment_id,
        segment_kind=segment_kind,
        sequence_index=sequence_index,
        label=label,
        speaker=speaker,
        text=text,
        start_char=start_char,
        end_char=end_char,
        provenance=build_provenance(
            clock=clock,
            transformation_name="document_segmentation",
            source_reference_ids=[source_reference_id],
            upstream_artifact_ids=[parsed_document_text.parsed_document_text_id],
            workflow_run_id=workflow_run_id,
            ingestion_time=parsed_document_text.provenance.ingestion_time,
            notes=notes,
        ),
        created_at=now,
        updated_at=now,
    )


def _normalize_inline_text(value: str) -> str:
    """Normalize inline text while preserving speaker labels and explicit paragraph breaks."""

    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = [" ".join(paragraph.split()) for paragraph in normalized.split("\n\n")]
    return "\n\n".join(paragraph for paragraph in paragraphs if paragraph).strip()


def _paragraph_spans(text: str) -> list[tuple[int, int]]:
    """Return exact paragraph spans from a normalized text block."""

    spans: list[tuple[int, int]] = []
    start_char = 0
    for match in re.finditer(r"\n\n", text):
        spans.append((start_char, match.start()))
        start_char = match.end()
    spans.append((start_char, len(text)))
    return [(start_char, end_char) for start_char, end_char in spans if end_char > start_char]


def _speaker_turn_spans(text: str) -> list[tuple[int, int, str, str]]:
    """Return exact speaker-turn spans from transcript text."""

    matches = list(
        re.finditer(
            r"(?P<header>[A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)*(?:, [A-Za-z][A-Za-z&./ -]+)?):",
            text,
        )
    )
    if not matches:
        return []

    spans: list[tuple[int, int, str, str]] = []
    for index, match in enumerate(matches):
        start_char = match.start()
        end_char = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        label = match.group("header").strip()
        speaker = label.split(",", 1)[0].strip()
        spans.append((start_char, end_char, label, speaker))
    return spans


def _contains_q_and_a(text: str) -> bool:
    """Detect whether transcript text explicitly signals a Q&A section."""

    return bool(re.search(r"\b(q&a|question-and-answer|questions and answers)\b", text, re.I))
