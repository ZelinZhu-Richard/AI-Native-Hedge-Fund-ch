# Portfolio Attribution

## Purpose

Day 20 adds a deterministic explanation layer for `PortfolioProposal`.

The goal is not to claim optimizer-grade attribution.
The goal is to make each proposal inspectable:

- which `Signal` and `PositionIdea` rows contributed
- which evidence links support the included positions
- which constraints still have headroom
- which concentration and exposure characteristics dominate the proposal

## Current Artifacts

Portfolio analysis persists local artifacts under `artifacts/portfolio_analysis/`:

- `position_attributions/`
- `portfolio_attributions/`
- `scenario_definitions/`
- `stress_test_runs/`
- `stress_test_results/`

The explainability layer uses:

- `PositionAttribution`
- `PortfolioAttribution`
- `ContributionBreakdown`

These artifacts are first-class and linked back to the proposal through:

- `PortfolioProposal.portfolio_attribution_id`
- `PositionAttribution.portfolio_proposal_id`
- `PositionAttribution.position_idea_id`
- signal, evidence-link, and constraint identifiers in provenance and structured fields

## What Position Attribution Explains Today

Each included `PositionIdea` gets one `PositionAttribution`.

It records:

- `signal_id`
- `supporting_evidence_link_ids`
- relevant `portfolio_constraint_ids`
- whether the idea came from an arbitrated primary signal or raw-signal fallback
- structured `ContributionBreakdown` rows for:
  - proposed weight
  - supporting evidence-link count
  - signal score when the signal artifact is available
  - confidence and uncertainty when present
  - single-name constraint headroom
  - sector membership when normalized company metadata exists

The operator-facing summary is intentionally short, but it is backed by explicit breakdown rows rather than prose-only explanation.

## What Portfolio Attribution Explains Today

Each `PortfolioProposal` gets one `PortfolioAttribution`.

It summarizes:

- dominant position ideas ranked by absolute proposed weight
- gross, net, and cash-buffer characteristics from `PortfolioExposureSummary`
- constraint headroom for:
  - single-name
  - gross exposure
  - net exposure
  - turnover
- top-sector concentration only when `Company.sector` resolves cleanly

If sector metadata is missing, the attribution says so explicitly instead of guessing a sector from ticker or document text.

## What This Does Not Claim

This is not:

- optimizer attribution
- factor attribution
- covariance-based risk attribution
- marginal contribution to VaR
- production portfolio analytics

The current layer explains the deterministic proposal that already exists.
It does not manufacture a deeper model than the repository has.

## How Reviewers Should Use It

Use attribution to answer a few concrete questions:

- Why does this proposal exist at all?
- Which signal and evidence links are actually driving it?
- Is one position doing most of the work?
- Are the current weights only barely inside the explicit constraints?
- Is sector concentration visible or unavailable?

Attribution is advisory.
It improves review quality, but it does not replace the explicit approval boundary.
