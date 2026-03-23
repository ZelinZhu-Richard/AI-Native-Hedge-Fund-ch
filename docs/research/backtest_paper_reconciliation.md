# Backtest To Paper Reconciliation

## Purpose

Day 24 adds a small reconciliation layer that compares the backtest path and the paper-trading path without pretending they are equivalent.

The goal is visibility:

- what timing assumptions the backtest used
- what timing assumptions the paper workflow used
- where those assumptions differ
- where the overall pipeline is internally inconsistent

This layer is advisory and review-facing in Day 24. It is not yet an approval gate.

## What Gets Recorded

The reconciliation layer persists:

- `ExecutionTimingRule`
- `FillAssumption`
- `CostModel`
- `StrategyToPaperMapping`
- `AssumptionMismatch`
- `AvailabilityMismatch`
- `RealismWarning`
- `ReconciliationReport`

Local storage layout:

- `artifacts/reconciliation/execution_timing_rules/`
- `artifacts/reconciliation/fill_assumptions/`
- `artifacts/reconciliation/cost_models/`
- `artifacts/reconciliation/strategy_to_paper_mappings/`
- `artifacts/reconciliation/assumption_mismatches/`
- `artifacts/reconciliation/availability_mismatches/`
- `artifacts/reconciliation/realism_warnings/`
- `artifacts/reconciliation/reconciliation_reports/`

## Current Matching Rules

Reconciliation compares one backtest run to one portfolio proposal and optional paper-trade candidates.

Matching behavior is strict:

- explicit `backtest_run_id` or `portfolio_proposal_id` wins
- otherwise auto-match only succeeds when exactly one plausible same-company candidate exists
- ambiguous matches are refused and require an explicit ID
- paper trades are optional; proposal-only reconciliation is still allowed

## Current Mismatch Types

`AssumptionMismatch` currently records:

- execution-anchor mismatch
- lag mismatch
- cost-model mismatch
- fill-price-basis mismatch
- quantity-basis mismatch
- approval-requirement mismatch

`AvailabilityMismatch` currently records:

- proposal `as_of_time` before signal `effective_at`
- paper-trade `submitted_at` before signal `effective_at`
- proposal approval later than the earliest backtest-style execution window
- backtest timing inconsistency if a mapped signal effective time exceeds the recorded cutoff

## Current Realism Warnings

The system records explicit warnings instead of smoothing over simplifications:

- synthetic price fixtures
- unit-position backtest sizing
- fixed-basis-point cost assumptions
- no intraday microstructure
- no paper fill simulation
- manual reference prices
- missing reference prices
- estimate-only paper-side cost model
- approval delay not represented in backtest execution

## Current Integration Points

Day 24 now connects reconciliation to:

- backtest workflow responses
- paper-trade proposal responses
- portfolio review pipeline responses
- operator review context for proposals and paper trades
- experiment registry context when the matched backtest run already belongs to an experiment
- monitoring run summaries

## What Reviewers Should Watch

- high or critical mismatches
- proposal times that precede signal effective times
- paper submission or approval timing that backtests did not represent
- manual or missing reference prices
- any workflow that appears comparable only because assumptions were left implicit

## What This Still Does Not Do

Day 24 does not provide:

- live execution realism
- intraday fill simulation
- holdings reconciliation
- microstructure modeling
- a promotion gate that blocks on reconciliation results

It makes the mismatch explicit. It does not make the two worlds fully realistic.
