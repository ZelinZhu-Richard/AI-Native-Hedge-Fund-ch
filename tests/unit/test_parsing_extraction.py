from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from libraries.schemas import (
    ClaimType,
    DataLayer,
    DocumentEvidenceBundle,
    DocumentStatus,
    EarningsCall,
    ProvenanceRecord,
    SourceReference,
    SourceType,
)
from libraries.time import FrozenClock
from pipelines.document_processing import run_fixture_ingestion_pipeline
from services.ingestion.payloads import RawCompanyReference, RawTranscriptFixture
from services.parsing.extraction import build_document_evidence_bundle
from services.parsing.loaders import LoadedParsingInputs, load_parsing_inputs
from services.parsing.segmentation import build_parsed_document_text, segment_document

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
FIXED_NOW = datetime(2026, 3, 16, 14, 30, tzinfo=UTC)


def test_evidence_spans_align_to_canonical_text(tmp_path: Path) -> None:
    bundle = _build_fixture_bundle(
        fixture_relative_path=Path("filings") / "apex_q1_2026_10q.json",
        artifact_root=tmp_path / "ingestion",
    )

    assert bundle.evidence_spans
    for span in bundle.evidence_spans:
        assert span.segment_id is not None
        assert bundle.parsed_document_text.canonical_text[span.start_char : span.end_char] == span.text


def test_filing_fixture_extracts_claim_and_guidance(tmp_path: Path) -> None:
    bundle = _build_fixture_bundle(
        fixture_relative_path=Path("filings") / "apex_q1_2026_10q.json",
        artifact_root=tmp_path / "ingestion",
    )

    assert {claim.claim_type for claim in bundle.claims} >= {
        ClaimType.FINANCIAL_RESULT,
        ClaimType.OUTLOOK_STATEMENT,
    }
    assert {change.direction.value for change in bundle.guidance_changes} == {"maintained"}


def test_news_fixture_does_not_create_guidance_from_generic_future_sentence(tmp_path: Path) -> None:
    bundle = _build_fixture_bundle(
        fixture_relative_path=Path("news") / "apex_launch_news.json",
        artifact_root=tmp_path / "ingestion",
    )

    assert bundle.guidance_changes == []
    assert {claim.claim_type for claim in bundle.claims} >= {
        ClaimType.PRODUCT_UPDATE,
        ClaimType.TIMELINE_STATEMENT,
    }


def test_synthetic_transcript_extracts_risk_and_tone_markers() -> None:
    inputs = _make_synthetic_transcript_inputs(
        "Chief Operating Officer, COO: We may delay the rollout because regulatory risk and margin pressure remain elevated."
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
    bundle = build_document_evidence_bundle(
        parsed_document_text=parsed_document_text,
        segments=segments,
        inputs=inputs,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="parse_test",
        notes=[],
    )

    assert bundle.risk_factors
    assert {marker.marker_type.value for marker in bundle.tone_markers} >= {"caution", "uncertainty"}
    assert bundle.evaluation.passed


def test_evaluation_fails_unresolved_references(tmp_path: Path) -> None:
    bundle = _build_fixture_bundle(
        fixture_relative_path=Path("transcripts") / "apex_q1_2026_call.json",
        artifact_root=tmp_path / "ingestion",
    )
    broken_claim = bundle.claims[0].model_copy(update={"segment_id": "seg_missing"})
    broken_bundle = bundle.model_copy(update={"claims": [broken_claim]})

    assert broken_bundle.evaluation.reference_integrity_ok

    from services.parsing.evals import evaluate_document_evidence_bundle

    evaluation = evaluate_document_evidence_bundle(
        parsed_document_text=broken_bundle.parsed_document_text,
        segments=broken_bundle.segments,
        evidence_spans=broken_bundle.evidence_spans,
        claims=broken_bundle.claims,
        risk_factors=broken_bundle.risk_factors,
        guidance_changes=broken_bundle.guidance_changes,
        tone_markers=broken_bundle.tone_markers,
        clock=FrozenClock(FIXED_NOW),
    )

    assert not evaluation.reference_integrity_ok
    assert not evaluation.passed


def _build_fixture_bundle(
    *, fixture_relative_path: Path, artifact_root: Path
) -> DocumentEvidenceBundle:
    run_fixture_ingestion_pipeline(
        fixtures_root=FIXTURE_ROOT.parent / "ingestion",
        output_root=artifact_root,
        clock=FrozenClock(FIXED_NOW),
    )
    fixture_name = fixture_relative_path.name
    if fixture_name.endswith("10q.json"):
        category = "filings"
    elif "call" in fixture_name:
        category = "earnings_calls"
    else:
        category = "news_items"
    document_path = next((artifact_root / "normalized" / category).glob("*.json"))
    inputs = load_parsing_inputs(
        document_path=document_path,
        source_reference_path=artifact_root
        / "normalized"
        / "source_references"
        / f"{_document_source_reference_id(document_path)}.json",
        raw_payload_path=artifact_root
        / "raw"
        / _fixture_type_for_category(category)
        / f"{_document_source_reference_id(document_path)}.json",
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
    return build_document_evidence_bundle(
        parsed_document_text=parsed_document_text,
        segments=segments,
        inputs=inputs,
        clock=FrozenClock(FIXED_NOW),
        workflow_run_id="parse_test",
        notes=[],
    )


def _document_source_reference_id(document_path: Path) -> str:
    import json

    payload = json.loads(document_path.read_text(encoding="utf-8"))
    return str(payload["source_reference_id"])


def _fixture_type_for_category(category: str) -> str:
    return {
        "filings": "filing",
        "earnings_calls": "earnings_call",
        "news_items": "news_item",
    }[category]


def _make_synthetic_transcript_inputs(text: str) -> LoadedParsingInputs:
    now = FIXED_NOW
    source_reference = SourceReference(
        source_reference_id="src_synthetic",
        source_type=SourceType.EARNINGS_TRANSCRIPT_VENDOR,
        external_id="transcript:synthetic",
        uri="transcripts://synthetic/test",
        title="Synthetic Transcript",
        publisher="Synthetic Vendor",
        content_hash="hash",
        published_at=now,
        retrieved_at=now,
        effective_at=now,
        license=None,
        provenance=ProvenanceRecord(
            source_reference_ids=[],
            transformation_name="unit_test",
            processing_time=now,
        ),
        created_at=now,
        updated_at=now,
    )
    document = EarningsCall(
        document_id="doc_synthetic",
        company_id="co_test",
        title="Synthetic Earnings Call",
        source_reference_id=source_reference.source_reference_id,
        external_id="transcript:synthetic",
        data_layer=DataLayer.NORMALIZED,
        language="en",
        storage_uri=None,
        content_hash="hash",
        source_published_at=now,
        effective_at=now,
        ingested_at=now,
        processed_at=now,
        status=DocumentStatus.NORMALIZED,
        tags=[],
        provenance=ProvenanceRecord(
            source_reference_ids=[source_reference.source_reference_id],
            transformation_name="unit_test",
            processing_time=now,
        ),
        created_at=now,
        updated_at=now,
        call_datetime=now,
        fiscal_year=2026,
        fiscal_quarter=1,
        prepared_remarks_uri=None,
        q_and_a_uri=None,
        participants=["Chief Operating Officer"],
    )
    raw_payload = RawTranscriptFixture(
        fixture_name="synthetic_transcript",
        source_type=SourceType.EARNINGS_TRANSCRIPT_VENDOR,
        external_id="transcript:synthetic",
        uri="transcripts://synthetic/test",
        title="Synthetic Transcript",
        published_at=now,
        retrieved_at=now,
        effective_at=None,
        company=RawCompanyReference(
            legal_name="Synthetic Co",
            ticker="SYN",
            exchange="NASDAQ",
            cik="0000000001",
            country_of_risk="US",
        ),
        call_datetime=now,
        fiscal_year=2026,
        fiscal_quarter=1,
        participants=["Chief Operating Officer"],
        raw_text=text,
    )
    return LoadedParsingInputs(
        document_path=Path("synthetic_document.json"),
        source_reference_path=Path("synthetic_source_reference.json"),
        raw_payload_path=Path("synthetic_raw_payload.json"),
        document=document,
        source_reference=source_reference,
        raw_payload=raw_payload,
    )
