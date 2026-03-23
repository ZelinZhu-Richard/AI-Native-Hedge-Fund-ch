# Portfolio Construction V2

## Purpose

Day 25 turns the portfolio layer into an inspectable proposal engine.

It still does not optimize a portfolio.
It still does not auto-approve anything.
It now records how candidate signals were ranked, why one survived, why another was rejected, and which constraints bound the final proposal.

## What Construction Records Now

Portfolio construction now persists:

- `SelectionRule`
- `ConstraintSet`
- `ConstraintResult`
- `PositionSizingRationale`
- `ConstructionDecision`
- `SelectionConflict`
- `PortfolioSelectionSummary`

These artifacts live under `artifacts/portfolio/` alongside the existing:

- `position_ideas/`
- `portfolio_proposals/`
- `constraints/`
- `risk_checks/`

`PositionIdea` remains an included-position artifact only.
Rejected candidates are represented through `ConstructionDecision`, not fake rejected positions.

## Current Construction Flow

1. Load same-company candidate signals and linked research artifacts.
2. Keep arbitration-withheld behavior explicit: no actionable candidates, empty review-bound proposal context.
3. Keep raw-signal fallback explicit when arbitration context is missing.
4. Apply deterministic intake rules:
   - directional stance required
   - symbol required
   - exact supporting evidence links required
5. Rank surviving candidates lexicographically:
   - arbitrated primary signal first when present
   - then by signal maturity bucket
   - then by absolute score
   - then by later `effective_at`
6. Resolve same-company competition explicitly.
7. Apply simple sizing:
   - `500 bps` for `approved + validated`
   - `300 bps` otherwise
8. Apply explicit constraints:
   - single-name can cap size
   - gross, net, and turnover can reject a candidate before proposal assembly
9. Persist full construction summary before downstream attribution, risk, and review.

## Inclusion And Exclusion

For each candidate signal, the system now records one `ConstructionDecision`.

Included candidates record:

- included outcome
- linked `PositionIdea`
- linked `PositionSizingRationale`
- linked `ConstraintResult` rows

Rejected candidates record:

- rejected outcome
- one or more `ProposalRejectionReason` rows
- linked `ConstraintResult` rows when constraints blocked inclusion
- linked `SelectionConflict` context when another same-company candidate won

Candidates are no longer dropped silently.

## Explainability

The inspectable answer for "why is this position here?" now comes from three layers:

1. `ConstructionDecision`
2. `PositionSizingRationale`
3. `PortfolioSelectionSummary`

The inspectable answer for "why was this other signal not selected?" now comes from:

1. rejected `ConstructionDecision`
2. `ProposalRejectionReason`
3. `SelectionConflict` when same-company candidates competed

## What Remains Simple

- one active idea per company and current symbol path
- no optimizer
- no proportional rebalance
- no holdings-aware turnover model
- no instrument layer beyond current company/ticker path
- no reviewed-and-evaluated eligibility gate yet

This is a construction-discipline layer, not a portfolio optimizer.
