from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from apps.cli.main import main

ROOT = Path(__file__).resolve().parents[2]
PRODUCT_DOCS = ROOT / "docs" / "product"
PLANS_DOCS = ROOT / "docs" / "plans"
REQUIRED_DOCS = [
    PRODUCT_DOCS / "founder_narrative.md",
    PRODUCT_DOCS / "technical_narrative.md",
    PRODUCT_DOCS / "quant_research_narrative.md",
    PRODUCT_DOCS / "operator_and_risk_narrative.md",
    PRODUCT_DOCS / "proof_artifact_inventory.md",
    PRODUCT_DOCS / "project_maturity_scorecard.md",
    PRODUCT_DOCS / "demo_script.md",
    PLANS_DOCS / "day29_plan.md",
]
PATH_PREFIXES = (
    "docs/",
    "apps/",
    "libraries/",
    "services/",
    "pipelines/",
    "tests/",
    "README.md",
    "Makefile",
    "pyproject.toml",
    "AGENTS.md",
    "PLAN.md",
)
REQUIRED_CAPABILITY_ANCHORS = {
    "ingestion",
    "parsing",
    "data_quality",
    "evaluation",
    "operator_review",
    "paper_ledger",
    "reporting",
    "signal_arbitration",
    "daily_workflow",
    "demo_end_to_end",
}
REQUIRED_DEMO_REFERENCES = [
    "nta manifest",
    "nta capabilities",
    "make demo",
    "make api",
    "make daily-run",
    "GET /system/manifest",
    "GET /portfolio/proposals",
    "GET /reports/proposals/{portfolio_proposal_id}/scorecard",
    "GET /reviews/queue",
]
REQUIRED_MATURITY_AREAS = {
    "data integrity": "3",
    "temporal correctness": "3",
    "reproducibility": "3",
    "evaluation": "2",
    "operator workflow": "3",
    "risk controls": "2",
    "paper trading": "2",
    "reporting": "2",
    "interface quality": "3",
}


def test_day29_docs_exist() -> None:
    missing = [str(path.relative_to(ROOT)) for path in REQUIRED_DOCS if not path.exists()]
    assert not missing, f"Missing Day 29 proof docs: {missing}"


def test_proof_inventory_references_real_paths_and_live_capabilities(
    capsys: pytest.CaptureFixture[str],
) -> None:
    inventory = (PRODUCT_DOCS / "proof_artifact_inventory.md").read_text(encoding="utf-8")
    referenced_paths = {
        value
        for value in re.findall(r"`([^`]+)`", inventory)
        if value.startswith(PATH_PREFIXES)
    }
    missing_paths = sorted(
        path for path in referenced_paths if not (ROOT / path).exists()
    )
    assert not missing_paths, f"Broken proof inventory references: {missing_paths}"

    exit_code = main(["capabilities", "--json"])
    payload = json.loads(capsys.readouterr().out)
    capability_names = {item["name"] for item in payload["items"]}

    assert exit_code == 0
    for capability_name in REQUIRED_CAPABILITY_ANCHORS:
        assert f"`{capability_name}`" in inventory
        assert capability_name in capability_names


def test_demo_script_matches_supported_entrypoints() -> None:
    demo_script = (PRODUCT_DOCS / "demo_script.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    cli_source = (ROOT / "apps" / "cli" / "main.py").read_text(encoding="utf-8")
    api_test = (ROOT / "tests" / "integration" / "test_api.py").read_text(encoding="utf-8")

    for reference in REQUIRED_DEMO_REFERENCES:
        assert reference in demo_script

    assert 'prog="nta"' in cli_source
    assert "manifest" in cli_source
    assert "capabilities" in cli_source
    assert 'add_parser("demo"' in cli_source
    assert 'add_parser("daily"' in cli_source
    assert 'add_parser("review"' in cli_source
    assert "legacy `anhf` alias" in readme.lower()
    assert "\napi:" in makefile
    assert "\ndemo:" in makefile
    assert "\ndaily-run:" in makefile
    assert "/system/manifest" in api_test
    assert "/portfolio/proposals" in api_test
    assert "/reports/proposals/" in api_test
    assert "/reviews/queue" in api_test


def test_maturity_scorecard_has_required_areas_and_ratings() -> None:
    scorecard = (PRODUCT_DOCS / "project_maturity_scorecard.md").read_text(encoding="utf-8")
    rows = {
        match.group("area").strip(): match.group("rating").strip()
        for match in re.finditer(
            r"^\|\s*(?P<area>[^|]+?)\s*\|\s*(?P<rating>[0-4])\s*\|",
            scorecard,
            flags=re.MULTILINE,
        )
        if match.group("area").strip().lower() != "area"
    }

    assert rows == REQUIRED_MATURITY_AREAS
