# Day 25 Plan

## Goal

Make portfolio construction cleaner, more inspectable, and more constraint-aware.

The portfolio layer should no longer look like a mechanical signal-to-position mapper.
It should record why candidates were included, why others were rejected, and which constraints shaped the final proposal.

## What Day 25 Adds

- explicit portfolio-construction schemas
- deterministic candidate ranking and same-company conflict recording
- explicit inclusion and rejection decisions
- explicit position-sizing rationales
- explicit constraint application results
- proposal-level construction summary
- downstream construction context in risk review, attribution, operator review, and paper-trade traceability

## What Day 25 Does Not Add

- optimizer-based construction
- proportional rebalance
- instrument-level portfolio modeling
- reviewed-and-evaluated eligibility gate
- richer holdings-aware turnover logic

## Main Design Decisions

- `PortfolioConstructionService` remains the public construction boundary
- construction artifacts live under `artifacts/portfolio/`
- `PositionIdea` remains included-only
- rejected candidates are represented via `ConstructionDecision`
- portfolio-level hard constraints reject candidates during construction instead of relying only on later risk failure

## Immediate Follow-On

The next highest-leverage step is to make the Week 4 eligibility gate consume:

- `PortfolioSelectionSummary`
- `ConstructionDecision`
- `ConstraintResult`
- `ValidationGate`

That is the point where structural quality, policy review state, and explicit construction logic should converge.
