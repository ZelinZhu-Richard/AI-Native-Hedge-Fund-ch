from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRODUCT_DOCS = ROOT / "docs" / "product"
PLANS_DOCS = ROOT / "docs" / "plans"
REVIEWS_DOCS = ROOT / "docs" / "reviews"


def test_final_30_day_docs_exist() -> None:
    required_paths = [
        REVIEWS_DOCS / "final_30_day_review.md",
        PLANS_DOCS / "phase2_roadmap.md",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required_paths if not path.exists()]
    assert not missing, f"Missing final 30-day docs: {missing}"


def test_readme_and_demo_docs_reference_final_proof_and_phase2_materials() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    end_to_end_demo = (PRODUCT_DOCS / "end_to_end_demo.md").read_text(encoding="utf-8")
    demo_script = (PRODUCT_DOCS / "demo_script.md").read_text(encoding="utf-8")
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")

    assert "make final-proof" in readme
    assert "docs/reviews/final_30_day_review.md" in readme
    assert "docs/plans/phase2_roadmap.md" in readme
    assert "make final-proof" in end_to_end_demo
    assert "python -m pipelines.demo.final_30_day_proof" in end_to_end_demo
    assert "make final-proof" in demo_script
    assert "\nfinal-proof:" in makefile
    assert "pipelines.demo.final_30_day_proof" in makefile


def test_final_review_and_release_docs_keep_major_gaps_visible() -> None:
    final_review = (REVIEWS_DOCS / "final_30_day_review.md").read_text(encoding="utf-8").lower()
    release_candidate_status = (
        PRODUCT_DOCS / "release_candidate_status.md"
    ).read_text(encoding="utf-8").lower()
    known_limitations = (PRODUCT_DOCS / "known_limitations.md").read_text(encoding="utf-8").lower()

    required_truths = [
        "no true reviewed-and-evaluated downstream eligibility gate",
        "no full selected-artifact",
        "no first-class instrument/security layer",
        "no live trading",
        "no validated alpha",
    ]

    for truth in required_truths:
        assert truth in final_review
        assert truth in release_candidate_status

    assert "selected-artifact" in known_limitations
    assert "paper trading and ledger" in known_limitations


def test_phase2_roadmap_contains_ordered_phase2_priorities() -> None:
    roadmap = (PLANS_DOCS / "phase2_roadmap.md").read_text(encoding="utf-8").lower()

    required_topics = [
        "downstream eligibility enforcement",
        "stronger data providers",
        "better extraction quality",
        "richer evaluation",
        "improved backtest realism",
        "first-class instrument/security model",
        "longer-duration paper operation",
        "deeper operator console",
    ]

    for topic in required_topics:
        assert topic in roadmap


def test_audience_narratives_have_aligned_30_day_build_summaries() -> None:
    audience_paths = [
        PRODUCT_DOCS / "founder_narrative.md",
        PRODUCT_DOCS / "technical_narrative.md",
        PRODUCT_DOCS / "quant_research_narrative.md",
        PRODUCT_DOCS / "operator_and_risk_narrative.md",
    ]

    for path in audience_paths:
        content = path.read_text(encoding="utf-8").lower()
        assert "## 30-day build summary" in content
        assert "what is real today" in content
        assert "must not conclude" in content
        assert "next-phase focus" in content
