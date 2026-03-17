# Day 6 Plan

## Goal

Build the first honest backtesting and simulation skeleton with strong temporal discipline.

## Priority 1: Backtesting Contracts

- refine `BacktestRun`
- add `BacktestConfig`
- add `ExecutionAssumption`
- add `StrategyDecision`
- add `SimulationEvent`
- add `PerformanceSummary`
- add `BenchmarkReference`
- refine `DataSnapshot` with explicit information cutoffs

## Priority 2: Deterministic Local Engine

- consume persisted candidate signals and features
- apply a simple unit-position decision rule
- execute at next-bar open
- record every decision and fill explicitly
- persist snapshots, runs, decisions, events, summaries, and benchmarks

## Priority 3: Temporal Correctness

- enforce `effective_at <= decision_time`
- enforce `FeatureValue.available_at <= decision_time`
- separate snapshot time from information cutoff time
- reject same-bar execution
- record leakage and integrity checks on the run artifact

## Priority 4: Honest Assumptions

- make transaction cost and slippage explicit
- use synthetic price fixtures only for mechanical testing
- mark every Day 6 run `exploratory_only`
- emit only simple benchmarks:
  - `flat_baseline`
  - `buy_and_hold`

## Exact Target

Implement a reproducible exploratory backtesting boundary that proves the platform can:

- replay candidate signals under explicit temporal controls
- simulate mechanical fills and marks honestly
- persist structured run artifacts for later validation work

without pretending the current signals are validated or profitable.
