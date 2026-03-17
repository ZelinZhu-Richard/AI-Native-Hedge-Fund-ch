from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from libraries.time import FrozenClock
from pipelines.daily_research import run_hypothesis_workflow_pipeline
from pipelines.document_processing import (
    run_evidence_extraction_pipeline,
    run_fixture_ingestion_pipeline,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"


def test_research_workflow_pipeline_persists_artifacts(tmp_path: Path) -> None:
    fixed_now = datetime(2026, 3, 16, 14, 30, tzinfo=UTC)
    artifact_root = tmp_path / "artifacts"

    run_fixture_ingestion_pipeline(
        fixtures_root=FIXTURE_ROOT,
        output_root=artifact_root / "ingestion",
        clock=FrozenClock(fixed_now),
    )
    run_evidence_extraction_pipeline(
        ingestion_root=artifact_root / "ingestion",
        output_root=artifact_root / "parsing",
        clock=FrozenClock(fixed_now),
    )
    response = run_hypothesis_workflow_pipeline(
        ingestion_root=artifact_root / "ingestion",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "research",
        clock=FrozenClock(fixed_now),
    )

    assert response.status == "completed"
    assert response.hypothesis is not None
    assert response.counter_hypothesis is not None
    assert response.research_brief is not None
    assert response.memo is not None
    assert (artifact_root / "research" / "hypotheses" / f"{response.hypothesis.hypothesis_id}.json").exists()
    assert (
        artifact_root
        / "research"
        / "counter_hypotheses"
        / f"{response.counter_hypothesis.counter_hypothesis_id}.json"
    ).exists()
    assert (
        artifact_root
        / "research"
        / "research_briefs"
        / f"{response.research_brief.research_brief_id}.json"
    ).exists()
    assert (artifact_root / "research" / "memos" / f"{response.memo.memo_id}.json").exists()
    hypothesis_payload = json.loads(
        (
            artifact_root / "research" / "hypotheses" / f"{response.hypothesis.hypothesis_id}.json"
        ).read_text(encoding="utf-8")
    )
    assessment_payload = json.loads(
        (
            artifact_root
            / "research"
            / "evidence_assessments"
            / f"{response.evidence_assessment.evidence_assessment_id}.json"
        ).read_text(encoding="utf-8")
    )
    brief_payload = json.loads(
        (
            artifact_root
            / "research"
            / "research_briefs"
            / f"{response.research_brief.research_brief_id}.json"
        ).read_text(encoding="utf-8")
    )
    assert hypothesis_payload["validation_status"] == response.hypothesis.validation_status.value
    assert assessment_payload["validation_status"] == response.evidence_assessment.validation_status.value
    assert brief_payload["validation_status"] == response.research_brief.validation_status.value
    parsing_span_ids = {
        path.stem for path in (artifact_root / "parsing" / "evidence_spans").glob("*.json")
    }
    assert {
        link.evidence_span_id for link in response.hypothesis.supporting_evidence_links
    } <= parsing_span_ids
