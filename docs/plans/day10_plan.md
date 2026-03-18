# Day 10 Plan

## Goal

Build the first reviewed signal-evaluation and promotion gate on top of the new Day 9 baseline and ablation harness.

## Why This Is Next

The repo now has:

- evidence-backed research artifacts
- candidate features and signals
- exploratory backtesting
- baseline and ablation comparisons
- portfolio proposals and paper-trade candidates

What it still lacks is a disciplined boundary that answers:

- which signal slices have actually been reviewed
- which evaluation runs are acceptable as validation evidence
- which downstream workflows are allowed to consume a signal beyond exploratory mode

## Priorities

### 1. Signal Evaluation Artifacts

- add typed evaluation records for candidate signals and strategy variants
- record:
  - selected snapshot IDs
  - compared baselines
  - review notes
  - blocking issues
  - outcome

### 2. Promotion Gate

- define the first explicit promotion path from:
  - candidate signal
  - exploratory backtest or ablation evidence
  - reviewed evaluation decision
  - validation-aware downstream eligibility

### 3. Snapshot-Native Selection

- stop relying on cutoff-only loading for evaluation inputs
- make selected artifact slices and snapshot IDs first-class in the evaluation flow

### 4. Downstream Enforcement

- make portfolio proposal and paper-trade flows reject signals that have not crossed the required evaluation gate

### 5. Harder Replay Tests

- add adversarial tests for:
  - stale evaluation artifacts
  - wrong snapshot selection
  - promotion without review
  - downstream consumption of blocked signals

## Non-Goals

- live trading
- portfolio optimization
- richer factor engineering
- statistical significance tooling

## Exact Target

At the end of Day 10, the repository should be able to say:

- which signal or variant was evaluated
- on which exact snapshot slice
- against which baseline set
- what the human-review outcome was
- whether the artifact is still exploratory or is allowed into stricter downstream workflows
