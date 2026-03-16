from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from libraries.schemas import EarningsCall, Filing, NewsItem
from libraries.time import FrozenClock
from services.ingestion import FixtureIngestionRequest, IngestionService
from services.parsing.loaders import LoadedParsingInputs, load_parsing_inputs
from services.parsing.segmentation import build_parsed_document_text, segment_document

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
FIXED_NOW = datetime(2026, 3, 16, 14, 30, tzinfo=UTC)


def test_filing_segmentation_creates_body_section_and_paragraph(tmp_path: Path) -> None:
    inputs = _prepare_inputs(
        fixture_relative_path=Path("filings") / "apex_q1_2026_10q.json",
        artifact_root=tmp_path / "ingestion",
    )

    parsed_document_text = build_parsed_document_text(
        inputs=inputs,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="parse_test",
        notes=[],
    )
    segments = segment_document(
        parsed_document_text=parsed_document_text,
        inputs=inputs,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="parse_test",
        notes=[],
    )

    assert parsed_document_text.canonical_text == inputs.raw_payload.raw_text
    assert [segment.segment_kind.value for segment in segments] == ["section", "paragraph"]
    assert segments[0].label == "body"
    assert segments[1].text == parsed_document_text.canonical_text


def test_transcript_segmentation_creates_speaker_turns(tmp_path: Path) -> None:
    inputs = _prepare_inputs(
        fixture_relative_path=Path("transcripts") / "apex_q1_2026_call.json",
        artifact_root=tmp_path / "ingestion",
    )

    parsed_document_text = build_parsed_document_text(
        inputs=inputs,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="parse_test",
        notes=[],
    )
    segments = segment_document(
        parsed_document_text=parsed_document_text,
        inputs=inputs,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="parse_test",
        notes=[],
    )

    speaker_turns = [segment for segment in segments if segment.segment_kind.value == "speaker_turn"]
    assert segments[0].label == "prepared_remarks"
    assert [segment.speaker for segment in speaker_turns] == ["Maya Chen", "David Ortiz"]
    assert speaker_turns[0].text.startswith("Maya Chen, CEO:")
    assert speaker_turns[1].text.startswith("David Ortiz, CFO:")


def test_news_segmentation_creates_headline_and_body_offsets(tmp_path: Path) -> None:
    inputs = _prepare_inputs(
        fixture_relative_path=Path("news") / "apex_launch_news.json",
        artifact_root=tmp_path / "ingestion",
    )

    parsed_document_text = build_parsed_document_text(
        inputs=inputs,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="parse_test",
        notes=[],
    )
    segments = segment_document(
        parsed_document_text=parsed_document_text,
        inputs=inputs,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="parse_test",
        notes=[],
    )

    headline, body, paragraph = segments
    assert headline.segment_kind.value == "headline"
    assert body.segment_kind.value == "body"
    assert paragraph.segment_kind.value == "paragraph"
    assert body.start_char == len(parsed_document_text.headline_text or "") + 2
    assert parsed_document_text.canonical_text[headline.start_char : headline.end_char] == headline.text
    assert parsed_document_text.canonical_text[body.start_char : body.end_char] == body.text


def _prepare_inputs(*, fixture_relative_path: Path, artifact_root: Path) -> LoadedParsingInputs:
    fixture_path = FIXTURE_ROOT / fixture_relative_path
    service = IngestionService(clock=FrozenClock(FIXED_NOW))
    response = service.ingest_fixture(
        FixtureIngestionRequest(
            fixture_path=fixture_path,
            output_root=artifact_root,
            requested_by="unit_test",
        )
    )
    document = response.filing or response.earnings_call or response.news_item
    assert document is not None
    return load_parsing_inputs(
        document_path=_document_path(artifact_root=artifact_root, document=document),
        source_reference_path=artifact_root
        / "normalized"
        / "source_references"
        / f"{response.source_reference.source_reference_id}.json",
        raw_payload_path=artifact_root
        / "raw"
        / response.fixture_type
        / f"{response.source_reference.source_reference_id}.json",
    )


def _document_path(*, artifact_root: Path, document: Filing | EarningsCall | NewsItem) -> Path:
    if hasattr(document, "form_type"):
        category = "filings"
    elif hasattr(document, "call_datetime"):
        category = "earnings_calls"
    else:
        category = "news_items"
    return artifact_root / "normalized" / category / f"{document.document_id}.json"
