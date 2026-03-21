from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from libraries.schemas import GuidanceChange, ResearchBrief, Signal
from libraries.time import FrozenClock
from pipelines.daily_research import run_hypothesis_workflow_pipeline
from pipelines.document_processing import (
    run_evidence_extraction_pipeline,
    run_fixture_ingestion_pipeline,
)
from pipelines.signal_generation import run_feature_signal_pipeline
from services.feature_store.loaders import load_feature_mapping_inputs
from services.portfolio.loaders import load_portfolio_inputs
from services.signal_generation.loaders import load_signal_generation_inputs

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"
BASE_TIME = datetime(2026, 3, 17, 11, 0, tzinfo=UTC)
LATER_TIME = BASE_TIME + timedelta(days=1)
CUTOFF_TIME = BASE_TIME + timedelta(hours=12)


def test_feature_mapping_loader_respects_as_of_time(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    _build_ingestion_and_parsing(artifact_root=artifact_root, clock_time=BASE_TIME)
    run_hypothesis_workflow_pipeline(
        ingestion_root=artifact_root / "ingestion",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "research",
        clock=FrozenClock(BASE_TIME),
    )
    _duplicate_research_brief_with_later_timestamp(
        research_root=artifact_root / "research",
        later_time=LATER_TIME,
    )
    _duplicate_parsing_artifact_with_later_timestamp(
        directory=artifact_root / "parsing" / "guidance_changes",
        later_time=LATER_TIME,
    )

    loaded = load_feature_mapping_inputs(
        research_root=artifact_root / "research",
        parsing_root=artifact_root / "parsing",
        as_of_time=CUTOFF_TIME,
    )

    assert loaded.research_brief is not None
    assert loaded.research_brief.created_at == BASE_TIME
    assert loaded.evidence_assessment.created_at == BASE_TIME
    assert all(change.created_at <= CUTOFF_TIME for change in loaded.guidance_changes)


def test_signal_generation_loader_respects_as_of_time(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    _build_ingestion_and_parsing(artifact_root=artifact_root, clock_time=BASE_TIME)
    run_hypothesis_workflow_pipeline(
        ingestion_root=artifact_root / "ingestion",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "research",
        clock=FrozenClock(BASE_TIME),
    )
    run_feature_signal_pipeline(
        research_root=artifact_root / "research",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "signal_generation",
        clock=FrozenClock(BASE_TIME),
    )
    _duplicate_feature_and_research_brief_with_later_timestamps(
        signal_generation_root=artifact_root / "signal_generation",
        research_root=artifact_root / "research",
        later_time=LATER_TIME,
    )

    loaded = load_signal_generation_inputs(
        feature_root=artifact_root / "signal_generation",
        research_root=artifact_root / "research",
        as_of_time=CUTOFF_TIME,
    )

    assert len(loaded.features) == 6
    assert all(feature.feature_value.available_at <= CUTOFF_TIME for feature in loaded.features)
    assert loaded.research_brief is not None
    assert loaded.research_brief.created_at == BASE_TIME


def test_portfolio_loader_respects_as_of_time(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    _build_ingestion_and_parsing(artifact_root=artifact_root, clock_time=BASE_TIME)
    run_hypothesis_workflow_pipeline(
        ingestion_root=artifact_root / "ingestion",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "research",
        clock=FrozenClock(BASE_TIME),
    )
    run_feature_signal_pipeline(
        research_root=artifact_root / "research",
        parsing_root=artifact_root / "parsing",
        output_root=artifact_root / "signal_generation",
        clock=FrozenClock(BASE_TIME),
    )
    later_signal_id = _duplicate_signal_with_later_timestamp(
        signal_root=artifact_root / "signal_generation",
        later_time=LATER_TIME,
    )

    loaded = load_portfolio_inputs(
        signal_root=artifact_root / "signal_generation",
        research_root=artifact_root / "research",
        ingestion_root=artifact_root / "ingestion",
        backtesting_root=None,
        as_of_time=CUTOFF_TIME,
    )

    loaded_signal_ids = {signal.signal_id for signal in loaded.signals}
    assert later_signal_id not in loaded_signal_ids
    assert all(signal.effective_at <= CUTOFF_TIME for signal in loaded.signals)


def _build_ingestion_and_parsing(*, artifact_root: Path, clock_time: datetime) -> None:
    run_fixture_ingestion_pipeline(
        fixtures_root=FIXTURE_ROOT,
        output_root=artifact_root / "ingestion",
        clock=FrozenClock(clock_time),
    )
    run_evidence_extraction_pipeline(
        ingestion_root=artifact_root / "ingestion",
        output_root=artifact_root / "parsing",
        clock=FrozenClock(clock_time),
    )


def _duplicate_parsing_artifact_with_later_timestamp(
    *,
    directory: Path,
    later_time: datetime,
) -> None:
    source_path = next(directory.glob("*.json"))
    model = GuidanceChange.model_validate_json(source_path.read_text(encoding="utf-8"))
    later_model = model.model_copy(
        update={
            "guidance_change_id": f"{model.guidance_change_id}_later",
            "created_at": later_time,
            "updated_at": later_time,
            "provenance": model.provenance.model_copy(update={"processing_time": later_time}),
        }
    )
    later_path = directory / f"{later_model.guidance_change_id}.json"
    later_path.write_text(later_model.model_dump_json(indent=2), encoding="utf-8")


def _duplicate_feature_and_research_brief_with_later_timestamps(
    *,
    signal_generation_root: Path,
    research_root: Path,
    later_time: datetime,
) -> None:
    feature_path = next((signal_generation_root / "features").glob("*.json"))
    feature_payload = json.loads(feature_path.read_text(encoding="utf-8"))
    feature_payload["feature_id"] = f"{feature_payload['feature_id']}_later"
    feature_payload["created_at"] = later_time.isoformat().replace("+00:00", "Z")
    feature_payload["updated_at"] = later_time.isoformat().replace("+00:00", "Z")
    feature_payload["feature_value"]["feature_value_id"] = (
        f"{feature_payload['feature_value']['feature_value_id']}_later"
    )
    feature_payload["feature_value"]["available_at"] = later_time.isoformat().replace(
        "+00:00", "Z"
    )
    feature_payload["feature_value"]["availability_window"]["available_from"] = (
        later_time.isoformat().replace("+00:00", "Z")
    )
    feature_payload["feature_value"]["created_at"] = later_time.isoformat().replace(
        "+00:00", "Z"
    )
    feature_payload["feature_value"]["updated_at"] = later_time.isoformat().replace(
        "+00:00", "Z"
    )
    feature_payload["lineage"]["feature_lineage_id"] = (
        f"{feature_payload['lineage']['feature_lineage_id']}_later"
    )
    duplicate_feature_path = signal_generation_root / "features" / f"{feature_payload['feature_id']}.json"
    duplicate_feature_path.write_text(json.dumps(feature_payload, indent=2), encoding="utf-8")

    brief_path = next((research_root / "research_briefs").glob("*.json"))
    brief = ResearchBrief.model_validate_json(brief_path.read_text(encoding="utf-8"))
    later_brief = brief.model_copy(
        update={
            "research_brief_id": f"{brief.research_brief_id}_later",
            "created_at": later_time,
            "updated_at": later_time,
            "provenance": brief.provenance.model_copy(update={"processing_time": later_time}),
        }
    )
    later_brief_path = research_root / "research_briefs" / f"{later_brief.research_brief_id}.json"
    later_brief_path.write_text(later_brief.model_dump_json(indent=2), encoding="utf-8")


def _duplicate_research_brief_with_later_timestamp(
    *,
    research_root: Path,
    later_time: datetime,
) -> None:
    brief_path = next((research_root / "research_briefs").glob("*.json"))
    brief = ResearchBrief.model_validate_json(brief_path.read_text(encoding="utf-8"))
    later_brief = brief.model_copy(
        update={
            "research_brief_id": f"{brief.research_brief_id}_later",
            "created_at": later_time,
            "updated_at": later_time,
            "provenance": brief.provenance.model_copy(update={"processing_time": later_time}),
        }
    )
    later_brief_path = research_root / "research_briefs" / f"{later_brief.research_brief_id}.json"
    later_brief_path.write_text(later_brief.model_dump_json(indent=2), encoding="utf-8")


def _duplicate_signal_with_later_timestamp(
    *,
    signal_root: Path,
    later_time: datetime,
) -> str:
    signal_path = next((signal_root / "signals").glob("*.json"))
    signal = Signal.model_validate_json(signal_path.read_text(encoding="utf-8"))
    later_signal = signal.model_copy(
        update={
            "signal_id": f"{signal.signal_id}_later",
            "effective_at": later_time,
            "availability_window": (
                signal.availability_window.model_copy(update={"available_from": later_time})
                if signal.availability_window is not None
                else None
            ),
            "created_at": later_time,
            "updated_at": later_time,
            "provenance": signal.provenance.model_copy(update={"processing_time": later_time}),
        }
    )
    later_signal_path = signal_root / "signals" / f"{later_signal.signal_id}.json"
    later_signal_path.write_text(later_signal.model_dump_json(indent=2), encoding="utf-8")
    return later_signal.signal_id
