from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.cli.main import main
from libraries.config import get_settings

FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "ingestion"


def test_capabilities_cli_json_outputs_normalized_descriptors(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["capabilities", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["total"] >= 1
    assert any(item["kind"] == "workflow" and item["name"] == "daily_workflow" for item in payload["items"])


def test_demo_and_daily_cli_json_smoke(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    artifact_root = tmp_path / "artifacts"
    monkeypatch.setenv("ARTIFACT_ROOT", str(artifact_root))
    get_settings.cache_clear()
    try:
        demo_exit = main(
            [
                "demo",
                "run",
                "--base-root",
                str(tmp_path / "demo_run"),
                "--json",
            ]
        )
        demo_payload = json.loads(capsys.readouterr().out)
        assert demo_exit == 0
        assert demo_payload["workflow_name"] == "demo_end_to_end"
        assert Path(demo_payload["manifest_path"]).exists()

        daily_exit = main(
            [
                "daily",
                "run",
                "--artifact-root",
                str(tmp_path / "daily_run"),
                "--fixtures-root",
                str(FIXTURE_ROOT),
                "--json",
            ]
        )
        daily_payload = json.loads(capsys.readouterr().out)
        assert daily_exit == 0
        assert daily_payload["workflow_name"] == "daily_workflow"
        assert daily_payload["artifact_root"] == str(tmp_path / "daily_run")
    finally:
        get_settings.cache_clear()
