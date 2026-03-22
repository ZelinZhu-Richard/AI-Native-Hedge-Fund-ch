# Day 20 Plan: Portfolio Attribution And Structured Stress Testing

## Goal

Make `PortfolioProposal` artifacts more explainable and more stress-testable without pretending the repository already has institutional portfolio analytics.

## What Day 20 Added

- `PortfolioAttribution`, `PositionAttribution`, `ContributionBreakdown`
- `ScenarioDefinition`, `StressTestRun`, `StressTestResult`, `ExposureShock`
- a dedicated `PortfolioAnalysisService`
- persistence under `artifacts/portfolio_analysis/`
- portfolio workflow integration before risk evaluation
- non-blocking risk warnings for concentration and stress fragility
- operator review context support for proposal-linked attribution and stress artifacts

## Current Design Choices

- deterministic and local only
- review-facing, not auto-approving
- stress findings stay `WARN`-level in v1
- no experiment-registry or backtest integration in this pass
- no factor model, VaR model, or optimizer attribution claims

## Why This Layer Exists

Portfolio proposals should not feel like optimizer fog.

A reviewer should be able to answer:

- which signals and position ideas created the proposal
- which constraints are tight
- which concentration drivers dominate
- how the proposal behaves under a few simple, explicit stresses

## Current Limitations

- proposal analysis is still heuristic
- sector-specific stress depends on normalized `Company.sector`
- stress results are informative, not gating
- the portfolio workflow still supports raw-signal fallback when arbitration context is missing
- this still does not implement the Week 3 reviewed-and-evaluated eligibility gate

## Best Next Step After Day 20

Use the new proposal-analysis artifacts inside the real downstream eligibility boundary, so proposal approval can consider:

- reviewed and evaluated signal status
- arbitration visibility
- proposal explainability
- structured fragility findings
