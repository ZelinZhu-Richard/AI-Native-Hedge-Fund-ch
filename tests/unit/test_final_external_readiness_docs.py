from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRODUCT_DOCS = ROOT / "docs" / "product"
REVIEWS_DOCS = ROOT / "docs" / "reviews"


def test_final_external_readiness_review_exists() -> None:
    assert (REVIEWS_DOCS / "final_external_readiness_review.md").exists()


def test_final_external_review_and_closeout_docs_keep_major_gaps_aligned() -> None:
    external_review = (REVIEWS_DOCS / "final_external_readiness_review.md").read_text(
        encoding="utf-8"
    ).lower()
    final_review = (REVIEWS_DOCS / "final_30_day_review.md").read_text(encoding="utf-8").lower()
    release_candidate_status = (
        PRODUCT_DOCS / "release_candidate_status.md"
    ).read_text(encoding="utf-8").lower()
    known_limitations = (PRODUCT_DOCS / "known_limitations.md").read_text(encoding="utf-8").lower()
    maturity_scorecard = (
        PRODUCT_DOCS / "project_maturity_scorecard.md"
    ).read_text(encoding="utf-8").lower()

    required_truths = [
        "reviewed-and-evaluated downstream eligibility gate",
        "selected-artifact",
        "instrument/security layer",
        "live trading",
        "validated alpha",
    ]

    for truth in required_truths:
        assert truth in external_review
        assert truth in final_review
        assert truth in release_candidate_status

    assert "selected-artifact" in known_limitations
    assert "paper trading and ledger" in known_limitations
    assert "evaluation | 2" in maturity_scorecard
    assert "paper trading | 2" in maturity_scorecard


def test_readme_and_proof_docs_reference_final_external_review_and_real_commands() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    end_to_end_demo = (PRODUCT_DOCS / "end_to_end_demo.md").read_text(encoding="utf-8")
    proof_inventory = (PRODUCT_DOCS / "proof_artifact_inventory.md").read_text(
        encoding="utf-8"
    )
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "docs/reviews/final_external_readiness_review.md" in readme
    assert "make final-proof" in readme
    assert "python -m pipelines.demo.final_30_day_proof" in readme
    assert "make final-proof" in end_to_end_demo
    assert "docs/reviews/final_external_readiness_review.md" in proof_inventory
    assert "\nfinal-proof:" in makefile
