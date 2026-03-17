# Day 7 Plan

## Goal

Build the first reviewed signal-evaluation and promotion layer on top of the new Day 6 exploratory backtesting boundary.

## Priority 1: Signal Evaluation Artifacts

- define typed evaluation outputs for candidate signals and exploratory backtest runs
- record:
  - lineage completeness
  - ablation slice
  - snapshot coverage
  - failure modes
  - review state
- keep these artifacts separate from `Signal` and `BacktestRun`

## Priority 2: Snapshot-Aware Replay Checks

- replay candidate signals against explicit signal and feature snapshots
- prove that feature availability and signal eligibility checks remain stable under replay
- add regression fixtures for timestamp edge cases

## Priority 3: Promotion Gate

- define the first explicit gate between:
  - candidate signals
  - exploratory backtest artifacts
  - reviewed validation work
- require human-visible review and validation state before anything can move downstream

## Priority 4: Ablation Coverage

- compare current `text_only` signals against future:
  - `price_only`
  - `fundamentals_only`
  - `combined`
- keep absent slices explicit instead of silently dropping them

## Non-Goals

Day 7 should not build:

- portfolio optimization
- live execution
- hidden promotion paths
- performance marketing metrics

## Exact Target

Implement a typed signal-evaluation and promotion workflow that can say:

- what was tested
- with which snapshots
- under which ablation slice
- with which failure modes
- and whether the artifact is still only exploratory or is ready for deeper validation work
