from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRODUCT_DOCS = ROOT / "docs" / "product"
PLANS_DOCS = ROOT / "docs" / "plans"


def test_day30_release_candidate_docs_exist() -> None:
    required_paths = [
        PRODUCT_DOCS / "release_candidate_status.md",
        PRODUCT_DOCS / "known_limitations.md",
        PLANS_DOCS / "day30_plan.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required_paths if not path.exists()]
    assert not missing, f"Missing Day 30 release-candidate docs: {missing}"


def test_readme_and_demo_docs_use_release_candidate_paths_and_current_review_docs() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    demo_doc = (PRODUCT_DOCS / "end_to_end_demo.md").read_text(encoding="utf-8")
    demo_usability = (PRODUCT_DOCS / "demo_usability.md").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "artifacts/demo_runs/release_candidate" in readme
    assert "artifacts/demo_runs/release_candidate" in demo_doc
    assert "artifacts/demo_runs/release_candidate" in demo_usability
    assert "artifacts/demo_runs/week3_demo" not in readme
    assert "artifacts/demo_runs/week3_demo" not in demo_doc
    assert "artifacts/demo_runs/week3_demo" not in demo_usability
    assert "docs/reviews/week4_review.md" in readme
    assert "docs/plans/final_30_day_push.md" in readme
    assert "docs/product/release_candidate_status.md" in readme
    assert "docs/product/known_limitations.md" in readme
    assert "artifacts/demo_runs/release_candidate" in makefile


def test_readme_quickstart_prioritizes_verification_before_formatting() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    lint_index = readme.index("make lint")
    typecheck_index = readme.index("make typecheck")
    test_index = readme.index("make test")
    format_index = readme.index("make format")

    assert lint_index < typecheck_index < test_index < format_index


def test_readme_intro_keeps_thesis_framing_and_nonproof_limits_visible() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()

    assert "attempt to answer a simple question" in readme
    assert "what would an ai-native hedge fund research stack look like" in readme
    assert "projects are shallow" in readme
    assert "research operating system" in readme
    assert "approval-gated paper trading" in readme
    assert "it does **not** yet prove" in readme
    assert "validated alpha" in readme
    assert "live-market readiness" in readme
    assert (
        "ingestion -> normalization -> evidence extraction -> hypothesis + critique"
        in readme
    )


def test_release_candidate_docs_keep_required_limitations_visible() -> None:
    release_candidate_status = (PRODUCT_DOCS / "release_candidate_status.md").read_text(
        encoding="utf-8"
    )
    known_limitations = (PRODUCT_DOCS / "known_limitations.md").read_text(encoding="utf-8")

    required_truths = [
        "no true reviewed-and-evaluated downstream eligibility gate yet",
        "no full selected-artifact or snapshot-native enforcement yet",
        "no first-class instrument/security layer",
        "no live trading or broker execution",
        "no validated market edge or performance claim",
    ]

    for truth in required_truths:
        assert truth in release_candidate_status

    limitation_groups = [
        "## Data Quality And Contract Enforcement",
        "## Temporal Selection And Replay Discipline",
        "## Evaluation And Readiness",
        "## Portfolio And Risk",
        "## Paper Trading And Ledger",
        "## Reporting And Interface",
        "## Infrastructure And Operations",
    ]

    for group in limitation_groups:
        assert group in known_limitations


def test_cli_transition_uses_nta_as_primary_and_keeps_anhf_alias() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    api_contracts = (PRODUCT_DOCS / "api_and_interface_contracts.md").read_text(
        encoding="utf-8"
    )
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    cli_source = (ROOT / "apps" / "cli" / "main.py").read_text(encoding="utf-8")

    for command in [
        "nta demo run",
        "nta daily run",
        "nta capabilities",
        "nta manifest",
    ]:
        assert command in readme

    assert 'nta = "apps.cli.main:main"' in pyproject
    assert 'anhf = "apps.cli.main:main"' in pyproject
    assert 'prog="nta"' in cli_source
    assert "legacy `anhf` alias" in readme.lower()
    assert "legacy `anhf` alias" in api_contracts.lower()
